"""Dọn bản cài kiểu cũ (install.sh tạo symlink vào git clone) trong thư mục home.

Phần trong /etc (udev rule, modules-load) do postinst của gói .deb dọn.
"""
import os
import subprocess

HOME = os.path.expanduser("~")

FILES = [
    ".local/share/applications/dev.hoan.rgbctl.desktop",
    ".local/share/applications/rgbctl.desktop",
    ".local/share/icons/hicolor/scalable/apps/rgbctl.svg",
    ".local/share/icons/hicolor/symbolic/apps/rgbctl-symbolic.svg",
    ".config/autostart/rgbctl-tray.desktop",
    ".config/autostart/rgbctl-apply.desktop",
]
SERVICES = ["rgbctl-daemon.service", "rgbctl-aio-temp.service"]


def cleanup():
    """Trả về danh sách đường dẫn đã xoá."""
    removed = []
    for name in SERVICES:
        path = os.path.join(HOME, ".config/systemd/user", name)
        if os.path.exists(path):
            subprocess.run(["systemctl", "--user", "disable", "--now", name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.remove(path)
            removed.append(path)
    if any(p.endswith(".service") for p in removed):
        subprocess.run(["systemctl", "--user", "daemon-reload"], stderr=subprocess.DEVNULL)

    # Symlink cũ trỏ về rgbctl.sh của git clone: trỏ lại sang /usr/bin/rgbctl thay vì xoá.
    # GNOME Shell đang chạy vẫn nhớ Exec=~/.local/bin/rgbctl của .desktop cũ tới khi đăng
    # xuất; xoá đi thì bấm icon báo "not found in $PATH".
    link = os.path.join(HOME, ".local/bin/rgbctl")
    if os.path.islink(link) and os.readlink(link).endswith("rgbctl.sh"):
        os.remove(link)
        os.symlink("/usr/bin/rgbctl", link)
        removed.append(f"{link} (giờ trỏ tới /usr/bin/rgbctl)")

    for rel in FILES:
        path = os.path.join(HOME, rel)
        if os.path.isfile(path) and _is_ours(path):
            os.remove(path)
            removed.append(path)

    if removed:
        # GNOME Shell và GTK giữ cache: không làm mới thì menu vẫn chạy
        # ~/.local/bin/rgbctl đã xoá ("not found in $PATH") và tìm icon cũ
        for cmd in (["update-desktop-database", os.path.join(HOME, ".local/share/applications")],
                    ["gtk-update-icon-cache", "-q", "-f", "-t",
                     os.path.join(HOME, ".local/share/icons/hicolor")]):
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return removed


def _is_ours(path):
    if path.endswith(".svg"):
        return True
    with open(path, errors="replace") as f:
        return "rgbctl" in f.read()
