"""Chuỗi giao diện (GUI + tray) tiếng Anh / tiếng Việt. Ngôn ngữ lưu ở config "ui.lang";
chưa đặt thì theo ngôn ngữ hệ thống (vi_* → tiếng Việt, còn lại tiếng Anh)."""
import os

from . import core

LANGS = {"en": "English", "vi": "Tiếng Việt"}

STRINGS = {
    # hiệu ứng
    "mode.static": ("Static", "Tĩnh"),
    "mode.breathing": ("Breathing", "Thở"),
    "mode.flash": ("Flash", "Nháy"),
    "mode.cycle": ("Color cycle", "Đổi màu"),
    "mode.rainbow": ("Rainbow", "Cầu vồng"),
    "mode.off": ("Off", "Tắt"),
    # thiết bị
    "dev.mb": ("Fans + AIO", "Fan + AIO"),
    "dev.ram": ("RAM", "RAM"),
    "dev.gpu": ("Graphics card", "Card đồ hoạ"),
    # cửa sổ
    "devices": ("Devices", "Thiết bị"),
    "effect": ("Effect", "Hiệu ứng"),
    "color": ("Color", "Màu"),
    "speed": ("Speed", "Tốc độ"),
    "brightness": ("Brightness", "Độ sáng"),
    "language": ("Language", "Ngôn ngữ"),
    "save_mb": ("Save to motherboard", "Lưu vào main"),
    "save_mb.tip": (
        "Write the current Fans + AIO effect to the motherboard's flash so it is kept at boot, "
        "before login. Static / Rainbow / Off only.",
        "Ghi hiệu ứng hiện tại của Fan + AIO vào flash của mainboard để giữ cả lúc khởi động, "
        "trước khi đăng nhập. Chỉ với Tĩnh / Cầu vồng / Tắt.",
    ),
    "status.applying": ("Applying…", "Đang áp dụng…"),
    "status.applied": ("✓ Applied: {}", "✓ Đã áp dụng: {}"),
    "status.saved": ("✓ Saved to motherboard", "✓ Đã lưu vào main"),
    "status.none": ("No device selected", "Chưa chọn thiết bị nào"),
    # màn hình AIO
    "aio": ("AIO display", "Màn hình AIO"),
    "aio.show": ("Show", "Hiển thị"),
    "aio.temp": ("CPU temperature", "Nhiệt độ CPU"),
    "aio.missing": ("AIO display not found", "Không thấy màn hình AIO"),
    "aio.sending": ("Sending to display (PID {})", "Đang gửi lên màn hình (PID {})"),
    "aio.off": ("Off", "Đã tắt"),
    "aio.no_perm": ("No write access to {}. Install the package first.",
                    "Không có quyền ghi {}. Cài gói trước."),
    # tray
    "tray.static": ("Static", "Tĩnh"),
    "tray.breathing": ("Breathing (current color)", "Thở (màu hiện tại)"),
    "tray.off": ("Turn off", "Tắt đèn"),
    "tray.open": ("Open window…", "Mở cửa sổ…"),
    "tray.quit": ("Quit", "Thoát"),
    "color.red": ("Red", "Đỏ"),
    "color.orange": ("Orange", "Cam"),
    "color.yellow": ("Yellow", "Vàng"),
    "color.green": ("Green", "Xanh lá"),
    "color.blue": ("Blue", "Xanh dương"),
    "color.purple": ("Purple", "Tím"),
    "color.white": ("White", "Trắng"),
}


def current():
    lang = core.load_config().get("ui", {}).get("lang")
    if lang in LANGS:
        return lang
    sys_lang = os.environ.get("LANGUAGE") or os.environ.get("LC_ALL") or os.environ.get("LANG", "")
    return "vi" if sys_lang.startswith("vi") else "en"


def set_lang(lang):
    cfg = core.load_config()
    cfg.setdefault("ui", {})["lang"] = lang
    core.save_config(cfg)


def t(key, *args, lang=None):
    text = STRINGS[key][0 if (lang or current()) == "en" else 1]
    return text.format(*args) if args else text
