import os
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import aio_display, core, daemon  # noqa: E402

DEVICES = [("mb", "Fan + AIO"), ("ram", "RAM"), ("gpu", "Card đồ hoạ")]
DEVICE_NAMES = dict(DEVICES)
PRESETS = ["ff0000", "ff6a00", "ffd000", "00ff40", "00e5ff", "0050ff", "9d00ff", "ff00b0", "ffffff"]
NO_COLOR = ("cycle", "rainbow", "off")  # hiệu ứng không dùng màu đã chọn
NO_SPEED = ("static", "off")
FLASHABLE = ("static", "rainbow", "off")  # hiệu ứng do chip tự chạy, lưu được vào flash
DEBOUNCE_MS = 300


def _rgba(hexstr):
    c = Gdk.RGBA()
    c.parse("#" + hexstr)
    return c


def _hex(rgba):
    return "".join(f"{round(v * 255):02x}" for v in (rgba.red, rgba.green, rgba.blue))


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="RGB")
        self.set_default_size(420, -1)

        cfg = core.load_config()
        state = {**core.DEFAULT_STATE,
                 **next((cfg[t] for t, _ in DEVICES if t in cfg), {})}

        # hàng đợi áp dụng: chỉ giữ yêu cầu mới nhất, một luồng nền xử lý lần lượt
        self._pending = None
        self._pending_lock = threading.Lock()
        self._worker = None
        self._debounce = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)
        self.set_child(box)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        box.append(grid)

        def row(i, label, widget):
            grid.attach(Gtk.Label(label=label, xalign=0), 0, i, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, i, 1, 1)

        devices = Gtk.Box(spacing=12)
        self.devices = {}
        for key, label in DEVICES:
            cb = Gtk.CheckButton(label=label, active=True)
            devices.append(cb)
            self.devices[key] = cb
        row(0, "Thiết bị", devices)

        self.mode = Gtk.DropDown.new_from_strings([core.MODE_LABELS[m] for m in core.MODES])
        self.mode.set_selected(core.MODES.index(state["mode"]))
        row(1, "Hiệu ứng", self.mode)

        color_row = Gtk.Box(spacing=8)
        self.color = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False))
        self.color.set_rgba(_rgba(state["color"]))
        color_row.append(self.color)
        css = Gtk.CssProvider()
        css.load_from_string(
            "".join(f".sw-{c} {{ background: #{c}; min-width: 22px; min-height: 22px; "
                    f"border-radius: 11px; padding: 0; }}" for c in PRESETS)
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        for c in PRESETS:
            b = Gtk.Button(css_classes=[f"sw-{c}"], tooltip_text="#" + c,
                           valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda _b, c=c: self.color.set_rgba(_rgba(c)))
            color_row.append(b)
        self.color_label = Gtk.Label(label="Màu", xalign=0)
        grid.attach(self.color_label, 0, 2, 1, 1)
        grid.attach(color_row, 1, 2, 1, 1)
        self.color_row = color_row

        self.speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 5, 1)
        self.speed.set_value(state["speed"])
        self.speed.set_draw_value(True)
        row(3, "Tốc độ", self.speed)

        self.bright = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        self.bright.set_value(state["brightness"])
        self.bright.set_draw_value(True)
        row(4, "Độ sáng", self.bright)

        self.save_btn = Gtk.Button(
            label="Lưu vào main", halign=Gtk.Align.START,
            tooltip_text="Ghi hiệu ứng hiện tại của Fan + AIO vào flash của mainboard để giữ cả "
                         "lúc khởi động, trước khi đăng nhập. Chỉ với Tĩnh / Cầu vồng / Tắt.",
        )
        self.save_btn.connect("clicked", lambda _b: self._request(["mb"], save_flash=True))
        grid.attach(self.save_btn, 1, 5, 1, 1)

        self.status = Gtk.Label(xalign=0, wrap=True, css_classes=["dim-label"])
        box.append(self.status)

        # nối tín hiệu sau khi đã đặt giá trị ban đầu, để mở cửa sổ không áp dụng gì
        self.mode.connect("notify::selected", lambda *_: self._changed())
        self.color.connect("notify::rgba", lambda *_: self._changed())
        self.speed.connect("value-changed", lambda *_: self._changed(debounce=True))
        self.bright.connect("value-changed", lambda *_: self._changed(debounce=True))
        for key, cb in self.devices.items():
            cb.connect("toggled", lambda w, key=key: self._device_toggled(key, w.get_active()))
        self._update_sensitivity()

        self._build_aio(box)

    # --- áp dụng ngay khi đổi ----------------------------------------------
    def _state(self):
        return {
            "mode": core.MODES[self.mode.get_selected()],
            "color": _hex(self.color.get_rgba()),
            "speed": int(self.speed.get_value()),
            "brightness": int(self.bright.get_value()),
        }

    def _checked(self):
        return [k for k, cb in self.devices.items() if cb.get_active()]

    def _update_sensitivity(self):
        mode = core.MODES[self.mode.get_selected()]
        for w in (self.color_label, self.color_row):
            w.set_sensitive(mode not in NO_COLOR)
        self.speed.set_sensitive(mode not in NO_SPEED)
        self.bright.set_sensitive(mode != "off")
        self.save_btn.set_sensitive(mode in FLASHABLE and self.devices["mb"].get_active())

    def _changed(self, debounce=False):
        self._update_sensitivity()
        if self._debounce:
            GLib.source_remove(self._debounce)
            self._debounce = None
        if debounce:  # thanh kéo: chờ dừng tay rồi mới gửi
            self._debounce = GLib.timeout_add(DEBOUNCE_MS, self._debounced)
        else:
            self._request(self._checked())

    def _debounced(self):
        self._debounce = None
        self._request(self._checked())
        return False

    def _device_toggled(self, key, active):
        self._update_sensitivity()
        if active:  # tick thêm: thiết bị nhận hiệu ứng đang chọn; bỏ tick: giữ nguyên
            self._request([key])

    def _request(self, targets, save_flash=False):
        if not targets:
            self.status.set_text("Chưa chọn thiết bị nào")
            return
        with self._pending_lock:
            self._pending = (targets, self._state(), save_flash)
            if self._worker is not None:
                return  # luồng đang chạy sẽ lấy yêu cầu mới nhất này
            self._worker = threading.Thread(target=self._work, daemon=True)
        self.status.set_text("Đang áp dụng…")
        self._worker.start()

    def _work(self):
        # SMBus của RAM ghi từng byte (~0.3 s) nên chạy nền; yêu cầu dồn lại thì chỉ làm cái cuối
        while True:
            with self._pending_lock:
                job, self._pending = self._pending, None
                if job is None:
                    self._worker = None  # trong khoá: _request sau đó sẽ tạo luồng mới
                    return
            targets, state, save_flash = job
            ok, errors = [], []
            for t in targets:
                try:
                    core.set_state(t, state, save_flash=save_flash and t == "mb")
                    ok.append(DEVICE_NAMES[t])
                except Exception as e:  # noqa: BLE001
                    errors.append(f"✗ {DEVICE_NAMES[t]}: {e}")
            msg = ("✓ Đã lưu vào main" if save_flash else "✓ Đã áp dụng: " + ", ".join(ok)) \
                if ok else ""
            GLib.idle_add(self.status.set_text, "\n".join([m for m in [msg] if m] + errors))

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
        if settings["enabled"]:
            self._aio_error = daemon.set_aio_enabled(True)
        self._aio_tick()
        GLib.timeout_add_seconds(1, self._aio_tick)

    def _aio_tick(self):
        try:
            self.aio_value.set_text(f"{aio_display.cpu_temp(self.aio_temp_path):.0f}°C")
        except Exception:  # noqa: BLE001
            self.aio_value.set_text("—")
        pid = daemon.is_running()
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
        self._aio_error = daemon.set_aio_enabled(switch.get_active())
        GLib.timeout_add(500, lambda: self._aio_tick() and False)


def main():
    # chạy từ git clone: lấy icon trong repo; bản .deb đã cài icon vào /usr/share/icons
    icons = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")
    if os.path.isdir(icons):
        Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(icons)
    Gtk.Window.set_default_icon_name("rgbctl")
    daemon.start_tray()
    app = Gtk.Application(application_id="dev.hoan.rgbctl")
    app.connect("activate", lambda a: Window(a).present())
    return app.run(sys.argv[:1])
