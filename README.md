<img src="icons/rgbctl.svg" width="96" align="right" alt="">

# jonsbo-aio-led-ubuntu (`rgbctl`)

Tool nhỏ, gọn để điều khiển LED và màn hình nhiệt độ AIO trên Ubuntu, **không cần OpenRGB**:

- **Fan + LED AIO Jonsbo** (cắm vào header ARGB của main Gigabyte)
- **LED trên main Gigabyte** (chip ITE IT5711 – RGB Fusion 2)
- **RAM Corsair Vengeance RGB DDR5**
- **Màn hình nhiệt độ trên block AIO Jonsbo** (hiện nhiệt độ CPU)

Có 3 cách dùng: dòng lệnh (`rgbctl`), cửa sổ GTK4 và icon trên thanh trên cùng (tray).
Viết bằng Python thuần, nói chuyện trực tiếp với `/dev/hidraw*` và `/dev/i2c-*`, không cần
thư viện ngoài (GUI dùng PyGObject có sẵn trên Ubuntu).

> Tool này viết cho một cấu hình cụ thể (bên dưới). Máy khác dùng chip IT5711 / RAM Corsair
> DDR5 / AIO Jonsbo có màn hình nhiều khả năng chạy được, nhưng chưa được kiểm chứng.

---

## Mục lục

- [Phần cứng đã thử](#phần-cứng-đã-thử)
- [Trạng thái tính năng](#trạng-thái-tính-năng)
- [Cài đặt](#cài-đặt)
- [Bật SMBus cho RAM](#bật-smbus-cho-ram-làm-1-lần)
- [Sử dụng](#sử-dụng)
- [Config](#config)
- [Cách hoạt động / protocol](#cách-hoạt-động--protocol)
- [Xử lý sự cố](#xử-lý-sự-cố)
- [Gỡ cài đặt](#gỡ-cài-đặt)
- [Cấu trúc code](#cấu-trúc-code)
- [Ghi công](#ghi-công)

---

## Phần cứng đã thử

| Thành phần | Model | Điều khiển qua |
|---|---|---|
| Mainboard | Gigabyte **B850M GAMING X WIFI6E** | — |
| Chip RGB trên main | ITE **IT5711** (`IT5711-GIGABYTE V1.0.19.6`), USB `048d:5711` | `/dev/hidraw*`, HID feature report `0xCC` |
| Fan case | Jonsbo ARGB (5V 3 pin) | header ARGB_V2_x của main |
| AIO | Jonsbo, LED ARGB + màn hình 2 số | LED: header ARGB của main · màn hình: USB `5131:2007` |
| RAM | Corsair Vengeance RGB DDR5 `CMH96GX5M2E6000C36` (2 thanh) | SMBus AMD PIIX4, địa chỉ `0x18–0x1F` |
| CPU | AMD Ryzen 7 9700X | nhiệt độ đọc từ `k10temp` (Tctl) |
| OS | Ubuntu, GNOME (Wayland), kernel 7.0 | |

**Lưu ý:** thiết bị USB `5131:2007` hiện trong `lsusb` là *"MSR MSR-101U Mini HID magnetic card
reader"*. Đây là **nhầm tên** do VID/PID dùng chung: thật ra nó là màn hình nhiệt độ trên block
AIO (tên HID: `FBB`). Nó **không** điều khiển LED. LED của AIO và fan đều đi qua header ARGB
của main.

## Trạng thái tính năng

| Tính năng | Trạng thái |
|---|---|
| Fan/AIO/main: **Tĩnh** (static) | ✅ đã kiểm chứng |
| Fan/AIO/main: **Cầu vồng** (rainbow) | ✅ đã kiểm chứng |
| Fan/AIO/main: chế độ direct (màu từng LED) | ✅ đã kiểm chứng (dùng nội bộ khi debug) |
| Fan/AIO/main: **Thở / Nháy / Đổi màu** | ⚠️ đã cài đặt, chưa kiểm chứng trên máy thật |
| RAM Corsair (mọi hiệu ứng) | ⚠️ đã cài đặt, chưa chạy thử được (cần [bật SMBus](#bật-smbus-cho-ram-làm-1-lần)) |
| Màn hình AIO hiện nhiệt độ CPU | ✅ đã kiểm chứng |
| GUI GTK4 | ✅ |
| Icon tray | ⚠️ đã cài đặt, cần gói `gir1.2-ayatanaappindicator3-0.1` (install.sh tự cài) |

## Cài đặt

Yêu cầu: Ubuntu có GNOME, Python 3, PyGObject/GTK4 (có sẵn trên Ubuntu desktop).

```sh
git clone git@github.com:HoanNguyen1711/jonsbo-aio-led-ubuntu.git
cd jonsbo-aio-led-ubuntu
./install.sh
```

`install.sh` làm các việc sau.

**Cần sudo (sẽ hỏi mật khẩu):**

1. `apt-get install gir1.2-ayatanaappindicator3-0.1`: thư viện cho icon tray.
2. Chép `60-rgbctl.rules` vào `/etc/udev/rules.d/`: cho user đang đăng nhập truy cập 3 thiết bị
   mà không cần sudo:
   - chip RGB Gigabyte (`048d:5711`)
   - SMBus khe RAM (`SMBus PIIX4 adapter port 0`)
   - màn hình AIO (`5131:2007` **và** tên `FBB`, vì VID/PID này bị nhiều thiết bị khác dùng chung)
3. Tạo `/etc/modules-load.d/rgbctl.conf` để nạp `i2c-dev` khi khởi động.

**Trong thư mục home (không cần sudo):**

4. `~/.local/bin/rgbctl`: symlink về thư mục repo (**đừng xoá/di chuyển thư mục repo**).
5. `~/.local/share/icons/hicolor/…/rgbctl*.svg` và `~/.local/share/applications/dev.hoan.rgbctl.desktop`:
   icon và mục **RGB Control** trong menu ứng dụng.
6. `~/.config/autostart/rgbctl-tray.desktop`: tray tự chạy khi đăng nhập và áp dụng lại config.
7. `~/.config/systemd/user/rgbctl-aio-temp.service`: gửi nhiệt độ CPU lên màn hình AIO.

Nếu shell báo không tìm thấy lệnh `rgbctl`, thêm vào `~/.zshrc` hoặc `~/.bashrc`:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Không muốn cài cũng được: chạy thẳng `sudo ./rgbctl.sh <lệnh>` từ thư mục repo. GUI và tray
không chạy được bằng sudo trên Wayland.

### Bật SMBus cho RAM (làm 1 lần)

BIOS Gigabyte giữ vùng IO của SMBus, nên driver `i2c_piix4` không nhận được bus. Trong `dmesg`
sẽ thấy:

```
ACPI Warning: SystemIO range 0x0000000000000B00-0x0000000000000B08 conflicts with OpRegion ... (\GSA1.SMBI)
ACPI: OSL: Resource conflict; ACPI support missing from driver?
```

Cần thêm tham số kernel `acpi_enforce_resources=lax`. OpenRGB cũng yêu cầu y hệt:

```sh
sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="/&acpi_enforce_resources=lax /' /etc/default/grub
sudo update-grub
sudo reboot
```

Sau khi reboot:

```sh
rgbctl info
# Main : IT5711-GIGABYTE V1.0.19.6 (fw 1.0.19.6) tại /dev/hidraw6
# RAM  : 2 thanh Corsair (...)
# AIO  : màn hình nhiệt độ tại /dev/hidraw7
```

> ⚠️ `acpi_enforce_resources=lax` cho phép driver dùng vùng IO mà firmware ACPI cũng dùng.
> Trên đa số máy không có vấn đề gì, nhưng đó là lý do kernel mặc định chặn. Code RAM ở đây
> chỉ **đọc** để nhận diện và chỉ ghi vào controller LED của Corsair ở `0x18–0x1F`, không đụng
> vùng SPD (`0x50–0x57`).

## Sử dụng

### Dòng lệnh

```sh
rgbctl info                           # xem thiết bị phát hiện được
rgbctl set static ff0000              # tất cả (main + RAM) màu đỏ
rgbctl set rainbow                    # cầu vồng
rgbctl set breathing 00aaff -t ram    # chỉ RAM, hiệu ứng thở
rgbctl set rainbow -t argb1 -s 5      # chỉ header ARGB_V2_1, nhanh nhất
rgbctl set cycle -b 40                # đổi màu, độ sáng 40%
rgbctl off                            # tắt đèn
rgbctl apply                          # áp dụng lại config đã lưu
rgbctl aio-temp                       # gửi nhiệt độ CPU lên màn hình AIO (chạy liên tục)
rgbctl aio-temp --once                # gửi một lần (để thử)
rgbctl leds 64                        # số LED tối đa mỗi header ARGB
rgbctl gui                            # mở cửa sổ
rgbctl tray &                         # icon trên thanh trên cùng
```

**Hiệu ứng:** `static`, `breathing`, `flash`, `cycle`, `rainbow`, `off`

**Tuỳ chọn của `set` / `off`:**

| Tuỳ chọn | Ý nghĩa | Mặc định |
|---|---|---|
| `color` | màu hex, ví dụ `ff8800` (bỏ qua với `cycle`/`rainbow`) | `ffffff` |
| `-t, --target` | `all`, `mb`, `argb1`, `argb2`, `argb3`, `board`, `ram` | `all` |
| `-s, --speed` | 1 (chậm) … 5 (nhanh) | 3 |
| `-b, --brightness` | 0 … 100 | 100 |
| `--flash` | ghi luôn vào flash của main, nên màu giữ cả lúc boot trước khi đăng nhập | tắt |
| `--no-save` | không ghi vào config | tắt |

**Target:**

| Target | Gồm |
|---|---|
| `all` | `mb` + `ram` |
| `mb` | mọi vùng trên main: 3 header ARGB + LED onboard |
| `argb1` / `argb2` / `argb3` | header ARGB_V2_1 / _2 / _3 |
| `board` | LED onboard (Chipset Accent, LED_C) |
| `ram` | tất cả thanh RAM Corsair tìm thấy |

> `--flash` ghi vào bộ nhớ flash của chip trên main. Flash có giới hạn số lần ghi, nên chỉ dùng
> khi đã chốt màu, đừng dùng trong script chạy liên tục.

### GUI

`rgbctl gui`, hoặc mở **RGB Control** trong menu ứng dụng.

- **Thiết bị / Hiệu ứng / Màu / Tốc độ / Độ sáng** rồi bấm **Áp dụng**. Bấm vào ô màu có sẵn là
  áp dụng ngay.
- **Lưu vào main**: tương đương `--flash`.
- Mục **Màn hình AIO**: công tắc **Hiển thị** bật/tắt việc gửi nhiệt độ. Bật thì GUI tự chạy
  tiến trình nền nếu chưa có, tắt thì dừng nó. Đóng cửa sổ thì tiến trình nền vẫn chạy.

### Tray

Tự chạy khi đăng nhập (sau `install.sh`), hoặc chạy tay `rgbctl tray &`. Menu gồm:

```
Cầu vồng
Tĩnh ▸ Đỏ / Cam / Vàng / Xanh lá / Xanh dương / Tím / Trắng
Thở (màu hiện tại)
Tắt đèn
─────────
☑ Màn hình AIO: 43°C      ← bấm để bật/tắt
─────────
Mở cửa sổ…
Thoát
```

Cần extension **Ubuntu AppIndicators** (Ubuntu bật sẵn). Nếu thiếu gói tray, `rgbctl tray` vẫn
áp dụng config rồi thoát, nên màu vẫn được khôi phục lúc đăng nhập.

### Màn hình nhiệt độ AIO

Màn hình **không tự đo nhiệt độ**. Máy phải gửi số liên tục (5 lần/giây), nếu không màn hình
sẽ trống. Sau `install.sh`, việc này do service `rgbctl-aio-temp` làm:

```sh
systemctl --user status rgbctl-aio-temp
journalctl --user -u rgbctl-aio-temp
```

Chữ **CPU** và **JONSBO** trên màn hình là in cố định. Đã thử byte đơn vị (°C/°F) và byte chế
độ hiển thị trong protocol: màn hình này bỏ qua, chỉ hiện được một số 2 chữ số.

## Config

`~/.config/rgbctl/config.json`. GUI, tray và lệnh `set` tự ghi vào file này. `rgbctl apply`
và tray đọc nó lúc đăng nhập.

```json
{
  "mb":  { "mode": "rainbow", "color": "ffffff", "speed": 3, "brightness": 100 },
  "ram": { "mode": "static",  "color": "ff0000", "speed": 3, "brightness": 100 },
  "aio": { "enabled": true }
}
```

Có thể thêm `argb1`, `argb2`, `argb3`, `board` để đặt riêng từng header. Khi áp dụng, `mb`
chạy trước để các header riêng ghi đè lên. Đặt lại `mb` sẽ xoá các mục riêng lẻ đó.

## Cách hoạt động / protocol

### Gigabyte RGB Fusion 2 – ITE IT5711 (`rgbctl/fusion.py`)

- Interface HID vendor, usage page `0xFF89`. Mọi lệnh là **feature report 64 byte**, byte đầu
  là report ID `0xCC`. Gửi qua `ioctl(HIDIOCSFEATURE)` trên `/dev/hidrawN`.
- `CC 60`, rồi đọc feature report: thông tin chip (tên, firmware, số LED mỗi header, thứ tự
  màu). Trên máy này thứ tự màu của dải ARGB là **GRB**.
- `CC 20+n …`: hiệu ứng phần cứng cho vùng `n`. Gói gồm loại hiệu ứng, độ sáng, màu
  (`0x00RRGGBB`), 4 chu kỳ thời gian và 4 tham số. Sau đó gửi `CC 28 <mask>` để áp dụng.
  - Vùng trên B850M GAMING X WIFI6E: `argb1`=5, `argb2`=6, `argb3`=7, Chipset Accent=2, LED_C=4.
- `CC 32 <mask>`: bật/tắt hiệu ứng built-in cho từng header ARGB (bit = 1 là tắt, tức chế độ
  direct).
- `CC 34 …`: số LED tối đa mỗi header.
- `CC 47 1` + `CC 5E`: lưu trạng thái vào flash.
- `CC 58/59/62 …`: chế độ direct, gửi màu từng LED cho header ARGB 1/2/3.

**Hai điều phát hiện trên chip này, khác với OpenRGB:**

1. Chip xuất xưởng để **số LED mỗi header = 0**. Khi đó hiệu ứng phần cứng *tắt hết* đèn ARGB,
   dù chế độ direct vẫn sáng. OpenRGB coi giá trị 0 là "32 LED". Tool tự đặt 64 trước khi gửi
   hiệu ứng nếu đang là 0.
2. Hiệu ứng **Wave (6)** cũng làm tắt đèn. Cầu vồng chạy được với **Wave 4 (12)**, nên
   `rainbow` dùng mã 12.

### Corsair Vengeance RGB DDR5 (`rgbctl/corsair_ram.py`)

- SMBus qua `/dev/i2c-N` (`ioctl I2C_SMBUS`, kiểu byte data). Chỉ quét `0x18–0x1F`. Nhận diện
  bằng thanh ghi `0x43 ∈ {1A,1B,1C}` và `0x44 ∈ {01,03,04}`.
- Đặt hiệu ứng: reset buffer (`0x0B`), bắt đầu (`0x21`), ghi 20 byte cấu hình qua `0x20`, đọc
  checksum CRC-8 ở `0x42` để so, khớp thì ghi `0x82 = 1` để áp dụng. Lệch thì thử lại tối đa 3 lần.

### Màn hình AIO Jonsbo (`rgbctl/aio_display.py`)

- USB HID `5131:2007`, tên `FBB`, usage page `0xFF00`, **không có report ID**, output report
  64 byte.
- Khung tin: `00 01 02 <nhiệt độ> <phần trăm> <đơn vị> 00 …`. Ghi vào hidraw với một byte
  `0x00` đứng đầu (report ID rỗng, kernel bỏ byte này), gửi lại mỗi 200 ms.
- Nhiệt độ đọc từ `k10temp` `temp1_input` (Tctl).
- Chống chạy trùng bằng `flock` trên `$XDG_RUNTIME_DIR/rgbctl-aio.lock`, vì service và tray
  có thể cùng khởi động.

## Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| `Permission denied: '/dev/hidrawN'` | chưa chạy `install.sh`, hoặc chạy `sudo udevadm trigger` rồi đăng xuất/đăng nhập lại |
| `RAM : Không thấy SMBus PIIX4` | chưa thêm `acpi_enforce_resources=lax`, xem [phần trên](#bật-smbus-cho-ram-làm-1-lần) |
| `RAM : Không tìm thấy thanh RAM Corsair RGB nào` | thử `sudo apt install i2c-tools && sudo i2cdetect -y <bus>` để xem địa chỉ nào trả lời |
| Đặt hiệu ứng xong fan/AIO tắt hẳn | báo lại hiệu ứng nào (xem mục phát hiện ở trên). Thử `rgbctl set static ff0000 -t mb` để chắc kết nối vẫn ổn |
| Fan chỉ sáng một phần dải LED | `rgbctl leds 256` |
| Màn hình AIO trống | `systemctl --user status rgbctl-aio-temp`; thử `rgbctl aio-temp --once` |
| Màn hình AIO chớp `88` rồi tắt | thiết bị vừa khởi động lại; service tự kết nối lại sau vài giây |
| Không thấy icon tray | kiểm tra `gnome-extensions list --enabled \| grep appindicator`; chạy `rgbctl tray` trong terminal để xem lỗi |
| Lệnh `rgbctl` không tồn tại | thêm `~/.local/bin` vào `PATH` |

## Gỡ cài đặt

```sh
systemctl --user disable --now rgbctl-aio-temp
rm ~/.config/systemd/user/rgbctl-aio-temp.service \
   ~/.config/autostart/rgbctl-tray.desktop \
   ~/.local/share/applications/dev.hoan.rgbctl.desktop \
   ~/.local/share/icons/hicolor/scalable/apps/rgbctl.svg \
   ~/.local/share/icons/hicolor/symbolic/apps/rgbctl-symbolic.svg \
   ~/.local/bin/rgbctl
rm -r ~/.config/rgbctl
sudo rm /etc/udev/rules.d/60-rgbctl.rules /etc/modules-load.d/rgbctl.conf
sudo udevadm control --reload
# nếu đã thêm: xoá acpi_enforce_resources=lax trong /etc/default/grub rồi sudo update-grub
```

## Cấu trúc code

```
.
├── install.sh              # cài đặt cho user hiện tại
├── 60-rgbctl.rules         # udev: quyền truy cập thiết bị cho user đang đăng nhập
├── rgbctl.sh               # launcher (được symlink vào ~/.local/bin/rgbctl)
├── icons/                  # icon app (màu) + icon tray (symbolic)
└── rgbctl/
    ├── fusion.py           # Gigabyte RGB Fusion 2 / IT5711 qua hidraw
    ├── corsair_ram.py      # Corsair DDR5 qua SMBus
    ├── aio_display.py      # màn hình nhiệt độ AIO Jonsbo
    ├── core.py             # gộp hiệu ứng chung cho main + RAM, đọc/ghi config
    ├── cli.py              # dòng lệnh
    ├── gui.py              # cửa sổ GTK4
    └── tray.py             # icon tray (GTK3 + AyatanaAppIndicator)
```

## Ghi công

- [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB): protocol Gigabyte RGB Fusion 2 USB
  (`GigabyteRGBFusion2USBController`) và Corsair DRAM (`CorsairDRAMController`) được tham khảo
  từ source OpenRGB.
- [danieyal/jonsbolite](https://github.com/danieyal/jonsbolite): tài liệu reverse-engineering
  protocol màn hình Jonsbo `5131:2007`.
- [htkhiem/jonsbo-th-linux](https://github.com/htkhiem/jonsbo-th-linux): gợi ý ban đầu rằng
  `5131:2007` là màn hình nhiệt độ AIO.

Dùng với rủi ro của bạn: tool ghi trực tiếp vào phần cứng (USB HID, SMBus).
