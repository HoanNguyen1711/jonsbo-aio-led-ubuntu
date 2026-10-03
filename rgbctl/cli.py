import argparse
import sys

from . import aio_display, core, corsair_ram, fusion

EPILOG = """ví dụ:
  rgbctl set static ff0000              # tất cả (main + RAM) màu đỏ
  rgbctl set breathing 00aaff -t ram    # chỉ RAM, hiệu ứng thở
  rgbctl set rainbow -t argb1 -s 5      # header ARGB_V2_1 cầu vồng nhanh
  rgbctl off                            # tắt hết
  rgbctl apply                          # áp dụng lại config đã lưu
  rgbctl aio-temp                       # nhiệt độ CPU lên màn hình AIO
  rgbctl gui                            # mở cửa sổ
"""


def cmd_info(_args):
    try:
        with fusion.Fusion2() as dev:
            i = dev.info
            print(f"Main : {i['name']} (fw {i['fw']}) tại {dev.dev}")
            print(f"       số LED tối đa mỗi header: {i['led_counts'][:4]}")
    except Exception as e:
        print(f"Main : lỗi - {e}")
    try:
        with corsair_ram.CorsairRAM() as dev:
            addrs = ", ".join(f"0x{a:02x}" for a in dev.sticks)
            print(f"RAM  : {len(dev.sticks)} thanh Corsair ({addrs})")
    except Exception as e:
        print(f"RAM  : lỗi - {e}")
    dev = aio_display.find_hidraw()
    print(f"AIO  : màn hình nhiệt độ tại {dev}" if dev else "AIO  : không thấy màn hình nhiệt độ")
    print(f"Config: {core.CONFIG_PATH}")


def _apply_targets(targets, state, save_flash, remember):
    rc = 0
    for t in targets:
        try:
            core.apply(t, **state, save_flash=save_flash and t != "ram")
            print(f"✓ {t}")
            if remember:
                core.remember(t, state)
        except Exception as e:
            print(f"✗ {t}: {e}", file=sys.stderr)
            rc = 1
    return rc


def _targets(t):
    return ["mb", "ram"] if t == "all" else [t]


def cmd_set(args):
    state = {
        "mode": args.mode,
        "color": args.color,
        "speed": args.speed,
        "brightness": args.brightness,
    }
    return _apply_targets(_targets(args.target), state, args.flash, not args.no_save)


def cmd_off(args):
    state = {**core.DEFAULT_STATE, "mode": "off"}
    return _apply_targets(_targets(args.target), state, args.flash, not args.no_save)


def cmd_apply(_args):
    cfg = core.load_config()
    if not cfg:
        print("Chưa có config nào được lưu.")
        return 0
    errors = core.apply_config(cfg)
    for t, e in errors:
        print(f"✗ {t}: {e}", file=sys.stderr)
    return 1 if errors else 0


def cmd_leds(args):
    with fusion.Fusion2() as dev:
        dev.set_led_count(args.count)
    print(f"Đã đặt số LED tối đa mỗi header ARGB = {args.count}")


def cmd_aio_temp(args):
    if args.once:
        print(f"Đã gửi {aio_display.run(once=True):.0f}°C lên màn hình AIO")
    else:
        aio_display.run()


def cmd_tray(_args):
    from . import tray
    return tray.main()


def cmd_gui(_args):
    from . import gui
    return gui.main()


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="rgbctl",
        description="Điều khiển LED: main Gigabyte (fan/AIO Jonsbo) + RAM Corsair",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("info", help="xem thiết bị phát hiện được").set_defaults(func=cmd_info)

    target_help = "all | " + " | ".join(core.TARGETS) + " (mặc định: all)"
    s = sub.add_parser("set", help="đặt hiệu ứng")
    s.add_argument("mode", choices=core.MODES)
    s.add_argument("color", nargs="?", default="ffffff", help="màu hex, vd ff8800")
    s.add_argument("-t", "--target", default="all", choices=["all", *core.TARGETS], help=target_help)
    s.add_argument("-s", "--speed", type=int, default=3, help="1 (chậm) .. 5 (nhanh)")
    s.add_argument("-b", "--brightness", type=int, default=100, help="0..100")
    s.add_argument("--flash", action="store_true", help="lưu vào flash của main (giữ cả khi chưa đăng nhập)")
    s.add_argument("--no-save", action="store_true", help="không ghi vào config")
    s.set_defaults(func=cmd_set)

    o = sub.add_parser("off", help="tắt đèn")
    o.add_argument("-t", "--target", default="all", choices=["all", *core.TARGETS])
    o.add_argument("--flash", action="store_true")
    o.add_argument("--no-save", action="store_true")
    o.set_defaults(func=cmd_off)

    sub.add_parser("apply", help="áp dụng lại config đã lưu").set_defaults(func=cmd_apply)

    l = sub.add_parser("leds", help="số LED tối đa mỗi header ARGB (nếu fan chỉ sáng một phần)")
    l.add_argument("count", type=int, choices=fusion.LED_COUNT_STEPS)
    l.set_defaults(func=cmd_leds)

    a = sub.add_parser("aio-temp", help="hiển thị nhiệt độ CPU lên màn hình AIO (chạy liên tục)")
    a.add_argument("--once", action="store_true", help="gửi một lần rồi thoát")
    a.set_defaults(func=cmd_aio_temp)

    sub.add_parser("gui", help="mở giao diện").set_defaults(func=cmd_gui)
    sub.add_parser("tray", help="icon trên thanh trên cùng (áp dụng config khi khởi động)").set_defaults(
        func=cmd_tray)

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 0
    try:
        return args.func(args) or 0
    except PermissionError as e:
        print(f"Không có quyền truy cập {e.filename}. Chạy ./install.sh (udev) hoặc dùng sudo.",
              file=sys.stderr)
        return 1
