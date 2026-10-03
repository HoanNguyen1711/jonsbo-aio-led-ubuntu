"""Tiến trình nền `rgbctl daemon`:

- gửi nhiệt độ CPU lên màn hình AIO (5 Hz) khi config `aio.enabled` bật;
- chạy các hiệu ứng phần mềm (thở / nháy / đổi màu, xem effects.py) ~30 khung hình/giây
  cho fan/AIO (chế độ direct của IT5711) và RAM (chế độ direct của Corsair), tất cả cùng
  một đồng hồ nên khớp nhau.

Hiệu ứng tĩnh / cầu vồng / tắt vẫn do chip tự chạy; daemon không đụng tới các vùng đó.
"""
import fcntl
import glob
import os
import subprocess
import sys
import time

from . import aio_display, core, corsair_ram, effects, fusion

FPS = 30
AIO_INTERVAL = 0.2
RETRY = 10  # giây, mở lại thiết bị bị lỗi


# --- quản lý tiến trình ------------------------------------------------------
def is_running():
    """PID của daemon đang chạy (không tính chính mình), hoặc None."""
    for path in glob.glob("/proc/[0-9]*/cmdline"):
        pid = int(path.split("/")[2])
        if pid == os.getpid():
            continue
        try:
            with open(path, "rb") as f:
                args = f.read().split(b"\0")
        except OSError:
            continue
        # "aio-temp" là tên cũ, service cài trước đây vẫn gọi tên này
        if any(b"rgbctl" in a for a in args) and (b"daemon" in args or b"aio-temp" in args):
            return pid
    return None


def start_background():
    """Chạy daemon tách khỏi tiến trình hiện tại nếu chưa chạy. Trả về lỗi (str) hoặc None."""
    if is_running():
        return None
    subprocess.Popen(
        [sys.executable, "-m", "rgbctl", "daemon"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        start_new_session=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return None


def set_aio_enabled(on):
    """Bật/tắt màn hình AIO. Daemon vẫn chạy (còn lo hiệu ứng), chỉ ngừng gửi nhiệt độ."""
    aio_display.save_settings(enabled=on)
    dev = aio_display.find_hidraw()
    if on and dev and not os.access(dev, os.W_OK):
        return f"Không có quyền ghi {dev}. Chạy ./install.sh trước."
    return start_background() if on else None


def _single_instance():
    """Giữ khoá suốt đời tiến trình; False nếu đã có daemon khác (service + tray cùng khởi động)."""
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    fd = os.open(os.path.join(runtime, "rgbctl-daemon.lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    return True


# --- thiết bị, tự mở lại khi lỗi --------------------------------------------
class _Lazy:
    """Mở thiết bị khi cần; lỗi thì đóng và chờ RETRY giây mới thử lại."""

    def __init__(self, factory):
        self.factory = factory
        self.dev = None
        self.failed_at = -RETRY

    def get(self):
        if self.dev is None and time.monotonic() - self.failed_at >= RETRY:
            try:
                self.dev = self.factory()
            except Exception:  # noqa: BLE001 - thiết bị chưa sẵn sàng, thử lại sau
                self.failed_at = time.monotonic()
        return self.dev

    def fail(self):
        if self.dev is not None:
            try:
                self.dev.close()
            except OSError:
                pass
        self.dev = None
        self.failed_at = time.monotonic()


class _AioDev:
    def __init__(self):
        dev = aio_display.find_hidraw()
        if not dev:
            raise RuntimeError("không thấy màn hình AIO")
        self.fd = os.open(dev, os.O_WRONLY)

    def close(self):
        os.close(self.fd)


# --- vòng lặp chính ----------------------------------------------------------
def run():
    if not _single_instance():
        return 0
    temp_path = aio_display.cpu_temp_path()
    mb = _Lazy(fusion.Fusion2)
    ram = _Lazy(corsair_ram.CorsairRAM)
    aio = _Lazy(_AioDev)

    cfg_mtime = None
    plan = {}  # vùng -> state hiệu ứng phần mềm ("ram" là RAM)
    direct_set = None  # bộ header ARGB đã chuyển sang direct
    last = {}  # vùng -> màu đã gửi, chỉ gửi khi đổi
    aio_enabled, aio_next = True, 0.0

    while True:
        frame_start = time.monotonic()

        # đọc lại config khi file đổi (GUI/tray/CLI ghi vào)
        try:
            mtime = os.stat(core.CONFIG_PATH).st_mtime_ns
        except OSError:
            mtime = None
        if mtime != cfg_mtime:
            cfg_mtime = mtime
            cfg = core.load_config()
            plan = core.software_plan(cfg)
            aio_enabled = {**aio_display.DEFAULT, **cfg.get("aio", {})}["enabled"]
            direct_set, last = None, {}

        # hiệu ứng phần mềm
        if plan:
            t = time.time()  # đồng hồ chung cho mọi thiết bị
            fusion_zones = [z for z in plan if z != "ram"]
            if fusion_zones and (dev := mb.get()):
                try:
                    argb = sorted(z for z in fusion_zones if fusion.ZONES[z][1])
                    if direct_set != argb:
                        dev.set_direct_headers(argb)
                        direct_set, last = argb, {}
                    for z in fusion_zones:
                        st = plan[z]
                        c = effects.color_at(t, st["mode"], core.parse_color(st["color"]),
                                             st["speed"], st["brightness"])
                        if last.get(z) != c:
                            if z in argb:
                                dev.set_direct_color(z, c)
                            else:
                                dev.send_effects([z], fusion.EFFECT_STATIC, c)
                            last[z] = c
                except OSError:
                    mb.fail()
                    direct_set = None
            if "ram" in plan and (dev := ram.get()):
                st = plan["ram"]
                c = effects.color_at(t, st["mode"], core.parse_color(st["color"]),
                                     st["speed"], st["brightness"])
                if last.get("ram") != c:
                    try:
                        dev.set_direct(c)
                        last["ram"] = c
                    except OSError:
                        ram.fail()

        # màn hình AIO
        if aio_enabled and frame_start >= aio_next and (h := aio.get()):
            try:
                aio_display.send(h.fd, aio_display.cpu_temp(temp_path))
            except OSError:
                aio.fail()
            aio_next = frame_start + AIO_INTERVAL

        # không có hiệu ứng phần mềm thì ngủ lâu hơn cho nhẹ máy
        interval = 1 / FPS if plan else AIO_INTERVAL
        time.sleep(max(0.0, interval - (time.monotonic() - frame_start)))
