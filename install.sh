#!/bin/sh
# Cài từ source: build gói .deb rồi cài bằng apt (apt tự kéo các gói phụ thuộc).
# Cách khác: tải file .deb ở trang Releases trên GitHub rồi `sudo apt install ./rgbctl_*.deb`.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "→ build gói .deb"
DEB="$("$DIR/build-deb.sh")"

echo "→ cài $DEB (cần sudo)"
sudo apt-get install -y --reinstall "$DEB"

echo "→ dọn bản cài kiểu cũ trong home (nếu có)"
/usr/bin/rgbctl uninstall-legacy

echo "→ khởi động daemon và tray cho phiên hiện tại"
systemctl --user daemon-reload
systemctl --user restart rgbctl-daemon.service
pkill -u "$(id -u)" -f "m rgbctl tray$" 2>/dev/null || true
setsid -f /usr/bin/rgbctl tray >/dev/null 2>&1

echo "Xong. Thử: rgbctl info"
