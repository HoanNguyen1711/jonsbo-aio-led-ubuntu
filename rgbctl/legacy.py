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

    # chỉ xoá symlink trỏ về rgbctl.sh của git clone, không đụng file khác trùng tên
    link = os.path.join(HOME, ".local/bin/rgbctl")
    if os.path.islink(link) and os.readlink(link).endswith("rgbctl.sh"):
        os.remove(link)
        removed.append(link)

    for rel in FILES:
        path = os.path.join(HOME, rel)
        if os.path.isfile(path) and _is_ours(path):
            os.remove(path)
            removed.append(path)
    return removed


def _is_ours(path):
    if path.endswith(".svg"):
        return True
    with open(path, errors="replace") as f:
        return "rgbctl" in f.read()
