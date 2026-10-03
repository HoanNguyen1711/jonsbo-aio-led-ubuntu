import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import aio_display, core  # noqa: E402

TARGET_LABELS = [
    ("all", "Tất cả"),
    ("mb", "Fan + AIO + main"),
    ("argb1", "ARGB_V2_1"),
    ("argb2", "ARGB_V2_2"),
    ("argb3", "ARGB_V2_3"),
    ("board", "LED trên main"),
    ("ram", "RAM"),
]
_lock = threading.Lock()
PRESETS = ["ff0000", "ff6a00", "ffd000", "00ff40", "00e5ff", "0050ff", "9d00ff", "ff00b0", "ffffff"]


def _rgba(hexstr):
    c = Gdk.RGBA()
    c.parse("#" + hexstr)
    return c


def _hex(rgba):
    return "".join(f"{round(v * 255):02x}" for v in (rgba.red, rgba.green, rgba.blue))


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="RGB")
        self.set_default_size(400, -1)

        cfg = core.load_config()
        state = {**core.DEFAULT_STATE, **cfg.get("mb", {})}

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)
        self.set_child(box)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        box.append(grid)

        def row(i, label, widget):
            lbl = Gtk.Label(label=label, xalign=0)
            grid.attach(lbl, 0, i, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, i, 1, 1)

        self.target = Gtk.DropDown.new_from_strings([l for _, l in TARGET_LABELS])
        row(0, "Thiết bị", self.target)

        self.mode = Gtk.DropDown.new_from_strings([core.MODE_LABELS[m] for m in core.MODES])
        self.mode.set_selected(core.MODES.index(state["mode"]))
        row(1, "Hiệu ứng", self.mode)

        self.color = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False))
        self.color.set_rgba(_rgba(state["color"]))
        row(2, "Màu", self.color)

        swatches = Gtk.Box(spacing=4)
        css = Gtk.CssProvider()
        css.load_from_string(
            "".join(f".sw-{c} {{ background: #{c}; min-width: 24px; min-height: 24px; "
                    f"border-radius: 12px; padding: 0; }}" for c in PRESETS)
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        for c in PRESETS:
            b = Gtk.Button(css_classes=[f"sw-{c}"], tooltip_text="#" + c)
            b.connect("clicked", lambda _b, c=c: (self.color.set_rgba(_rgba(c)), self.on_apply()))
            swatches.append(b)
        grid.attach(swatches, 1, 3, 1, 1)

        self.speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 5, 1)
        self.speed.set_value(state["speed"])
        self.speed.set_draw_value(True)
        row(4, "Tốc độ", self.speed)

        self.bright = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        self.bright.set_value(state["brightness"])
        self.bright.set_draw_value(True)
        row(5, "Độ sáng", self.bright)

        self.flash = Gtk.CheckButton(label="Lưu vào main (giữ màu cả lúc khởi động)")
        box.append(self.flash)

        buttons = Gtk.Box(spacing=8, homogeneous=True)
        off = Gtk.Button(label="Tắt đèn")
        off.connect("clicked", lambda _b: self.on_apply(off=True))
        apply_btn = Gtk.Button(label="Áp dụng", css_classes=["suggested-action"])
        apply_btn.connect("clicked", lambda _b: self.on_apply())
        buttons.append(off)
        buttons.append(apply_btn)
        box.append(buttons)

        self.status = Gtk.Label(xalign=0, wrap=True, css_classes=["dim-label"])
        box.append(self.status)

        self._build_aio(box)

    def on_apply(self, off=False):
        target = TARGET_LABELS[self.target.get_selected()][0]
        state = {
            "mode": "off" if off else core.MODES[self.mode.get_selected()],
            "color": _hex(self.color.get_rgba()),
            "speed": int(self.speed.get_value()),
            "brightness": int(self.bright.get_value()),
        }
        targets = ["mb", "ram"] if target == "all" else [target]
        flash = self.flash.get_active()
        self.status.set_text("Đang áp dụng…")

        def work():
            msgs = []
            _lock.acquire()
            for t in targets:
                try:
                    core.apply(t, **state, save_flash=flash and t != "ram")
                    core.remember(t, state)
                    msgs.append(f"✓ {t}")
                except Exception as e:  # noqa: BLE001
                    msgs.append(f"✗ {t}: {e}")
            _lock.release()
            GLib.idle_add(self.status.set_text, "\n".join(msgs))

        # SMBus ghi từng byte nên RAM mất ~0.5s, chạy nền để UI không đứng
        threading.Thread(target=work, daemon=True).start()


    # --- Màn hình nhiệt độ trên AIO --------------------------------------
    def _build_aio(self, box):
        box.append(Gtk.Separator())
        box.append(Gtk.Label(label="<b>Màn hình AIO</b>", use_markup=True, xalign=0))

        settings = aio_display.get_settings()
        self._aio_error = None
        self.aio_temp_path = aio_display.cpu_temp_path()

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        box.append(grid)

        self.aio_enabled = Gtk.Switch(active=settings["enabled"], halign=Gtk.Align.START)
        self.aio_enabled.connect("notify::active", self.on_aio_toggle)
        grid.attach(Gtk.Label(label="Hiển thị", xalign=0), 0, 0, 1, 1)
        grid.attach(self.aio_enabled, 1, 0, 1, 1)

        self.aio_value = Gtk.Label(xalign=0)
        grid.attach(Gtk.Label(label="Nhiệt độ CPU", xalign=0), 0, 1, 1, 1)
        grid.attach(self.aio_value, 1, 1, 1, 1)

        self.aio_status = Gtk.Label(xalign=0, wrap=True, css_classes=["dim-label"])
        box.append(self.aio_status)

        # đang bật trong config mà chưa có tiến trình (vd chưa cài service) thì chạy luôn
        if settings["enabled"] and not aio_display.is_running():
            self._aio_error = aio_display.start_background()
        self._aio_tick()
        GLib.timeout_add_seconds(1, self._aio_tick)

    def _aio_tick(self):
        try:
            self.aio_value.set_text(f"{aio_display.cpu_temp(self.aio_temp_path):.0f}°C")
        except Exception:  # noqa: BLE001
            self.aio_value.set_text("—")
        pid = aio_display.is_running()
        dev = aio_display.find_hidraw()
        if not dev:
            self.aio_status.set_text("Không thấy màn hình AIO")
        elif self._aio_error:
            self.aio_status.set_text(self._aio_error)
        elif pid and self.aio_enabled.get_active():
            self.aio_status.set_text(f"Đang gửi lên màn hình (PID {pid})")
        else:
            self.aio_status.set_text("Đã tắt")
        return True

    def on_aio_toggle(self, switch, _pspec):
        self._aio_error = aio_display.set_enabled(switch.get_active())
        GLib.timeout_add(500, lambda: self._aio_tick() and False)

def main():
    app = Gtk.Application(application_id="dev.hoan.rgbctl")
    app.connect("activate", lambda a: Window(a).present())
    return app.run(sys.argv[:1])
