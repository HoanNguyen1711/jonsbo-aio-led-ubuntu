"""Icon trên thanh trên cùng (GNOME + extension Ubuntu AppIndicators).

Lúc khởi động áp dụng lại config đã lưu, nên thay luôn cho autostart `rgbctl apply`.
"""
import os
import subprocess
import sys
import threading

from . import aio_display, core, daemon, i18n

COLORS = [
    ("color.red", "ff0000"),
    ("color.orange", "ff6a00"),
    ("color.yellow", "ffd000"),
    ("color.green", "00ff40"),
    ("color.blue", "0050ff"),
    ("color.purple", "9d00ff"),
    ("color.white", "ffffff"),
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
            for t in core.ALL_TARGETS:
                try:
                    core.set_state(t, state)
                except Exception as e:  # noqa: BLE001 - RAM chưa bật SMBus, không có card...
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

    # autostart lúc đăng nhập và mở app từ menu đều có thể bật tray: chỉ giữ một icon
    if not daemon.single_instance("tray"):
        return 0

    with _lock:
        core.apply_config()

    def ensure_aio():
        # Chỉ dự phòng khi không có service: chờ để service systemd (khởi động cùng lúc
        # đăng nhập) giữ khoá trước, nếu không nó sẽ tự thoát và mất Restart=on-failure.
        if aio_display.get_settings()["enabled"]:
            daemon.start_background()
        return False

    ind = AppIndicator.Indicator.new(
        "rgbctl", "rgbctl-symbolic", AppIndicator.IndicatorCategory.HARDWARE,
    )
    # chạy từ git clone: lấy icon trong repo; bản .deb đã cài icon vào /usr/share/icons
    if os.path.isdir(ICONS_DIR):
        ind.set_icon_theme_path(ICONS_DIR)
    ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    ind.set_title("RGB Control")

    menu = Gtk.Menu()
    labeled = []  # (menu item, khoá chuỗi) để đổi nhãn khi đổi ngôn ngữ trong GUI

    def item(key, cb, parent=menu):
        it = Gtk.MenuItem(label=i18n.t(key))
        it.connect("activate", lambda _w: cb())
        parent.append(it)
        labeled.append((it, key))
        return it

    item("mode.rainbow", lambda: _apply_all("rainbow"))

    static = Gtk.MenuItem(label=i18n.t("tray.static"))
    labeled.append((static, "tray.static"))
    sub = Gtk.Menu()
    for key, hexc in COLORS:
        item(key, lambda c=hexc: _apply_all("static", c), sub)
    static.set_submenu(sub)
    menu.append(static)

    item("tray.breathing", lambda: _apply_all("breathing"))
    item("tray.off", lambda: _apply_all("off"))
    menu.append(Gtk.SeparatorMenuItem())

    aio = Gtk.CheckMenuItem(label=i18n.t("aio"))
    aio.set_active(aio_display.get_settings()["enabled"])
    aio_handler = aio.connect("toggled", lambda w: daemon.set_aio_enabled(w.get_active()))
    menu.append(aio)
    menu.append(Gtk.SeparatorMenuItem())

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    item("tray.open", lambda: subprocess.Popen(
        [sys.executable, "-m", "rgbctl", "gui"], cwd=root, start_new_session=True))
    item("tray.quit", Gtk.main_quit)

    menu.show_all()
    ind.set_menu(menu)

    temp_path = aio_display.cpu_temp_path()
    shown_lang = [i18n.current()]

    def tick():
        lang = i18n.current()
        if lang != shown_lang[0]:
            for it, key in labeled:
                it.set_label(i18n.t(key, lang=lang))
            shown_lang[0] = lang
        try:
            temp = f": {aio_display.cpu_temp(temp_path):.0f}°C"
        except OSError:
            temp = ""
        aio.set_label(i18n.t("aio", lang=lang) + temp)
        # đồng bộ khi bật/tắt từ GUI, không kích hoạt lại handler
        on = aio_display.get_settings()["enabled"]
        if aio.get_active() != on:
            aio.handler_block(aio_handler)
            aio.set_active(on)
            aio.handler_unblock(aio_handler)
        return True

    tick()
    GLib.timeout_add_seconds(2, tick)
    GLib.timeout_add_seconds(10, ensure_aio)
    Gtk.main()
    return 0
