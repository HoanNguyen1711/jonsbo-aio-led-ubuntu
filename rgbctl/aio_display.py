"""Màn hình nhiệt độ trên block AIO Jonsbo (USB 5131:2007, tên "FBB").

Màn hình 2 chữ số 7 đoạn, chữ "CPU"/"JONSBO" in cố định, không tự đo: phải gửi
nhiệt độ CPU liên tục (5 Hz).
Protocol theo github.com/danieyal/jonsbolite (reverse-engineering/PROTOCOL.md):
payload 64 byte, offset 0..2 = 00 01 02, 3 = nhiệt độ nguyên, 4 = phần trăm, 5 = đơn vị (0 = °C).
Đã thử byte đơn vị (5) và chế độ hiển thị (40, 41): màn hình này bỏ qua, chỉ hiện ô 3.
"""
import glob
import os

from . import core

HID_ID = "HID_ID=0003:00005131:00002007"
DEFAULT = {"enabled": True}


def find_hidraw():
    # VID:PID 5131:2007 bị dùng chung bởi nhiều thiết bị rẻ tiền, nên kiểm tra cả tên
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(f"{path}/device/uevent") as f:
                uevent = f.read()
        except OSError:
            continue
        if HID_ID in uevent and "HID_NAME=FBB" in uevent:
            return "/dev/" + os.path.basename(path)
    return None


def get_settings():
    return {**DEFAULT, **core.load_config().get("aio", {})}


def save_settings(**changes):
    cfg = core.load_config()
    merged = {**DEFAULT, **cfg.get("aio", {}), **changes}
    cfg["aio"] = {k: merged[k] for k in DEFAULT}  # bỏ khoá cũ không còn dùng
    core.save_config(cfg)


def cpu_temp_path():
    """Tctl của Ryzen (k10temp)."""
    for path in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        try:
            with open(f"{path}/name") as f:
                if f.read().strip() == "k10temp":
                    return f"{path}/temp1_input"
        except OSError:
            continue
    raise RuntimeError("Không tìm thấy cảm biến k10temp")


def cpu_temp(path):
    with open(path) as f:
        return int(f.read()) / 1000


def send(fd, value):
    value = max(0.0, min(99.99, value))
    p = bytearray(64)
    p[1], p[2] = 0x01, 0x02
    p[3], p[4] = int(value), int(value * 100) % 100
    # Thiết bị không dùng report ID: byte 0x00 đầu bị kernel bỏ, thiết bị nhận đúng 64 byte p
    os.write(fd, b"\0" + bytes(p))


def send_once():
    """Gửi nhiệt độ CPU hiện tại một lần (để thử). Trả về nhiệt độ đã gửi."""
    dev = find_hidraw()
    if not dev:
        raise RuntimeError("Không tìm thấy màn hình AIO Jonsbo (5131:2007)")
    value = cpu_temp(cpu_temp_path())
    fd = os.open(dev, os.O_WRONLY)
    try:
        send(fd, value)
    finally:
        os.close(fd)
    return value
