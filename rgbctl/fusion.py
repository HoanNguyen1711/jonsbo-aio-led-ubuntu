"""Gigabyte RGB Fusion 2 (ITE IT5711, USB 048d:5711) qua hidraw.

Điều khiển các header ARGB trên main (fan + AIO Jonsbo cắm vào đây)
và LED onboard. Protocol tham khảo từ OpenRGB (GigabyteRGBFusion2USBController).
"""
import fcntl
import glob
import os
import struct
import time

VID, PID = 0x048D, 0x5711
REPORT_ID = 0xCC
PKT = 64

# Mã hiệu ứng phần cứng
EFFECT_STATIC = 1
EFFECT_PULSE = 2
EFFECT_FLASH = 3
EFFECT_CYCLE = 4
EFFECT_WAVE = 6
EFFECT_WAVE4 = 12  # cầu vồng chạy trên dải ARGB; EFFECT_WAVE (6) làm tắt đèn trên IT5711 này

# Vùng trên B850M GAMING X WIFI6E (layout it5711_9 trong OpenRGB)
# tên -> (chỉ số LED, bit header ARGB cho lệnh 0x32 hoặc None)
ZONES = {
    "argb1": (5, 0x01),
    "argb2": (6, 0x02),
    "argb3": (7, 0x08),
    "chipset": (2, None),
    "led_c": (4, None),
}
ALL_ZONES = list(ZONES)

LED_COUNT_STEPS = [32, 64, 256, 512, 1024]

# header gửi màu từng LED cho argb1..3 (chế độ direct)
DIRECT_HEADERS = [0x58, 0x59, 0x62]


def _ioc(direction, nr, size):
    return (direction << 30) | (size << 16) | (ord("H") << 8) | nr


HIDIOCSFEATURE = _ioc(3, 0x06, PKT)
HIDIOCGFEATURE = _ioc(3, 0x07, PKT)


def find_hidraw():
    """Tìm interface vendor (usage page 0xFF89) của chip ITE 5711."""
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(f"{path}/device/uevent") as f:
                uevent = f.read()
            with open(f"{path}/device/report_descriptor", "rb") as f:
                desc = f.read(3)
        except OSError:
            continue
        if f"HID_ID=0003:{VID:08X}:{PID:08X}" in uevent and desc == b"\x06\x89\xff":
            return "/dev/" + os.path.basename(path)
    return None


class Fusion2:
    def __init__(self, dev=None):
        dev = dev or find_hidraw()
        if not dev:
            raise RuntimeError("Không tìm thấy Gigabyte RGB Fusion 2 (048d:5711)")
        self.dev = dev
        self.fd = os.open(dev, os.O_RDWR)
        self.info = self._read_info()
        # tắt chế độ Windows Dynamic Lighting (LampArray) nếu chip hỗ trợ
        if self.info["flags"] & 0x02:
            self._cmd(0x48, 0)
        self._cmd(0x31, 0)  # tắt chế độ nháy theo nhạc

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- tầng thấp ---------------------------------------------------
    def _send(self, buf):
        buf = bytes(buf).ljust(PKT, b"\0")
        fcntl.ioctl(self.fd, HIDIOCSFEATURE, buf)

    def _cmd(self, a, b=0, c=0):
        self._send(bytes([REPORT_ID, a, b, c]))

    def _get(self, cmd):
        self._cmd(cmd)
        buf = bytearray(PKT)
        buf[0] = REPORT_ID
        fcntl.ioctl(self.fd, HIDIOCGFEATURE, buf)
        return buf

    def _read_info(self):
        r = self._get(0x60)
        (_, product, _devnum, _detect, fw, a01, a23, a45, flags, name) = struct.unpack_from(
            "<BBBBIBBBB28s", r
        )
        counts = [a01 & 0xF, a01 >> 4, a23 & 0xF, a23 >> 4, a45 & 0xF, a45 >> 4]
        # vị trí byte R/G/B trong mỗi LED của dải ARGB (0x00RRGGBB = offset của từng màu)
        cal = [struct.unpack_from("<I", r, 44)[0], struct.unpack_from("<I", r, 48)[0]]
        r2 = self._get(0x61)
        cal.append(struct.unpack_from("<I", r2, 4)[0])
        return {
            "color_order": [((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF) for c in cal],
            "name": name.split(b"\0")[0].decode(errors="replace"),
            "fw": ".".join(str((fw >> s) & 0xFF) for s in (0, 8, 16, 24)),
            "flags": flags,
            "led_counts": [LED_COUNT_STEPS[c] if c < 5 else c for c in counts],
            "led_counts_raw": counts,
        }

    # --- API ---------------------------------------------------------
    def set_led_count(self, count):
        """Số LED tối đa mỗi header ARGB (32/64/256...). Áp dụng cho cả 6 kênh."""
        idx = next((i for i, s in enumerate(LED_COUNT_STEPS) if count <= s), 4)
        nib = (idx << 4) | idx
        self._send(bytes([REPORT_ID, 0x34, nib, nib, nib]))

    def set_direct_headers(self, zones):
        """Các header ARGB trong `zones` chuyển sang direct (màu do máy gửi), còn lại chạy
        hiệu ứng built-in. Lệnh 0x32 đặt cả mask một lần nên phải truyền đủ danh sách."""
        mask = 0
        for name in zones:
            if ZONES[name][1]:
                mask |= ZONES[name][1]
        self._cmd(0x32, mask)
        time.sleep(0.05)

    def set_direct_color(self, zone, color, count=64):
        """Chế độ direct: tô cả dải ARGB của `zone` một màu (cần set_direct_headers trước)."""
        idx = ["argb1", "argb2", "argb3"].index(zone)
        header = DIRECT_HEADERS[idx]
        o_r, o_g, o_b = self.info["color_order"][idx]
        led = bytearray(3)
        led[o_r], led[o_g], led[o_b] = color
        offset = 0
        while count > 0:
            n = min(19, count)  # tối đa 19 LED mỗi gói
            self._send(struct.pack("<BBHB", REPORT_ID, header, offset, n * 3) + bytes(led) * n)
            offset += n * 3
            count -= n

    def set_effect(self, zones, effect, color=(255, 255, 255), speed=3, brightness=255,
                   direct_zones=()):
        """Đặt hiệu ứng phần cứng cho các vùng.

        effect: EFFECT_*; color: (r, g, b); speed: 1 (chậm) .. 5 (nhanh);
        brightness: 0..255; direct_zones: các vùng khác đang do daemon điều khiển (giữ direct).
        """
        # Main xuất xưởng để số LED = 0 (dù OpenRGB coi 0 là "32"): hiệu ứng phần cứng
        # khi đó tắt hết đèn ARGB, direct mode thì vẫn chạy. Đặt 64 nếu chưa đặt.
        if 0 in self.info["led_counts_raw"][:4]:
            self.set_led_count(64)
            self.info = self._read_info()
            time.sleep(0.05)

        self.set_direct_headers([z for z in direct_zones if z not in zones])
        self.send_effects(zones, effect, color, speed, brightness)

    def send_effects(self, zones, effect, color=(255, 255, 255), speed=3, brightness=255):
        """Chỉ gửi gói hiệu ứng + áp dụng (không đụng mask direct). Daemon dùng để tô LED
        onboard mỗi khung hình vì LED onboard không có chế độ direct."""
        # Gigabyte: giá trị speed lớn = chu kỳ dài = chậm. Đổi thang 1..5 -> 8..0
        s = max(0, min(8, (5 - int(speed)) * 2))
        r, g, b = color
        mask = 0
        for name in zones:
            led = ZONES[name][0]
            mask |= 1 << led
            p = [0, 0, 0, 0]  # period0..3
            prm = [0, 0, 0, 0]  # effect_param0..3
            if effect == EFFECT_PULSE:
                p[0] = 400 + s * 100 if s <= 6 else 1000 + (s - 6) * 200
                p[1], p[2] = p[0], 200
            elif effect == EFFECT_FLASH:
                p[0], p[1], p[2] = 100, 100, s * 200 + 700
            elif effect == EFFECT_CYCLE:
                p[0] = s * 100 + 300
                p[1] = p[0] - 200
                prm[0] = 7
            elif effect == EFFECT_WAVE4:
                p[0] = [400, 300, 200, 120, 60][int(speed) - 1]
                prm[0] = 7
            elif effect == EFFECT_WAVE:
                p[0] = ((s + 1) ** 2 + (s + 1) + 10) * 5 // 2
                prm[0], prm[1] = 7, 1
            pkt = struct.pack(
                "<BBIIBBBBIIHHHHBBBB",
                REPORT_ID,
                0x20 + led,
                1 << led,
                0,
                0,
                effect,
                brightness,
                0,
                (r << 16) | (g << 8) | b,
                0,
                *p,
                *prm,
            )
            self._send(pkt)
        # áp dụng cho các vùng vừa đặt
        self._send(struct.pack("<BBII", REPORT_ID, 0x28, mask, 0))

    def save_to_flash(self):
        """Lưu trạng thái hiện tại vào flash của main (giữ sau khi tắt máy)."""
        self._cmd(0x47, 1)
        time.sleep(0.02)
        self._cmd(0x5E, 0)
