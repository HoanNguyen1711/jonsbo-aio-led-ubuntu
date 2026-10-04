"""Đèn trang trí trên card đồ hoạ Colorful (đã thử: iGame RTX 5070 Battle-AX, 7377:2000).

Chip LED ở địa chỉ 0x61 trên bus I2C nội bộ của card ("NVIDIA i2c adapter 1"). Protocol
theo OpenRGB (ColorfulGPUController): gói nhận diện AA EF 81 02 1C 02 → trả về AA EF 81 …;
gói đặt màu AA EF 12 03 01 FF R G B + tổng 16 bit. Chip chỉ có một vùng màu (gói màu từng
LED của dòng Vulcan/Neptune bị bỏ qua), nên mọi hiệu ứng động do daemon gửi màu liên tục.

Bus này còn có chip điều áp của card: chỉ ghi vào 0x61 và chỉ sau khi nhận diện đúng chip.
"""
import fcntl
import glob
import os

I2C_SLAVE = 0x0703
ADDR = 0x61
NVIDIA_VEN = "0x10de"
COLORFUL_SUB_VEN = "0x7377"
HANDSHAKE = bytes([0xAA, 0xEF, 0x81, 0x02, 0x1C, 0x02])


def _candidate_buses():
    """Bus I2C của card NVIDIA do Colorful sản xuất, adapter 1 trước."""
    found = []
    for path in glob.glob("/sys/class/i2c-dev/i2c-*"):
        try:
            with open(f"{path}/name") as f:
                name = f.read().strip()
            pci = os.path.realpath(f"{path}/device/..")
            with open(f"{pci}/vendor") as f:
                vendor = f.read().strip()
            with open(f"{pci}/subsystem_vendor") as f:
                sub_vendor = f.read().strip()
        except OSError:
            continue
        if name.startswith("NVIDIA i2c adapter") and vendor == NVIDIA_VEN \
                and sub_vendor == COLORFUL_SUB_VEN:
            found.append((not name.startswith("NVIDIA i2c adapter 1 "), "/dev/" + os.path.basename(path)))
    return [dev for _, dev in sorted(found)]


class ColorfulGPU:
    def __init__(self):
        for dev in _candidate_buses():
            try:
                fd = os.open(dev, os.O_RDWR)
            except OSError:
                continue
            try:
                fcntl.ioctl(fd, I2C_SLAVE, ADDR)
                os.read(fd, 1)  # chỉ đọc: có chip ở 0x61 không (bus nối ra màn hình thì không)
                os.write(fd, HANDSHAKE)
                if os.read(fd, 3) == HANDSHAKE[:3]:
                    self.fd, self.dev = fd, dev
                    return
            except OSError:
                pass
            os.close(fd)
        raise RuntimeError("Không tìm thấy đèn card Colorful (I2C 0x61)")

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def set_color(self, color):
        r, g, b = color
        pkt = bytes([0xAA, 0xEF, 0x12, 0x03, 0x01, 0xFF, r, g, b])
        crc = sum(pkt)
        os.write(self.fd, pkt + bytes([crc & 0xFF, crc >> 8]))
