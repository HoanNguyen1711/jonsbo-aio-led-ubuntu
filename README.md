<img src="icons/rgbctl.svg" width="96" align="right" alt="">

# jonsbo-aio-led-ubuntu (`rgbctl`)

A small personal tool to control the lighting in my PC on Ubuntu, without OpenRGB:
fans, AIO, RAM and graphics card LEDs, plus the temperature display on the AIO pump.
CLI, a GTK window and a tray icon. Breathing / flash / color-cycle effects run in sync
across every device.

It is written for my hardware below. Similar parts will probably work, but nothing else
has been tested.

## My hardware

| Part | Model | Notes |
|---|---|---|
| Motherboard | Gigabyte B850M GAMING X WIFI6E | RGB chip ITE IT5711 |
| CPU cooler | Jonsbo AIO with temperature display | LEDs on the motherboard ARGB headers |
| Case fans | Jonsbo ARGB | motherboard ARGB headers |
| RAM | Corsair Vengeance RGB DDR5 (2 × CMH96GX5M2E6000C36) | needs a kernel parameter, see below |
| Graphics card | Colorful iGame RTX 5070 Battle-AX | single-zone logo light |
| CPU | AMD Ryzen 7 9700X | temperature source for the AIO display |
| OS | Ubuntu, GNOME (Wayland) | |

## Install

Download `rgbctl_<version>_all.deb` from
[Releases](https://github.com/HoanNguyen1711/jonsbo-aio-led-ubuntu/releases), then:

```sh
sudo apt install ./rgbctl_*_all.deb
```

Or build from source:

```sh
git clone git@github.com:HoanNguyen1711/jonsbo-aio-led-ubuntu.git
cd jonsbo-aio-led-ubuntu
./install.sh
```

Log out and back in (not needed with `install.sh`). The tray icon and the background
service (`rgbctl-daemon`) start automatically on login.

### Enable RAM control (once)

The BIOS blocks the SMBus that the RAM sits on. Add a kernel parameter and reboot:

```sh
sudo cp /etc/default/grub /etc/default/grub.bak
sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="/&acpi_enforce_resources=lax /' /etc/default/grub
sudo update-grub
sudo reboot
```

Check that everything is detected:

```sh
rgbctl info
```

## Use

### Window and tray

Open **RGB Control** from the app menu (the tray icon starts with it).

- Tick the devices to control: **Fans + AIO**, **RAM**, **Graphics card**.
- Every change applies immediately. Unticked devices keep their current lighting.
- **Save to motherboard** writes the fans/AIO effect to the board so it shows at boot,
  before login (Static / Rainbow / Off only).
- **AIO display** switch: show the CPU temperature on the pump.
- **Language**: English / Tiếng Việt (defaults to the system language).

The tray menu has quick presets, the AIO display switch and a shortcut to the window.

### Command line

```sh
rgbctl set rainbow                    # everything
rgbctl set static ff0000              # red
rgbctl set breathing 00aaff -s 2      # slow breathing, light blue
rgbctl set cycle -b 40                # color cycle at 40 % brightness
rgbctl set static ff8800 -t ram       # only the RAM
rgbctl off -t gpu                     # turn off the graphics card light
rgbctl info                           # detected devices
```

| Option | Values | Default |
|---|---|---|
| effect | `static`, `breathing`, `flash`, `cycle`, `rainbow`, `off` | |
| color | hex, e.g. `ff8800` | `ffffff` |
| `-t` target | `all`, `mb` (fans + AIO), `ram`, `gpu`, or one header: `argb1` `argb2` `argb3` `board` | `all` |
| `-s` speed | 1 (slow) – 5 (fast) | 3 |
| `-b` brightness | 0 – 100 | 100 |
| `--flash` | also save to the motherboard | off |

Settings are saved to `~/.config/rgbctl/config.json` and restored at login.
CLI messages are in Vietnamese.

### Good to know

- Breathing, flash and color cycle are driven by the background service so all devices stay
  in sync; they freeze if the service stops (`systemctl --user status rgbctl-daemon`).
- The graphics card light is a single zone, so "rainbow" there is a color cycle.
- The AIO display only shows a number while the service is running.
- Fan **speed** is not controlled; use the BIOS Smart Fan curves.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Permission denied` on a device | log out and back in after installing |
| RAM error mentioning `SMBus PIIX4` | add the kernel parameter above |
| Effects stuck / AIO display blank | `systemctl --user restart rgbctl-daemon` |
| No tray icon | GNOME extension *Ubuntu AppIndicators* must be enabled |
| Fans light up only partly | `rgbctl leds 256` |

## Uninstall

```sh
sudo apt remove rgbctl
rm -r ~/.config/rgbctl
```

Remove `acpi_enforce_resources=lax` from `/etc/default/grub` and run `sudo update-grub` if
you added it.

## Release

Bump `__version__` in `rgbctl/__init__.py`, commit, then `git tag vX.Y.Z && git push --tags`.
GitHub Actions builds the `.deb` and attaches it to the release.

## Credits

Device protocols are based on [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB) and
[jonsbolite](https://github.com/danieyal/jonsbolite). Use at your own risk: this tool writes
directly to hardware.
