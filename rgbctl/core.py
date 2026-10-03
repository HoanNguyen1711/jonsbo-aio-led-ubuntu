"""Gộp main Gigabyte + RAM Corsair thành một bộ hiệu ứng chung, kèm lưu config."""
import json
import os

from . import corsair_ram as ram
from . import fusion

MODES = ["static", "breathing", "flash", "cycle", "rainbow", "off"]
MODE_LABELS = {
    "static": "Tĩnh",
    "breathing": "Thở",
    "flash": "Nháy",
    "cycle": "Đổi màu",
    "rainbow": "Cầu vồng",
    "off": "Tắt",
}

# mục tiêu -> danh sách vùng. "mb" = tất cả LED/ARGB trên main.
TARGETS = {
    "mb": fusion.ALL_ZONES,
    "argb1": ["argb1"],
    "argb2": ["argb2"],
    "argb3": ["argb3"],
    "board": ["chipset", "led_c"],
    "ram": None,
}

_FUSION_EFFECT = {
    "static": fusion.EFFECT_STATIC,
    "breathing": fusion.EFFECT_PULSE,
    "flash": fusion.EFFECT_FLASH,
    "cycle": fusion.EFFECT_CYCLE,
    "rainbow": fusion.EFFECT_WAVE4,
}

_RAM_EFFECT = {
    "static": ram.MODE_STATIC,
    "breathing": ram.MODE_COLOR_PULSE,
    "flash": ram.MODE_MARQUEE,
    "cycle": ram.MODE_COLOR_SHIFT,
    "rainbow": ram.MODE_RAINBOW_WAVE,
}

CONFIG_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "rgbctl", "config.json"
)

DEFAULT_STATE = {"mode": "static", "color": "ffffff", "speed": 3, "brightness": 100}


def parse_color(s):
    s = s.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Màu không hợp lệ: {s!r} (dạng ff8800)")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def apply(target, mode, color="ffffff", speed=3, brightness=100, save_flash=False):
    """Áp dụng hiệu ứng cho một mục tiêu. speed 1..5, brightness 0..100."""
    if target not in TARGETS:
        raise ValueError(f"Mục tiêu không hợp lệ: {target} (chọn: {', '.join(TARGETS)})")
    if mode not in MODES:
        raise ValueError(f"Hiệu ứng không hợp lệ: {mode} (chọn: {', '.join(MODES)})")
    rgb = parse_color(color)
    speed = max(1, min(5, int(speed)))
    bright = round(max(0, min(100, int(brightness))) * 255 / 100)
    if mode == "off":
        mode, rgb, bright = "static", (0, 0, 0), 0

    if target == "ram":
        with ram.CorsairRAM() as dev:
            # RAM chỉ có 3 mức tốc độ
            rspeed = 0 if speed <= 2 else (1 if speed == 3 else 2)
            ok = dev.set_effect(
                _RAM_EFFECT[mode], rgb, speed=rspeed, brightness=bright,
                random=(mode in ("cycle", "rainbow")),
            )
            if ok and mode == "static":  # gồm cả "off" (đã đổi thành static đen ở trên)
                ok = dev.set_colors(rgb, bright)
            if not ok:
                raise RuntimeError("RAM không xác nhận dữ liệu (CRC sai)")
    else:
        with fusion.Fusion2() as dev:
            dev.set_effect(TARGETS[target], _FUSION_EFFECT[mode], rgb, speed, bright)
            if save_flash:
                dev.save_to_flash()


def apply_config(cfg=None, only=None):
    """Áp dụng toàn bộ config đã lưu. Trả về danh sách (target, lỗi)."""
    cfg = load_config() if cfg is None else cfg
    errors = []
    # "mb" trước để các header riêng lẻ ghi đè lên sau
    for target in sorted(cfg, key=lambda t: (t != "mb", t)):
        if only and target not in only:
            continue
        try:
            apply(target, **{**DEFAULT_STATE, **cfg[target]})
        except Exception as e:  # noqa: BLE001 - báo lỗi từng thiết bị, không dừng cả loạt
            errors.append((target, e))
    return errors


def remember(target, state):
    """Lưu trạng thái của target; đặt "mb" thì xoá các header riêng để khỏi bị ghi đè."""
    cfg = load_config()
    if target == "mb":
        for t in ("argb1", "argb2", "argb3", "board"):
            cfg.pop(t, None)
    cfg[target] = state
    save_config(cfg)
