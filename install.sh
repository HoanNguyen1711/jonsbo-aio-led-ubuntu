#!/bin/sh
# Cài rgbctl cho user hiện tại. Chỉ bước udev cần sudo.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "→ gói cho icon tray (cần sudo)"
sudo apt-get install -y gir1.2-ayatanaappindicator3-0.1

echo "→ udev rule (cần sudo)"
sudo install -m 644 "$DIR/60-rgbctl.rules" /etc/udev/rules.d/60-rgbctl.rules
echo i2c-dev | sudo tee /etc/modules-load.d/rgbctl.conf >/dev/null
sudo modprobe i2c-dev
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw --subsystem-match=i2c-dev

echo "→ lệnh ~/.local/bin/rgbctl"
mkdir -p ~/.local/bin
ln -sf "$DIR/rgbctl.sh" ~/.local/bin/rgbctl

echo "→ icon + mục trong menu ứng dụng"
ICONS=~/.local/share/icons/hicolor
mkdir -p "$ICONS/scalable/apps" "$ICONS/symbolic/apps" ~/.local/share/applications
cp "$DIR/icons/rgbctl.svg" "$ICONS/scalable/apps/rgbctl.svg"
cp "$DIR/icons/rgbctl-symbolic.svg" "$ICONS/symbolic/apps/rgbctl-symbolic.svg"
gtk-update-icon-cache -q -t "$ICONS" 2>/dev/null || true
rm -f ~/.local/share/applications/rgbctl.desktop
# tên file trùng app ID của GUI để GNOME gắn đúng icon cho cửa sổ
cat > ~/.local/share/applications/dev.hoan.rgbctl.desktop <<DESK
[Desktop Entry]
Type=Application
Name=RGB Control
Comment=Điều khiển LED fan, AIO và RAM
Exec=$HOME/.local/bin/rgbctl gui
Icon=rgbctl
Categories=Utility;Settings;
DESK

echo "→ icon tray, tự chạy khi đăng nhập (áp dụng lại config đã lưu)"
mkdir -p ~/.config/autostart
rm -f ~/.config/autostart/rgbctl-apply.desktop
cat > ~/.config/autostart/rgbctl-tray.desktop <<DESK
[Desktop Entry]
Type=Application
Name=RGB Control (tray)
Exec=$HOME/.local/bin/rgbctl tray
NoDisplay=true
X-GNOME-Autostart-enabled=true
DESK

echo "→ hiển thị nhiệt độ CPU lên màn hình AIO (systemd user service)"
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/rgbctl-aio-temp.service <<UNIT
[Unit]
Description=Nhiệt độ CPU lên màn hình AIO Jonsbo

[Service]
ExecStart=$HOME/.local/bin/rgbctl aio-temp
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now rgbctl-aio-temp.service

echo "Xong. Thử: rgbctl info   (icon tray xuất hiện từ lần đăng nhập sau, hoặc chạy: rgbctl tray &)"
