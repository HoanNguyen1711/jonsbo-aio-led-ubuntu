"""Hiệu ứng do phần mềm tính (daemon gửi màu ~30 lần/giây).

Chip trên main và chip trên RAM có đồng hồ riêng nên hiệu ứng phần cứng không bao giờ
khớp nhau. Các hiệu ứng ở đây tính từ cùng một thời điểm `t` nên mọi thiết bị đồng bộ.
"""
import colorsys
import math

SOFTWARE_MODES = ("breathing", "flash", "cycle")

# chu kỳ (giây) theo tốc độ 1 (chậm) .. 5 (nhanh)
_PERIOD = {
    "breathing": [5.0, 4.0, 3.0, 2.2, 1.5],
    "flash": [2.0, 1.5, 1.0, 0.7, 0.45],
    "cycle": [24.0, 16.0, 10.0, 6.0, 3.5],
}


def color_at(t, mode, color, speed, brightness):
    """Màu (r, g, b) tại thời điểm t (giây). color: (r, g, b); speed 1..5; brightness 0..100."""
    if mode == "rainbow":  # chỉ gặp ở thiết bị một vùng màu (card Colorful): đổi màu toàn bộ
        mode = "cycle"
    period = _PERIOD[mode][max(1, min(5, int(speed))) - 1]
    phase = (t % period) / period
    if mode == "breathing":
        # nửa chu kỳ sáng dần, nửa tối dần; bình phương để mắt thấy đều hơn
        level = ((1 - math.cos(2 * math.pi * phase)) / 2) ** 2
    elif mode == "flash":
        level = 1.0 if phase < 0.3 else 0.0
    else:  # cycle: xoay vòng màu, bỏ qua `color`
        r, g, b = colorsys.hsv_to_rgb(phase, 1.0, 1.0)
        color, level = (r * 255, g * 255, b * 255), 1.0
    k = level * max(0, min(100, brightness)) / 100
    return tuple(round(c * k) for c in color)
