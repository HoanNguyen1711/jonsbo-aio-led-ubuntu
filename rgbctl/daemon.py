"""Tiến trình nền `rgbctl daemon`:

- gửi nhiệt độ CPU lên màn hình AIO (5 Hz) khi config `aio.enabled` bật;
- chạy các hiệu ứng phần mềm (thở / nháy / đổi màu, xem effects.py) ~30 khung hình/giây
  cho fan/AIO/LED main (lệnh "tĩnh + màu" của IT5711), RAM (chế độ direct của Corsair) và
  card Colorful, tất cả cùng một đồng hồ nên khớp nhau.

Hiệu ứng tĩnh / cầu vồng / tắt vẫn do chip tự chạy; daemon không đụng tới các vùng đó.
"""
import fcntl
import glob
import os
import subprocess
import sys
import time

from . import aio_display, colorful_gpu, core, corsair_ram, effects, fusion

FPS = 30
# Driver NVIDIA chờ bus I2C bằng cách chạy CPU suốt lúc truyền (~3.3 ms CPU mỗi lệnh):
# 30 lần/giây tốn ~10% một nhân. Card chỉ có một vùng màu nên 12 lần/giây là đủ mượt.
GPU_FPS = 12
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


def _spawn(subcommand):
    """Chạy `rgbctl <subcommand>` tách hẳn khỏi tiến trình hiện tại (đóng GUI vẫn chạy)."""
    subprocess.Popen(
        [sys.executable, "-m", "rgbctl", subcommand],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        start_new_session=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def start_background():
    """Chạy daemon nếu chưa chạy. Trả về lỗi (str) hoặc None."""
    if not is_running():
        _spawn("daemon")
    return None


def start_tray():
    """Bật tray nếu chưa chạy (mở app từ menu thì tray cũng hiện)."""
    if not is_locked("tray"):
        _spawn("tray")


def set_aio_enabled(on):
    """Bật/tắt màn hình AIO. Daemon vẫn chạy (còn lo hiệu ứng), chỉ ngừng gửi nhiệt độ."""
    aio_display.save_settings(enabled=on)
    dev = aio_display.find_hidraw()
    if on and dev and not os.access(dev, os.W_OK):
        return f"Không có quyền ghi {dev}. Chạy ./install.sh trước."
    return start_background() if on else None


def _lock_path(name):
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), f"rgbctl-{name}.lock")


def single_instance(name):
    """Giữ khoá `name` suốt đời tiến trình; False nếu đã có tiến trình khác giữ."""
    fd = os.open(_lock_path(name), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    return True  # cố ý không đóng fd: khoá nhả khi tiến trình thoát


def is_locked(name):
    """Có tiến trình nào đang giữ khoá `name` không."""
    fd = os.open(_lock_path(name), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except BlockingIOError:
        return True
    finally:
        os.close(fd)


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
    if not single_instance("daemon"):
        return 0  # service và tray cùng khởi động lúc đăng nhập: chỉ một daemon chạy
    temp_path = aio_display.cpu_temp_path()
    mb = _Lazy(fusion.Fusion2)
    ram = _Lazy(corsair_ram.CorsairRAM)
    gpu = _Lazy(colorful_gpu.ColorfulGPU)
    aio = _Lazy(_AioDev)

    cfg_mtime = None
    plan = {}  # vùng -> state hiệu ứng phần mềm ("ram" là RAM)
    builtin_ok = False  # đã bảo đảm các header ARGB chạy hiệu ứng của chip (không direct)
    last = {}  # vùng -> màu đã gửi, chỉ gửi khi đổi
    aio_enabled, aio_next = True, 0.0
    gpu_next = 0.0

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
            last = {}

        # hiệu ứng phần mềm
        if plan:
            t = time.time()  # đồng hồ chung cho mọi thiết bị
            fusion_zones = [z for z in plan if z in fusion.ZONES]
            if fusion_zones and (dev := mb.get()):
                try:
                    if not builtin_ok:
                        # tắt chế độ direct nếu bản cũ để lại, để lệnh hiệu ứng có tác dụng
                        dev.set_direct_headers([])
                        builtin_ok = True
                    # Tô bằng lệnh "tĩnh + màu" cho mọi vùng trong một lượt (~25 ms). Chế độ direct
                    # cần 4 gói mỗi header (~93 ms/khung) và đổi qua lại với hiệu ứng của chip làm
                    # đèn chớp lúc chuyển từ cầu vồng sang.
                    groups = {}
                    for z in fusion_zones:
                        st = plan[z]
                        c = effects.color_at(t, st["mode"], core.parse_color(st["color"]),
                                             st["speed"], st["brightness"])
                        if last.get(z) != c:
                            groups.setdefault(c, []).append(z)
                    for c, zones in groups.items():
                        dev.send_effects(zones, fusion.EFFECT_STATIC, c)
                        for z in zones:
                            last[z] = c
                except OSError:
                    mb.fail()
                    builtin_ok = False
            gpu_due = frame_start >= gpu_next
            if gpu_due:
                gpu_next = frame_start + 1 / GPU_FPS
            for name, lazy, send in (("ram", ram, "set_direct"), ("gpu", gpu, "set_color")):
                if name == "gpu" and not gpu_due:
                    continue
                if name in plan and (dev := lazy.get()):
                    st = plan[name]
                    c = effects.color_at(t, st["mode"], core.parse_color(st["color"]),
                                         st["speed"], st["brightness"])
                    if last.get(name) != c:
                        try:
                            getattr(dev, send)(c)
                            last[name] = c
                        except OSError:
                            lazy.fail()

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
