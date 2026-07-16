#!/bin/bash
#
# cf-ddns.sh - Tự động cập nhật DNS record trên Cloudflare theo IP WAN hiện tại
# Hỗ trợ bật/tắt proxy (orange cloud) RIÊNG cho từng record trong cùng 1 file.
#
# Cách dùng:
#   1. Điền ZONE_ID, API_TOKEN bên dưới (hoặc export biến môi trường trước khi chạy)
#   2. Khai báo từng record trong DNS_RECORDS theo định dạng "ten_record:true|false"
#   3. chmod +x cf-ddns.sh
#   4. Chạy thử: ./cf-ddns.sh
#   5. Đặt cron để tự động chạy định kỳ (xem hướng dẫn cuối file)

set -uo pipefail

# ====== CẤU HÌNH ======
# Điền Zone ID và API token vào đây, lấy trên cloudflare
ZONE_ID="TOKEN-ZONE-ID"
API_TOKEN="API-TOKEN"

# Danh sách record cần cập nhật, định dạng: "ten_record:proxied(true|false)"
DNS_RECORDS=(
    "record1:true"
    "record2:true"
    "record3:true"
    "record4:false"
)

TTL="${TTL:-120}"
RECORD_TYPE="A"                   # dùng "AAAA" nếu muốn cập nhật IPv6

# Nơi lưu log
STATE_DIR="${STATE_DIR:-$HOME/.cf-ddns}"
LOG_FILE="${LOG_FILE:-$STATE_DIR/cf-ddns.log}"

mkdir -p "$STATE_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# ====== KIỂM TRA CÔNG CỤ CẦN THIẾT ======
for cmd in curl jq; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        log "LỖI: thiếu lệnh '$cmd'. Cài bằng: sudo apt install $cmd"
        exit 1
    fi
done

if [[ "$ZONE_ID" == "user-zone-id" || "$API_TOKEN" == "user-API-token" ]]; then
    log "LỖI: chưa cấu hình ZONE_ID / API_TOKEN. Hãy sửa trong script hoặc export biến môi trường."
    exit 1
fi

if [[ ${#DNS_RECORDS[@]} -eq 0 ]]; then
    log "LỖI: DNS_RECORDS đang rỗng, chưa khai báo bản ghi nào."
    exit 1
fi

# ====== LẤY IP HIỆN TẠI (thử nhiều nguồn phòng khi 1 nguồn sập) ======
get_current_ip() {
    local ip
    for url in "https://ipv4.icanhazip.com" "https://api.ipify.org" "https://ifconfig.me/ip"; do
        ip=$(curl -s -4 --max-time 5 "$url" | tr -d '[:space:]')
        if [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
            echo "$ip"
            return 0
        fi
    done
    return 1
}

CURRENT_IP=$(get_current_ip)
if [[ -z "$CURRENT_IP" ]]; then
    log "LỖI: không lấy được IP hiện tại từ bất kỳ nguồn nào."
    exit 1
fi

EXIT_CODE=0

for ENTRY in "${DNS_RECORDS[@]}"; do
    DNS_RECORD="${ENTRY%%:*}"
    PROXIED="${ENTRY##*:}"

    if [[ "$PROXIED" != "true" && "$PROXIED" != "false" ]]; then
        log "[$DNS_RECORD] LỖI: giá trị proxied không hợp lệ ('$PROXIED'). Phải là true hoặc false. Bỏ qua."
        EXIT_CODE=1
        continue
    fi

    # ====== LẤY RECORD ID + GIÁ TRỊ IP HIỆN TẠI TRÊN CLOUDFLARE ======
    LOOKUP_RESPONSE=$(curl -s -X GET \
        "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=$RECORD_TYPE&name=$DNS_RECORD" \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json")

    LOOKUP_SUCCESS=$(echo "$LOOKUP_RESPONSE" | jq -r '.success')
    if [[ "$LOOKUP_SUCCESS" != "true" ]]; then
        log "[$DNS_RECORD] LỖI khi tra cứu record: $(echo "$LOOKUP_RESPONSE" | jq -c '.errors')"
        EXIT_CODE=1
        continue
    fi

    RECORD_ID=$(echo "$LOOKUP_RESPONSE" | jq -r '.result[0].id')
    REMOTE_IP=$(echo "$LOOKUP_RESPONSE" | jq -r '.result[0].content')
    REMOTE_PROXIED=$(echo "$LOOKUP_RESPONSE" | jq -r '.result[0].proxied')

    if [[ "$RECORD_ID" == "null" || -z "$RECORD_ID" ]]; then
        log "[$DNS_RECORD] LỖI: không tìm thấy DNS record (type $RECORD_TYPE) trong zone."
        EXIT_CODE=1
        continue
    fi

    # Cập nhật nếu IP đổi HOẶC trạng thái proxy trên Cloudflare khác với cấu hình mong muốn
    if [[ "$CURRENT_IP" == "$REMOTE_IP" && "$PROXIED" == "$REMOTE_PROXIED" ]]; then
        log "[$DNS_RECORD] Không đổi (IP: $CURRENT_IP, proxied: $PROXIED). Bỏ qua."
        continue
    fi

    log "[$DNS_RECORD] Cập nhật: IP $REMOTE_IP -> $CURRENT_IP, proxied $REMOTE_PROXIED -> $PROXIED"

    # ====== CẬP NHẬT RECORD ======
    UPDATE_RESPONSE=$(curl -s -X PUT \
        "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        --data "{\"type\":\"$RECORD_TYPE\",\"name\":\"$DNS_RECORD\",\"content\":\"$CURRENT_IP\",\"ttl\":$TTL,\"proxied\":$PROXIED}")

    UPDATE_SUCCESS=$(echo "$UPDATE_RESPONSE" | jq -r '.success')

    if [[ "$UPDATE_SUCCESS" == "true" ]]; then
        log "[$DNS_RECORD] Cập nhật thành công -> $CURRENT_IP (proxied: $PROXIED)"
    else
        log "[$DNS_RECORD] LỖI khi cập nhật: $(echo "$UPDATE_RESPONSE" | jq -c '.errors')"
        EXIT_CODE=1
    fi
done

exit $EXIT_CODE

# ====== HƯỚNG DẪN ĐẶT CRON (chạy mỗi 5 phút) ======
# crontab -e
# */5 * * * * /path/to/cf-ddns.sh >> /dev/null 2>&1
#
# Log chi tiết được ghi tại: ~/.cf-ddns/cf-ddns.log
