#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto-ddns-cloudflare.py — Cloudflare Auto DDNS Tool v2.0
=========================================================
Tự động cập nhật DNS record trên Cloudflare theo IP WAN hiện tại.
Auto-update Cloudflare DNS records to the current WAN IP.

Author : cf-auto-ddns project contributors
License: MIT
Version: 2.0.0
"""

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# ── Đường dẫn cơ sở ──────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent
DATA_FILE  = BASE_DIR / "data.json"
LOG_DIR    = BASE_DIR / "log"
SCRIPT_DIR = BASE_DIR  # .sh được tạo cùng thư mục với script này

# ── Màu sắc terminal ─────────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BLUE   = "\033[94m"
    GREY   = "\033[90m"


def cprint(color: str, msg: str):
    print(f"{color}{msg}{C.RESET}")

def banner():
    print(f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════╗
║     Cloudflare Auto DDNS Tool  v2.0                  ║
║     Tự động cập nhật DNS Cloudflare theo IP WAN       ║
╚══════════════════════════════════════════════════════╝{C.RESET}
""")

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

def get_log_file() -> Path:
    """
    Trả về đường dẫn log file hiện tại.
    Tách log mới sau mỗi 3 ngày: log/ddns-YYYYMMDD.log
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today     = datetime.now()
    day_index = today.toordinal()
    # Nhóm 3 ngày: 0,1,2 → nhóm 0; 3,4,5 → nhóm 1 …
    group     = day_index // 3
    # Ngày bắt đầu nhóm để dùng làm tên file
    start_day = datetime.fromordinal(group * 3)
    filename  = f"ddns-{start_day.strftime('%Y%m%d')}.log"
    return LOG_DIR / filename


def log(msg: str, level: str = "INFO", echo: bool = True):
    """Ghi log vào file và hiển thị ra màn hình."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line      = f"[{timestamp}] [{level}] {msg}"
    log_path  = get_log_file()
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    if echo:
        color = {
            "INFO" : C.RESET,
            "OK"   : C.GREEN,
            "WARN" : C.YELLOW,
            "ERROR": C.RED,
        }.get(level, C.RESET)
        print(f"{color}{line}{C.RESET}")

# ─────────────────────────────────────────────────────────────────────────────
# DATA / CONFIG
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict = {
    "zone_id"    : "",
    "api_token"  : "",
    "dns_records": [],
    "cron_interval_minutes": 5,
    "script_name": "cf-ddns-run.sh",
}

def load_config() -> dict:
    if DATA_FILE.exists():
        with DATA_FILE.open(encoding="utf-8") as fh:
            return json.load(fh)
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    with DATA_FILE.open("w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    cprint(C.GREEN, f"✔ Đã lưu cấu hình vào {DATA_FILE}")


def show_config(cfg: dict):
    """In cấu hình hiện tại ra màn hình."""
    print()
    cprint(C.CYAN, "── Cấu hình hiện tại ──────────────────────────────────")
    print(f"  Zone ID       : {cfg.get('zone_id','(chưa đặt)')}")
    token = cfg.get('api_token', '')
    masked = token[:6] + "***" + token[-4:] if len(token) > 10 else "***"
    print(f"  API Token     : {masked}")
    print(f"  Cron interval : mỗi {cfg.get('cron_interval_minutes', 5)} phút")
    print(f"  Script name   : {cfg.get('script_name', 'cf-ddns-run.sh')}")
    records = cfg.get("dns_records", [])
    if records:
        print("  DNS Records   :")
        for r in records:
            proxy_icon = "🟠" if r.get("proxied") else "⚫"
            print(f"    {proxy_icon}  {r['name']}  |  proxied={r['proxied']}  "
                  f"|  TTL={r['ttl']}  |  type={r['type']}")
    else:
        cprint(C.YELLOW, "  DNS Records   : (chưa có)")
    cprint(C.CYAN, "───────────────────────────────────────────────────────")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# INPUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def prompt(msg: str, default: str = "", secret: bool = False) -> str:
    """Nhập thông tin từ người dùng, có giá trị mặc định."""
    hint = f" [{default}]" if default else ""
    try:
        if secret:
            import getpass
            val = getpass.getpass(f"  {msg}{hint}: ")
        else:
            val = input(f"  {msg}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val if val else default


def confirm(msg: str, default: bool = True) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    ans  = prompt(f"{msg} {hint}").lower()
    if ans in ("y", "yes", "có", "co"):
        return True
    if ans in ("n", "no", "không", "khong"):
        return False
    return default


# ─────────────────────────────────────────────────────────────────────────────
# SETUP / CONFIGURE
# ─────────────────────────────────────────────────────────────────────────────

def parse_record_entry(entry: str) -> dict | None:
    """
    Phân tích chuỗi nhập dạng: name:proxied[:ttl[:type]]
    Ví dụ: "sub.example.com:true:120:A"
    Trả về dict hoặc None nếu lỗi.
    """
    parts = [p.strip() for p in entry.split(":")]
    if len(parts) < 2:
        return None
    name    = parts[0]
    proxied_str = parts[1].lower()
    if proxied_str not in ("true", "false"):
        return None
    proxied = proxied_str == "true"
    ttl     = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 120
    rtype   = parts[3].upper() if len(parts) > 3 and parts[3] else "A"
    if not name:
        return None
    return {"name": name, "proxied": proxied, "ttl": ttl, "type": rtype}


def cmd_configure():
    """Nhập / chỉnh sửa cấu hình và lưu vào data.json."""
    cprint(C.BOLD, "\n🔧  Nhập thông tin cấu hình")
    cprint(C.GREY, "   (Nhấn Enter để giữ giá trị hiện tại)\n")

    cfg = load_config()

    # ── Zone ID & API Token ──
    cfg["zone_id"]   = prompt("Zone ID", cfg.get("zone_id", ""))
    cfg["api_token"] = prompt("API Token", cfg.get("api_token", ""), secret=False)

    # ── Cron interval ──
    interval_str = prompt("Cron interval (phút)", str(cfg.get("cron_interval_minutes", 5)))
    cfg["cron_interval_minutes"] = int(interval_str) if interval_str.isdigit() else 5

    # ── Script name ──
    cfg["script_name"] = prompt("Tên file script .sh sẽ tạo", cfg.get("script_name", "cf-ddns-run.sh"))
    if not cfg["script_name"].endswith(".sh"):
        cfg["script_name"] += ".sh"

    # ── DNS Records ──
    print()
    cprint(C.CYAN, "  DNS Records — định dạng: name:proxied:ttl:type")
    cprint(C.GREY,  "  Ví dụ: sub.example.com:true:120:A")
    cprint(C.GREY,  "  (Nhập rỗng để kết thúc danh sách)")

    existing = cfg.get("dns_records", [])
    if existing:
        cprint(C.YELLOW, f"\n  Hiện có {len(existing)} record. Nhập lại toàn bộ hay chỉ thêm?")
        action = prompt("  r=nhập lại toàn bộ | a=thêm vào | Enter=giữ nguyên", "keep").lower()
        if action == "r":
            existing = []
        elif action != "a":
            pass  # giữ nguyên

    records = list(existing)
    idx = len(records) + 1
    while True:
        raw = prompt(f"  Record #{idx}")
        if not raw:
            break
        rec = parse_record_entry(raw)
        if rec is None:
            cprint(C.RED, "  ✗ Định dạng không hợp lệ. Thử lại.")
            continue
        records.append(rec)
        idx += 1

    if not records:
        cprint(C.YELLOW, "  Cảnh báo: Chưa có DNS record nào!")

    cfg["dns_records"] = records
    save_config(cfg)
    show_config(cfg)


# ─────────────────────────────────────────────────────────────────────────────
# GENERATE BASH SCRIPT
# ─────────────────────────────────────────────────────────────────────────────

def cron_expr(minutes: int) -> str:
    """Chuyển số phút thành biểu thức cron đơn giản."""
    if minutes <= 0:
        return "* * * * *"
    if minutes == 1:
        return "* * * * *"
    if minutes < 60:
        return f"*/{minutes} * * * *"
    hours = minutes // 60
    return f"0 */{hours} * * *"


def generate_bash_script(cfg: dict) -> Path:
    """Tạo file bash script dựa vào data.json."""
    zone_id   = cfg["zone_id"]
    api_token = cfg["api_token"]
    records   = cfg.get("dns_records", [])
    interval  = cfg.get("cron_interval_minutes", 5)
    script_name = cfg.get("script_name", "cf-ddns-run.sh")
    script_path = SCRIPT_DIR / script_name

    # ── Xây dựng block khai báo từng record ──
    record_lines = []
    for r in records:
        proxied = "true" if r["proxied"] else "false"
        record_lines.append(
            f'    "{r["name"]}:{proxied}:{r["ttl"]}:{r["type"]}"'
        )
    dns_block = "\n".join(record_lines)

    log_dir_str   = str(LOG_DIR)
    cron_schedule = cron_expr(interval)

    script_content = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        # ============================================================
        # Auto-generated by auto-ddns-cloudflare.py  (v2.0)
        # Generated at : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        # Cron schedule: {cron_schedule}   (mỗi {interval} phút)
        #
        # KHÔNG chỉnh sửa thủ công — hãy chạy lại python script để tái tạo.
        # DO NOT edit manually — re-run the python script to regenerate.
        # ============================================================
        set -uo pipefail

        # ── Cấu hình ──────────────────────────────────────────────
        ZONE_ID="{zone_id}"
        API_TOKEN="{api_token}"

        DNS_RECORDS=(
        {dns_block}
        )

        # ── Log rotation: tách log mới sau mỗi 3 ngày ─────────────
        # LOG_DIR luôn tính tương đối từ vị trí của script này
        SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
        LOG_DIR="$SCRIPT_DIR/log"
        mkdir -p "$LOG_DIR"

        _log_file() {{
            # Tính nhóm 3-ngày từ epoch day
            local epoch_day=$(( $(date +%s) / 86400 ))
            local group=$(( epoch_day / 3 ))
            local group_start_epoch=$(( group * 3 * 86400 ))
            local group_date
            group_date=$(date -d "@$group_start_epoch" +%Y%m%d 2>/dev/null \\
                      || date -r  "$group_start_epoch" +%Y%m%d 2>/dev/null \\
                      || date +%Y%m%d)
            echo "$LOG_DIR/ddns-$group_date.log"
        }}

        LOG_FILE=$(_log_file)

        log() {{
            local level="${{1:-INFO}}"
            local msg="$2"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $msg" | tee -a "$LOG_FILE"
        }}

        # ── Kiểm tra công cụ cần thiết ────────────────────────────
        for cmd in curl jq; do
            if ! command -v "$cmd" >/dev/null 2>&1; then
                log "ERROR" "Thiếu lệnh '$cmd'. Cài: sudo apt install $cmd"
                exit 1
            fi
        done

        # ── Lấy IP hiện tại ───────────────────────────────────────
        get_current_ip() {{
            local ip
            for url in "https://ipv4.icanhazip.com" "https://api.ipify.org" "https://ifconfig.me/ip"; do
                ip=$(curl -s -4 --max-time 5 "$url" | tr -d '[:space:]')
                if [[ "$ip" =~ ^([0-9]{{1,3}}\.){{3}}[0-9]{{1,3}}$ ]]; then
                    echo "$ip"
                    return 0
                fi
            done
            return 1
        }}

        CURRENT_IP=$(get_current_ip)
        if [[ -z "$CURRENT_IP" ]]; then
            log "ERROR" "Không lấy được IP hiện tại từ bất kỳ nguồn nào."
            exit 1
        fi
        log "INFO" "IP WAN hiện tại: $CURRENT_IP"

        EXIT_CODE=0

        # ── Vòng lặp cập nhật từng record ─────────────────────────
        for ENTRY in "${{DNS_RECORDS[@]}}"; do
            IFS=':' read -r DNS_RECORD PROXIED TTL RECORD_TYPE <<< "$ENTRY"

            if [[ "$PROXIED" != "true" && "$PROXIED" != "false" ]]; then
                log "WARN" "[$DNS_RECORD] proxied không hợp lệ ('$PROXIED'). Bỏ qua."
                EXIT_CODE=1
                continue
            fi

            # Tra cứu record trên Cloudflare
            LOOKUP=$(curl -s -X GET \\
                "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=$RECORD_TYPE&name=$DNS_RECORD" \\
                -H "Authorization: Bearer $API_TOKEN" \\
                -H "Content-Type: application/json")

            if [[ "$(echo "$LOOKUP" | jq -r '.success')" != "true" ]]; then
                log "ERROR" "[$DNS_RECORD] Tra cứu thất bại: $(echo "$LOOKUP" | jq -c '.errors')"
                EXIT_CODE=1
                continue
            fi

            RECORD_ID=$(echo "$LOOKUP" | jq -r '.result[0].id')
            REMOTE_IP=$(echo "$LOOKUP" | jq -r '.result[0].content')
            REMOTE_PROXIED=$(echo "$LOOKUP" | jq -r '.result[0].proxied')

            if [[ "$RECORD_ID" == "null" || -z "$RECORD_ID" ]]; then
                log "ERROR" "[$DNS_RECORD] Không tìm thấy record (type=$RECORD_TYPE) trong zone."
                EXIT_CODE=1
                continue
            fi

            if [[ "$CURRENT_IP" == "$REMOTE_IP" && "$PROXIED" == "$REMOTE_PROXIED" ]]; then
                log "INFO" "[$DNS_RECORD] Không thay đổi (IP=$CURRENT_IP, proxied=$PROXIED)."
                continue
            fi

            log "INFO" "[$DNS_RECORD] Cập nhật: $REMOTE_IP -> $CURRENT_IP | proxied $REMOTE_PROXIED -> $PROXIED"

            UPDATE=$(curl -s -X PUT \\
                "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \\
                -H "Authorization: Bearer $API_TOKEN" \\
                -H "Content-Type: application/json" \\
                --data "{{\\\"type\\\":\\\"$RECORD_TYPE\\\",\\\"name\\\":\\\"$DNS_RECORD\\\",\\\"content\\\":\\\"$CURRENT_IP\\\",\\\"ttl\\\":$TTL,\\\"proxied\\\":$PROXIED}}")

            if [[ "$(echo "$UPDATE" | jq -r '.success')" == "true" ]]; then
                log "OK"    "[$DNS_RECORD] ✔ Cập nhật thành công -> $CURRENT_IP (proxied=$PROXIED)"
            else
                log "ERROR" "[$DNS_RECORD] ✗ Cập nhật thất bại: $(echo "$UPDATE" | jq -c '.errors')"
                EXIT_CODE=1
            fi
        done

        exit $EXIT_CODE
        # ── Crontab entry (được tự động thêm bởi python script) ───
        # {cron_schedule} {script_path} >> /dev/null 2>&1
    """)

    with script_path.open("w", encoding="utf-8") as fh:
        fh.write(script_content)
    script_path.chmod(0o755)
    cprint(C.GREEN, f"✔ Đã tạo script: {script_path}")
    return script_path


def cmd_generate():
    """Tạo / tái tạo bash script từ cấu hình hiện tại."""
    cfg = load_config()
    if not cfg.get("zone_id") or not cfg.get("api_token"):
        cprint(C.RED, "✗ Chưa có cấu hình. Hãy chạy 'configure' trước.")
        return
    if not cfg.get("dns_records"):
        cprint(C.RED, "✗ Chưa có DNS record nào trong cấu hình.")
        return
    generate_bash_script(cfg)


# ─────────────────────────────────────────────────────────────────────────────
# DRY-RUN (kiểm tra thử)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_test():
    """Chạy script bash ở chế độ kiểm tra (dry-run): chỉ in kết quả, không thêm cron."""
    cfg = load_config()
    script_name = cfg.get("script_name", "cf-ddns-run.sh")
    script_path = SCRIPT_DIR / script_name

    if not script_path.exists():
        cprint(C.YELLOW, "⚠ Script chưa được tạo. Đang tạo...")
        generate_bash_script(cfg)

    cprint(C.CYAN, f"\n▶ Chạy thử: {script_path}\n")
    log(f"[DRY-RUN] Bắt đầu kiểm tra script {script_path}", "INFO")
    try:
        result = subprocess.run(
            ["/usr/bin/env", "bash", str(script_path)],
            capture_output=False,
            text=True,
        )
        if result.returncode == 0:
            cprint(C.GREEN, "\n✔ Script chạy thành công (exit 0).")
            log("[DRY-RUN] Kết thúc thành công", "OK")
        else:
            cprint(C.RED, f"\n✗ Script kết thúc với mã lỗi {result.returncode}.")
            log(f"[DRY-RUN] Kết thúc với lỗi code={result.returncode}", "ERROR")
    except FileNotFoundError as exc:
        cprint(C.RED, f"✗ Không thể chạy bash: {exc}")
        log(f"[DRY-RUN] Lỗi: {exc}", "ERROR")


# ─────────────────────────────────────────────────────────────────────────────
# CRONTAB MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def get_current_crontab() -> str:
    """Đọc crontab hiện tại của user."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception:
        return ""


def cmd_cron_add():
    """Tự động thêm lịch cron vào crontab sau khi người dùng xác nhận."""
    cfg = load_config()
    script_name = cfg.get("script_name", "cf-ddns-run.sh")
    script_path = SCRIPT_DIR / script_name
    interval    = cfg.get("cron_interval_minutes", 5)
    schedule    = cron_expr(interval)

    if not shutil.which("crontab"):
        cprint(C.RED, "✗ Lệnh 'crontab' không tìm thấy trên hệ thống này.")
        return

    if not script_path.exists():
        cprint(C.YELLOW, "⚠ Script chưa tồn tại. Đang tạo...")
        generate_bash_script(cfg)

    cron_line = f"{schedule} {script_path} >> /dev/null 2>&1"

    # Kiểm tra xem cron entry đã tồn tại chưa
    current = get_current_crontab()
    if str(script_path) in current:
        cprint(C.YELLOW, f"⚠ Đã tồn tại cron entry cho {script_path}.")
        if not confirm("Ghi đè / cập nhật lại entry cũ?", default=False):
            cprint(C.GREY, "Không thay đổi crontab.")
            return
        # Xóa dòng cũ
        lines = [l for l in current.splitlines() if str(script_path) not in l]
        current = "\n".join(lines)

    cprint(C.CYAN, f"\n  Sẽ thêm vào crontab:\n  {C.BOLD}{cron_line}{C.RESET}\n")
    if not confirm("Xác nhận thêm vào crontab?"):
        cprint(C.GREY, "Đã hủy.")
        return

    new_crontab = current.rstrip("\n") + "\n" + cron_line + "\n"
    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        capture_output=True, text=True
    )
    if proc.returncode == 0:
        cprint(C.GREEN, "✔ Đã thêm vào crontab thành công!")
        log(f"Đã thêm cron entry: {cron_line}", "OK")
    else:
        cprint(C.RED, f"✗ Lỗi khi thêm crontab: {proc.stderr}")
        log(f"Lỗi thêm crontab: {proc.stderr}", "ERROR")


def cmd_cron_list():
    """Hiển thị crontab hiện tại."""
    current = get_current_crontab()
    if current.strip():
        cprint(C.CYAN, "\n── Crontab hiện tại ──────────────────────────────────")
        print(current)
        cprint(C.CYAN, "─────────────────────────────────────────────────────")
    else:
        cprint(C.YELLOW, "Crontab hiện tại trống.")


def cmd_cron_remove():
    """Xóa cron entry của script khỏi crontab."""
    cfg = load_config()
    script_name = cfg.get("script_name", "cf-ddns-run.sh")
    script_path = SCRIPT_DIR / script_name

    current = get_current_crontab()
    if str(script_path) not in current:
        cprint(C.YELLOW, "⚠ Không tìm thấy cron entry cho script này.")
        return

    cprint(C.CYAN, f"\n  Sẽ xóa entry chứa: {script_path}")
    if not confirm("Xác nhận xóa khỏi crontab?", default=False):
        cprint(C.GREY, "Đã hủy.")
        return

    lines = [l for l in current.splitlines() if str(script_path) not in l]
    new_crontab = "\n".join(lines) + "\n"
    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        capture_output=True, text=True
    )
    if proc.returncode == 0:
        cprint(C.GREEN, "✔ Đã xóa cron entry.")
        log(f"Đã xóa cron entry: {script_path}", "OK")
    else:
        cprint(C.RED, f"✗ Lỗi: {proc.stderr}")


# ─────────────────────────────────────────────────────────────────────────────
# LOG VIEWER
# ─────────────────────────────────────────────────────────────────────────────

def cmd_logs():
    """Hiển thị log gần đây."""
    log_files = sorted(LOG_DIR.glob("ddns-*.log"), reverse=True) if LOG_DIR.exists() else []
    if not log_files:
        cprint(C.YELLOW, "Chưa có file log nào.")
        return
    latest = log_files[0]
    cprint(C.CYAN, f"\n── Log file: {latest} ─────────────────────────────────")
    lines_str = prompt("Hiển thị bao nhiêu dòng gần nhất", "50")
    n = int(lines_str) if lines_str.isdigit() else 50
    with latest.open(encoding="utf-8") as fh:
        all_lines = fh.readlines()
    for line in all_lines[-n:]:
        line = line.rstrip()
        if "[ERROR]" in line:
            print(f"{C.RED}{line}{C.RESET}")
        elif "[OK]" in line:
            print(f"{C.GREEN}{line}{C.RESET}")
        elif "[WARN]" in line:
            print(f"{C.YELLOW}{line}{C.RESET}")
        else:
            print(line)
    cprint(C.CYAN, f"─────────────────────────────────────────────────────")
    if len(log_files) > 1:
        cprint(C.GREY, f"  (Có {len(log_files)} file log. Xem thêm trong thư mục: {LOG_DIR})")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────────────────────────────────────

MENU = [
    ("1", "configure",   "Nhập / chỉnh sửa cấu hình                  (lưu data.json)"),
    ("2", "generate",    "Tạo / tái tạo bash script (.sh)"),
    ("3", "test",        "Chạy thử bash script (dry-run, không sửa crontab)"),
    ("4", "cron-add",    "Thêm vào crontab -e sau khi xác nhận"),
    ("5", "cron-list",   "Xem crontab hiện tại"),
    ("6", "cron-remove", "Xóa cron entry của script"),
    ("7", "logs",        "Xem log gần đây"),
    ("8", "show",        "Hiển thị cấu hình hiện tại"),
    ("0", "exit",        "Thoát"),
]

ACTIONS = {
    "1": cmd_configure,
    "2": cmd_generate,
    "3": cmd_test,
    "4": cmd_cron_add,
    "5": cmd_cron_list,
    "6": cmd_cron_remove,
    "7": cmd_logs,
    "8": lambda: show_config(load_config()),
    "0": lambda: sys.exit(0),
}

# Alias dạng tên lệnh
ALIAS = {row[1]: row[0] for row in MENU}


def print_menu():
    cprint(C.BOLD, "  Menu chính:")
    for key, name, desc in MENU:
        print(f"  {C.CYAN}{key}{C.RESET}  {desc}")
    print()


def interactive_mode():
    banner()
    while True:
        print_menu()
        choice = prompt("Chọn").strip()
        if choice in ACTIONS:
            ACTIONS[choice]()
        elif choice in ALIAS:
            ACTIONS[ALIAS[choice]]()
        else:
            cprint(C.RED, "Lựa chọn không hợp lệ.")


def cli_mode(args: list[str]):
    """Chạy theo tham số dòng lệnh."""
    cmd = args[0].lower()
    mapping = {
        "configure"  : cmd_configure,
        "generate"   : cmd_generate,
        "test"       : cmd_test,
        "cron-add"   : cmd_cron_add,
        "cron-list"  : cmd_cron_list,
        "cron-remove": cmd_cron_remove,
        "logs"       : cmd_logs,
        "show"       : lambda: show_config(load_config()),
    }
    if cmd not in mapping:
        cprint(C.RED, f"Lệnh không hợp lệ: {cmd}")
        cprint(C.GREY, f"Các lệnh hợp lệ: {', '.join(mapping)}")
        sys.exit(1)
    banner()
    mapping[cmd]()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_mode(sys.argv[1:])
    else:
        interactive_mode()

