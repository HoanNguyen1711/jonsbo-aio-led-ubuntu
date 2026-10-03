"""Màn hình nhiệt độ trên block AIO Jonsbo (USB 5131:2007, tên "FBB").

Màn hình 2 chữ số 7 đoạn, chữ "CPU"/"JONSBO" in cố định, không tự đo: phải gửi
nhiệt độ CPU liên tục (5 Hz).
Protocol theo github.com/danieyal/jonsbolite (reverse-engineering/PROTOCOL.md):
payload 64 byte, offset 0..2 = 00 01 02, 3 = nhiệt độ nguyên, 4 = phần trăm, 5 = đơn vị (0 = °C).
Đã thử byte đơn vị (5) và chế độ hiển thị (40, 41): màn hình này bỏ qua, chỉ hiện ô 3.
"""
import fcntl
import glob
import os
import signal
import subprocess
import sys
import time

from . import core

HID_ID = "HID_ID=0003:00005131:00002007"
INTERVAL = 0.2

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


def is_running():
    """PID của tiến trình `rgbctl aio-temp` đang chạy (không tính chính mình), hoặc None."""
    for path in glob.glob("/proc/[0-9]*/cmdline"):
        pid = int(path.split("/")[2])
        if pid == os.getpid():
            continue
        try:
            with open(path, "rb") as f:
                args = f.read().split(b"\0")
        except OSError:
            continue
        if b"aio-temp" in args and any(b"rgbctl" in a for a in args):
            return pid
    return None


def start_background():
    """Chạy `rgbctl aio-temp` tách khỏi tiến trình hiện tại. Trả về lỗi (str) hoặc None."""
    dev = find_hidraw()
    if not dev:
        return "Không thấy màn hình AIO"
    if not os.access(dev, os.W_OK):
        return f"Không có quyền ghi {dev}. Chạy ./install.sh trước."
    # tách hẳn để đóng GUI/tray vẫn tiếp tục chạy
    subprocess.Popen(
        [sys.executable, "-m", "rgbctl", "aio-temp"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        start_new_session=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return None


def set_enabled(on):
    """Bật/tắt hiển thị: lưu config và chạy/dừng tiến trình gửi. Trả về lỗi hoặc None."""
    save_settings(enabled=on)
    pid = is_running()
    if on and not pid:
        return start_background()
    if not on and pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except PermissionError:
            pass  # tiến trình của user khác: nó tự ngừng gửi vì đọc enabled=false
    return None


def _single_instance():
    """Giữ khoá suốt đời tiến trình; False nếu đã có một `aio-temp` khác đang chạy."""
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    fd = os.open(os.path.join(runtime, "rgbctl-aio.lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    return True


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


def run(once=False):
    """Gửi nhiệt độ CPU lên màn hình AIO mỗi 0.2s khi config `aio.enabled` bật
    (chạy mãi nếu once=False)."""
    temp_path = cpu_temp_path()
    if not once and not _single_instance():
        return None  # service và tray cùng khởi động lúc đăng nhập: chỉ một cái chạy
    settings, settings_at = get_settings(), time.monotonic()
    while True:
        dev = find_hidraw()
        if not dev:
            if once:
                raise RuntimeError("Không tìm thấy màn hình AIO Jonsbo (5131:2007)")
            time.sleep(5)  # chờ thiết bị xuất hiện lại (vd sau khi sleep/resume)
            continue
        fd = os.open(dev, os.O_WRONLY)
        try:
            while True:
                # đọc lại config mỗi giây để GUI đổi được mà không cần khởi động lại
                if time.monotonic() - settings_at > 1:
                    settings, settings_at = get_settings(), time.monotonic()
                value = cpu_temp(temp_path)
                if settings["enabled"] or once:
                    send(fd, value)
                if once:
                    return value
                time.sleep(INTERVAL)
        except OSError:
            if once:
                raise
            time.sleep(1)  # thiết bị bị rút/reset: mở lại
        finally:
            os.close(fd)
