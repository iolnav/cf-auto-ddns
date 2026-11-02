# Cloudflare Auto DDNS Tool — v2.0

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python"/>
  <img src="https://img.shields.io/badge/platform-Ubuntu%20%2F%20Linux-orange?style=flat-square&logo=linux"/>
  <img src="https://img.shields.io/badge/Cloudflare-DNS-F38020?style=flat-square&logo=cloudflare"/>
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square"/>
</p>

---

## 🇻🇳 Tiếng Việt

### Giới thiệu

**auto-ddns-cloudflare.py** là công cụ Python tự động cập nhật DNS record trên Cloudflare theo IP WAN (địa chỉ IP công cộng) hiện tại của máy chủ.  
Tool là phiên bản **v2.0** — được viết lại từ script Bash gốc [`cf-ddns.sh`](./cf-ddns.sh) (v1.0) — bổ sung giao diện menu tương tác, quản lý cấu hình qua file JSON, sinh script bash tự động và tích hợp crontab tiện lợi.

### Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 🔧 Cấu hình tương tác | Nhập `ZONE_ID`, `API_TOKEN`, danh sách DNS record (bao gồm TTL & record type riêng cho từng record) và khoảng cách cron |
| 💾 Lưu cấu hình | Toàn bộ cấu hình lưu vào `data.json` cạnh script |
| 📜 Sinh script Bash | Tự động tạo file `.sh` sẵn sàng chạy trên Ubuntu/Linux |
| 🧪 Dry-run | Chạy thử script trước khi thêm vào crontab |
| ⏰ Quản lý crontab | Thêm, xem, xóa cron entry tự động sau khi xác nhận |
| 📋 Logging thông minh | Log ghi vào thư mục `log/`, tự tách sang file mới sau mỗi **3 ngày** hoạt động |
| 🖥️ CLI mode | Hỗ trợ chạy lệnh trực tiếp qua tham số (không cần menu) |

### Yêu cầu hệ thống

- Python **3.10+**
- `bash`, `curl`, `jq` — cài trên Ubuntu: `sudo apt install curl jq`
- Tài khoản Cloudflare với **Zone ID** và **API Token** có quyền chỉnh sửa DNS

### Cài đặt & Sử dụng

#### 1. Clone & cấp quyền

```bash
git clone https://github.com/your-user/cf-auto-ddns.git
cd cf-auto-ddns
chmod +x auto-ddns-cloudflare.py
```

#### 2. Chạy menu tương tác

```bash
python3 auto-ddns-cloudflare.py
```

Giao diện menu sẽ hiện ra:

```
  Menu chính:
  1  Nhập / chỉnh sửa cấu hình                  (lưu data.json)
  2  Tạo / tái tạo bash script (.sh)
  3  Chạy thử bash script (dry-run, không sửa crontab)
  4  Thêm vào crontab -e sau khi xác nhận
  5  Xem crontab hiện tại
  6  Xóa cron entry của script
  7  Xem log gần đây
  8  Hiển thị cấu hình hiện tại
  0  Thoát
```

#### 3. Chạy qua CLI (không cần menu)

```bash
python3 auto-ddns-cloudflare.py configure    # Nhập cấu hình
python3 auto-ddns-cloudflare.py generate     # Tạo bash script
python3 auto-ddns-cloudflare.py test         # Chạy thử
python3 auto-ddns-cloudflare.py cron-add     # Thêm vào crontab
python3 auto-ddns-cloudflare.py cron-list    # Xem crontab
python3 auto-ddns-cloudflare.py cron-remove  # Xóa khỏi crontab
python3 auto-ddns-cloudflare.py logs         # Xem log
python3 auto-ddns-cloudflare.py show         # Xem cấu hình
```

### Định dạng nhập DNS Record

Mỗi record theo định dạng: `tên_record:proxied:ttl:type`

```
sub.example.com:true:120:A      # bật proxy Cloudflare, TTL 120s, IPv4
api.example.com:false:300:A     # tắt proxy, TTL 300s, IPv4
ipv6.example.com:false:120:AAAA # IPv6, tắt proxy
```

### Cấu trúc thư mục

```
cf-auto-ddns/
├── auto-ddns-cloudflare.py   ← Tool chính (v2.0)
├── cf-ddns.sh                ← Script gốc tham khảo (v1.0, KHÔNG sửa đổi)
├── data.json                 ← Cấu hình (tự sinh sau khi configure)
├── cf-ddns-run.sh            ← Bash script được tạo tự động
├── log/
│   ├── ddns-20261102.log     ← Log theo nhóm 3 ngày
│   └── ddns-20261105.log
└── README.md
```

### Hệ thống Log

- Log lưu trong thư mục `log/` cạnh `auto-ddns-cloudflare.py`
- Tên file: `ddns-YYYYMMDD.log` — ngày là ngày đầu của nhóm 3 ngày
- Sau mỗi 3 ngày hoạt động, log sẽ được ghi vào file mới tự động (cả Python script lẫn Bash script đều tuân theo cùng logic)
- Mức log: `INFO`, `OK`, `WARN`, `ERROR`

### Lấy Zone ID & API Token

1. Đăng nhập [Cloudflare Dashboard](https://dash.cloudflare.com)
2. **Zone ID**: Trang tổng quan (Overview) của domain → cột phải → *Zone ID*
3. **API Token**: `Profile > API Tokens > Create Token` → chọn template *Edit zone DNS*

---

## ⚠️ Cảnh báo / Lưu ý bảo mật

> **CAUTION — Bảo vệ file `data.json`**  
> File này chứa API Token Cloudflare dạng plain text.  
> Hãy đảm bảo file chỉ có thể đọc bởi user hiện tại:
> ```bash
> chmod 600 data.json
> chmod 700 cf-ddns-run.sh
> ```

> **WARNING**
> - **Không commit `data.json`** lên git public repository.
> - Thêm vào `.gitignore`:
>   ```
>   data.json
>   log/
>   cf-ddns-run.sh
>   ```
> - API Token nên có scope tối thiểu: **Zone > DNS > Edit** cho zone cụ thể.

> **NOTE**  
> Script được tạo (`.sh`) ghi API Token vào nội dung file. Nên đặt quyền `chmod 700` cho file này.

---

## 🇬🇧 English

### Overview

**auto-ddns-cloudflare.py** is a Python tool that automatically updates Cloudflare DNS records to match the server's current public WAN IP address.  
This is **v2.0** — a full rewrite of the original Bash script [`cf-ddns.sh`](./cf-ddns.sh) (v1.0) — featuring an interactive menu, JSON-based configuration, automatic Bash script generation and crontab integration.

### Key Features

| Feature | Description |
|---------|-------------|
| 🔧 Interactive config | Enter `ZONE_ID`, `API_TOKEN`, DNS records (with per-record TTL & record type) and cron interval |
| 💾 Persistent config | All settings saved to `data.json` next to the script |
| 📜 Bash script generator | Auto-generates a ready-to-run `.sh` file for Ubuntu/Linux |
| 🧪 Dry-run | Test the script before touching crontab |
| ⏰ Crontab management | Add, view, remove cron entries with confirmation |
| 📋 Smart logging | Logs to `log/` directory, auto-rotates to a new file every **3 days** |
| 🖥️ CLI mode | Direct command execution without the menu |

### System Requirements

- Python **3.10+**
- `bash`, `curl`, `jq` — Ubuntu install: `sudo apt install curl jq`
- Cloudflare account with **Zone ID** and an **API Token** with DNS Edit permission

### Installation & Usage

#### 1. Clone & set permissions

```bash
git clone https://github.com/your-user/cf-auto-ddns.git
cd cf-auto-ddns
chmod +x auto-ddns-cloudflare.py
```

#### 2. Interactive menu

```bash
python3 auto-ddns-cloudflare.py
```

#### 3. CLI mode (no menu)

```bash
python3 auto-ddns-cloudflare.py configure    # Enter configuration
python3 auto-ddns-cloudflare.py generate     # Generate bash script
python3 auto-ddns-cloudflare.py test         # Dry-run test
python3 auto-ddns-cloudflare.py cron-add     # Add to crontab
python3 auto-ddns-cloudflare.py cron-list    # View crontab
python3 auto-ddns-cloudflare.py cron-remove  # Remove from crontab
python3 auto-ddns-cloudflare.py logs         # View recent logs
python3 auto-ddns-cloudflare.py show         # Show current config
```

### DNS Record Format

Each record follows the format: `record_name:proxied:ttl:type`

```
sub.example.com:true:120:A      # Proxied, TTL 120s, IPv4
api.example.com:false:300:A     # Not proxied, TTL 300s, IPv4
ipv6.example.com:false:120:AAAA # IPv6, not proxied
```

### Directory Structure

```
cf-auto-ddns/
├── auto-ddns-cloudflare.py   ← Main tool (v2.0)
├── cf-ddns.sh                ← Original reference script (v1.0, DO NOT EDIT)
├── data.json                 ← Config file (auto-generated after configure)
├── cf-ddns-run.sh            ← Auto-generated bash script
├── log/
│   ├── ddns-20261102.log     ← 3-day log groups
│   └── ddns-20261105.log
└── README.md
```

### Log System

- Logs are stored in the `log/` directory next to `auto-ddns-cloudflare.py`
- File name: `ddns-YYYYMMDD.log` — date is the start of the 3-day group
- After every 3 days of activity, a new log file is created automatically (both the Python script and the generated Bash script follow the same rotation logic)
- Log levels: `INFO`, `OK`, `WARN`, `ERROR`

### Getting Zone ID & API Token

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. **Zone ID**: Domain overview page → right column → *Zone ID*
3. **API Token**: `Profile > API Tokens > Create Token` → select *Edit zone DNS* template

---

## ⚠️ Security Warnings

> **CAUTION — Protect `data.json`**  
> This file stores your Cloudflare API Token in plain text.  
> Restrict file permissions:
> ```bash
> chmod 600 data.json
> chmod 700 cf-ddns-run.sh
> ```

> **WARNING**
> - **Never commit `data.json`** to a public git repository.
> - Add to `.gitignore`:
>   ```
>   data.json
>   log/
>   cf-ddns-run.sh
>   ```
> - The API Token should have minimal scope: **Zone > DNS > Edit** for the specific zone only.

> **NOTE**  
> The generated `.sh` script contains the API Token in plain text. Set `chmod 700` on that file as well.

---

## Credits

| Role | Info |
|------|------|
| Original script (v1.0) | [`cf-ddns.sh`](./cf-ddns.sh) — Bash-based Cloudflare DDNS updater |
| Python rewrite (v2.0)  | `auto-ddns-cloudflare.py` — Full-featured Python tool |
| Cloudflare API | [api.cloudflare.com](https://api.cloudflare.com/client/v4/) |
| IP detection sources | [icanhazip.com](https://ipv4.icanhazip.com), [ipify.org](https://api.ipify.org), [ifconfig.me](https://ifconfig.me/ip) |

## License

MIT License — free to use, modify and distribute with attribution.
