"""Gộp main Gigabyte + RAM Corsair thành một bộ hiệu ứng chung, kèm lưu config."""
import json
import os

import time

from . import corsair_ram as ram
from . import effects, fusion

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
    # ghi file tạm rồi đổi tên: daemon đọc config liên tục, không được thấy file ghi dở
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)


def _zone_states(cfg):
    """Trạng thái thực của từng vùng trên main: "mb" cho tất cả, header riêng ghi đè."""
    states = {z: cfg["mb"] for z in fusion.ALL_ZONES} if "mb" in cfg else {}
    for target in ("argb1", "argb2", "argb3", "board"):
        if target in cfg:
            for z in TARGETS[target]:
                states[z] = cfg[target]
    return states


def software_plan(cfg):
    """Vùng nào đang dùng hiệu ứng phần mềm (daemon chạy): {vùng | "ram": state}."""
    plan = {z: {**DEFAULT_STATE, **st} for z, st in _zone_states(cfg).items()}
    if "ram" in cfg:
        plan["ram"] = {**DEFAULT_STATE, **cfg["ram"]}
    return {z: st for z, st in plan.items() if st["mode"] in effects.SOFTWARE_MODES}


def _validate(target, mode):
    if target not in TARGETS:
        raise ValueError(f"Mục tiêu không hợp lệ: {target} (chọn: {', '.join(TARGETS)})")
    if mode not in MODES:
        raise ValueError(f"Hiệu ứng không hợp lệ: {mode} (chọn: {', '.join(MODES)})")


def _apply_hardware(target, mode, color="ffffff", speed=3, brightness=100, save_flash=False,
                    direct_zones=()):
    """Đặt hiệu ứng do chip tự chạy (tĩnh / cầu vồng / tắt). speed 1..5, brightness 0..100."""
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
            dev.set_effect(TARGETS[target], _FUSION_EFFECT[mode], rgb, speed, bright,
                           direct_zones=direct_zones)
            if save_flash:
                dev.save_to_flash()


def set_state(target, state, save=True, save_flash=False):
    """Đặt hiệu ứng cho target và lưu config.

    Thở / nháy / đổi màu do daemon tính (đồng bộ mọi thiết bị) nên chỉ cần lưu config và
    bảo đảm daemon đang chạy. Các hiệu ứng còn lại ghi thẳng vào chip.
    """
    from . import daemon

    state = {**DEFAULT_STATE, **state}
    _validate(target, state["mode"])
    software = state["mode"] in effects.SOFTWARE_MODES
    if software and not save:
        raise ValueError("Thở / nháy / đổi màu do daemon chạy theo config, không dùng được --no-save")
    if save:
        remember(target, state)
    if software:
        daemon.start_background()
        return
    if save and daemon.is_running():
        time.sleep(0.15)  # chờ daemon đọc config mới và thôi gửi màu cho vùng này
    plan = software_plan(load_config())
    _apply_hardware(target, **state, save_flash=save_flash,
                    direct_zones=[z for z in plan if z != "ram"])


def apply_config(cfg=None):
    """Áp dụng toàn bộ config đã lưu (lúc đăng nhập). Trả về danh sách (target, lỗi)."""
    cfg = load_config() if cfg is None else cfg
    plan = software_plan(cfg)
    direct = [z for z in plan if z != "ram"]
    errors = []
    # "mb" trước để các header riêng lẻ ghi đè lên sau; bỏ qua khoá khác như "aio"
    for target in sorted((t for t in cfg if t in TARGETS), key=lambda t: (t != "mb", t)):
        state = {**DEFAULT_STATE, **cfg[target]}
        if state["mode"] in effects.SOFTWARE_MODES:
            continue
        try:
            _apply_hardware(target, **state, direct_zones=direct)
        except Exception as e:  # noqa: BLE001 - báo lỗi từng thiết bị, không dừng cả loạt
            errors.append((target, e))
    if plan:
        from . import daemon
        daemon.start_background()
    return errors


def remember(target, state):
    """Lưu trạng thái của target; đặt "mb" thì xoá các header riêng để khỏi bị ghi đè."""
    cfg = load_config()
    if target == "mb":
        for t in ("argb1", "argb2", "argb3", "board"):
            cfg.pop(t, None)
    cfg[target] = state
    save_config(cfg)
