"""Icon trên thanh trên cùng (GNOME + extension Ubuntu AppIndicators).

Lúc khởi động áp dụng lại config đã lưu, nên thay luôn cho autostart `rgbctl apply`.
"""
import os
import subprocess
import sys
import threading

from . import aio_display, core

COLORS = [
    ("Đỏ", "ff0000"),
    ("Cam", "ff6a00"),
    ("Vàng", "ffd000"),
    ("Xanh lá", "00ff40"),
    ("Xanh dương", "0050ff"),
    ("Tím", "9d00ff"),
    ("Trắng", "ffffff"),
]

ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")

_lock = threading.Lock()


def _load_libs():
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3, GLib, Gtk

    return AyatanaAppIndicator3, GLib, Gtk


def _apply_all(mode, color=None):
    """Áp dụng cho main + RAM ở luồng nền; giữ tốc độ/độ sáng đang lưu."""
    cfg = core.load_config()
    state = {**core.DEFAULT_STATE, **cfg.get("mb", {}), "mode": mode}
    if color:
        state["color"] = color

    def work():
        with _lock:
            for t in ("mb", "ram"):
                try:
                    core.apply(t, **state)
                    core.remember(t, state)
                except Exception as e:  # noqa: BLE001 - RAM có thể chưa bật SMBus
                    print(f"rgbctl tray: {t}: {e}", file=sys.stderr)

    threading.Thread(target=work, daemon=True).start()


def main():
    try:
        AppIndicator, GLib, Gtk = _load_libs()
    except (ImportError, ValueError):
        # thiếu gir1.2-ayatanaappindicator3-0.1: vẫn làm phần quan trọng là áp config
        print("Thiếu gói gir1.2-ayatanaappindicator3-0.1, chỉ áp dụng config rồi thoát.",
              file=sys.stderr)
        core.apply_config()
        return 1

    with _lock:
        core.apply_config()
    if aio_display.get_settings()["enabled"] and not aio_display.is_running():
        aio_display.start_background()

    ind = AppIndicator.Indicator.new(
        "rgbctl", "rgbctl-symbolic", AppIndicator.IndicatorCategory.HARDWARE,
    )
    # lấy icon thẳng từ repo, không phụ thuộc đã cài icon vào theme hay chưa
    ind.set_icon_theme_path(ICONS_DIR)
    ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    ind.set_title("RGB Control")

    menu = Gtk.Menu()

    def item(label, cb, parent=menu):
        it = Gtk.MenuItem(label=label)
        it.connect("activate", lambda _w: cb())
        parent.append(it)
        return it

    item("Cầu vồng", lambda: _apply_all("rainbow"))

    static = Gtk.MenuItem(label="Tĩnh")
    sub = Gtk.Menu()
    for name, hexc in COLORS:
        item(name, lambda c=hexc: _apply_all("static", c), sub)
    static.set_submenu(sub)
    menu.append(static)

    item("Thở (màu hiện tại)", lambda: _apply_all("breathing"))
    item("Tắt đèn", lambda: _apply_all("off"))
    menu.append(Gtk.SeparatorMenuItem())

    aio = Gtk.CheckMenuItem(label="Màn hình AIO")
    aio.set_active(aio_display.get_settings()["enabled"])
    aio_handler = aio.connect("toggled", lambda w: aio_display.set_enabled(w.get_active()))
    menu.append(aio)
    menu.append(Gtk.SeparatorMenuItem())

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    item("Mở cửa sổ…", lambda: subprocess.Popen(
        [sys.executable, "-m", "rgbctl", "gui"], cwd=root, start_new_session=True))
    item("Thoát", Gtk.main_quit)

    menu.show_all()
    ind.set_menu(menu)

    temp_path = aio_display.cpu_temp_path()

    def tick():
        try:
            temp = f": {aio_display.cpu_temp(temp_path):.0f}°C"
        except OSError:
            temp = ""
        aio.set_label(f"Màn hình AIO{temp}")
        # đồng bộ khi bật/tắt từ GUI, không kích hoạt lại handler
        on = aio_display.get_settings()["enabled"]
        if aio.get_active() != on:
            aio.handler_block(aio_handler)
            aio.set_active(on)
            aio.handler_unblock(aio_handler)
        return True

    tick()
    GLib.timeout_add_seconds(2, tick)
    Gtk.main()
    return 0
