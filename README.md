# cf-auto-ddns
Tự động cập nhật địa chỉ IP WAN (tĩnh) lên cloudflare.

# cf-ddns.sh - Tự động cập nhật DNS record trên Cloudflare theo IP WAN hiện tại
# Hỗ trợ bật/tắt proxy (orange cloud) RIÊNG cho từng record trong cùng 1 file.
#
# Cách dùng:
#   1. Điền ZONE_ID, API_TOKEN bên dưới (hoặc export biến môi trường trước khi chạy)
#   2. Khai báo từng record trong DNS_RECORDS theo định dạng "ten_record:true|false"
#   3. chmod +x cf-ddns.sh
#   4. Chạy thử: ./cf-ddns.sh
#   5. Đặt cron để tự động chạy định kỳ (xem hướng dẫn cuối file)

# ====== HƯỚNG DẪN ĐẶT CRON (chạy mỗi 5 phút) ======
# crontab -e
# */5 * * * * /path/to/cf-ddns.sh >> /dev/null 2>&1
#
# Log chi tiết được ghi tại: ~/.cf-ddns/cf-ddns.log
