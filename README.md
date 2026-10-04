<img src="icons/rgbctl.svg" width="96" align="right" alt="">

# jonsbo-aio-led-ubuntu (`rgbctl`)

Tool nhỏ, gọn để điều khiển LED và màn hình nhiệt độ AIO trên Ubuntu, **không cần OpenRGB**:

- **Fan + LED AIO Jonsbo** (cắm vào header ARGB của main Gigabyte)
- **LED trên main Gigabyte** (chip ITE IT5711 – RGB Fusion 2)
- **RAM Corsair Vengeance RGB DDR5**
- **Đèn trang trí trên card đồ hoạ Colorful** (đã thử: iGame RTX 5070 Battle-AX)
- **Màn hình nhiệt độ trên block AIO Jonsbo** (hiện nhiệt độ CPU)

Có 3 cách dùng: dòng lệnh (`rgbctl`), cửa sổ GTK4 và icon trên thanh trên cùng (tray).
Hiệu ứng thở / nháy / đổi màu **chạy đồng bộ** trên fan, AIO, RAM và card đồ hoạ. Viết bằng Python thuần,
nói chuyện trực tiếp với `/dev/hidraw*` và `/dev/i2c-*`. Cài bằng gói `.deb`.

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
- [Phát triển](#phát-triển)
- [Ghi công](#ghi-công)

---

## Phần cứng đã thử

| Thành phần | Model | Điều khiển qua |
|---|---|---|
| Mainboard | Gigabyte **B850M GAMING X WIFI6E** | — |
| Chip RGB trên main | ITE **IT5711** (`IT5711-GIGABYTE V1.0.19.6`), USB `048d:5711` | `/dev/hidraw*`, HID feature report `0xCC` |
| Fan case | Jonsbo ARGB (5V 3 pin) | header ARGB_V2_x của main |
| AIO | Jonsbo, LED ARGB + màn hình 2 số | LED: header ARGB của main · màn hình: USB `5131:2007` |
| RAM | Corsair Vengeance RGB DDR5 `CMH96GX5M2E6000C36` (2 thanh, fw 1.2.9, protocol 4) | SMBus AMD PIIX4, địa chỉ `0x18–0x1F` |
| Card đồ hoạ | Colorful iGame RTX 5070 Battle-AX (PCI `10de:2f04`, subsystem `7377:2000`) | I2C nội bộ của card (`NVIDIA i2c adapter 1`), địa chỉ `0x61` |
| CPU | AMD Ryzen 7 9700X | nhiệt độ đọc từ `k10temp` (Tctl) |
| OS | Ubuntu, GNOME (Wayland), kernel 7.0 | |

**Lưu ý:** thiết bị USB `5131:2007` hiện trong `lsusb` là *"MSR MSR-101U Mini HID magnetic card
reader"*. Đây là **nhầm tên** do VID/PID dùng chung: thật ra nó là màn hình nhiệt độ trên block
AIO (tên HID: `FBB`). Nó **không** điều khiển LED. LED của AIO và fan đều đi qua header ARGB
của main.

## Trạng thái tính năng

| Tính năng | Trạng thái |
|---|---|
| Fan/AIO/main/RAM: **Tĩnh, Tắt, Cầu vồng** (chip tự chạy) | ✅ đã kiểm chứng |
| Fan/AIO/main/RAM: **Thở** (daemon, đồng bộ mọi thiết bị) | ✅ đã kiểm chứng |
| Fan/AIO/main/RAM: **Nháy, Đổi màu** (daemon) | ⚠️ cùng cơ chế với Thở, chưa kiểm chứng bằng mắt |
| Card Colorful: **đặt màu, đổi màu toàn bộ** | ✅ đã kiểm chứng; đèn chỉ có một vùng màu nên "cầu vồng" trên card là đổi màu toàn bộ |
| Màn hình AIO hiện nhiệt độ CPU | ✅ đã kiểm chứng |
| Gói `.deb`, chuyển từ bản cài cũ | ✅ đã kiểm chứng |
| GUI GTK4 | ✅ |
| Icon tray | ⚠️ chạy được, chưa thử hết các mục menu |

RAM cần [bật SMBus](#bật-smbus-cho-ram-làm-1-lần) trước.

## Cài đặt

Yêu cầu: Ubuntu có GNOME (24.04 trở lên).

**Cách 1: tải gói có sẵn.** Vào trang
[Releases](https://github.com/HoanNguyen1711/jonsbo-aio-led-ubuntu/releases), tải
`rgbctl_<version>_all.deb`, rồi:

```sh
sudo apt install ./rgbctl_*_all.deb
```

**Cách 2: build từ source.**

```sh
git clone git@github.com:HoanNguyen1711/jonsbo-aio-led-ubuntu.git
cd jonsbo-aio-led-ubuntu
./install.sh        # build .deb, cài bằng apt, dọn bản cài cũ, khởi động daemon + tray
```

`apt` tự cài các gói phụ thuộc: `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-gtk-3.0` và
`gir1.2-ayatanaappindicator3-0.1`. Gói cuối là phần nối giữa Python và thư viện tray
`libayatana-appindicator` của hệ thống, chỉ khoảng 30 KB.

Gói cài các file sau:

| Đường dẫn | Tác dụng |
|---|---|
| `/usr/bin/rgbctl`, `/usr/lib/rgbctl/` | lệnh và code |
| `/usr/lib/udev/rules.d/60-rgbctl.rules` | cho user đang đăng nhập truy cập chip LED, SMBus khe RAM, bus I2C của card Colorful, màn hình AIO mà không cần sudo |
| `/usr/lib/modules-load.d/rgbctl.conf` | nạp `i2c-dev` khi khởi động |
| `/usr/lib/systemd/user/rgbctl-daemon.service` | daemon (bật sẵn cho mọi user): màn hình AIO + hiệu ứng đồng bộ |
| `/etc/xdg/autostart/rgbctl-tray.desktop` | tray tự chạy khi đăng nhập, áp dụng lại màu đã lưu |
| `/usr/share/applications/dev.hoan.rgbctl.desktop`, `/usr/share/icons/hicolor/…` | mục **RGB Control** trong menu ứng dụng và icon |

Sau khi cài, đăng xuất rồi đăng nhập lại (`install.sh` khởi động luôn nên không cần).

**Nâng cấp từ bản cài kiểu cũ** (`install.sh` trước 0.2, tạo symlink vào git clone): postinst
tự xoá file cũ trong `/etc`. Phần trong thư mục home thì chạy `rgbctl uninstall-legacy`
(`install.sh` mới tự gọi lệnh này).

### Bật SMBus cho RAM (làm 1 lần)

BIOS Gigabyte giữ vùng IO của SMBus, nên driver `i2c_piix4` không nhận được bus. Trong `dmesg`
sẽ thấy:

```
ACPI Warning: SystemIO range 0x0000000000000B00-0x0000000000000B08 conflicts with OpRegion ... (\GSA1.SMBI)
ACPI: OSL: Resource conflict; ACPI support missing from driver?
```

Cần thêm tham số kernel `acpi_enforce_resources=lax`. OpenRGB cũng yêu cầu y hệt. Gói `.deb`
**không** tự sửa tham số kernel, chỉ nhắc khi cài:

```sh
sudo cp /etc/default/grub /etc/default/grub.bak
sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="/&acpi_enforce_resources=lax /' /etc/default/grub
sudo update-grub
sudo reboot
```

Sau khi reboot:

```sh
rgbctl info
# Main : IT5711-GIGABYTE V1.0.19.6 (fw 1.0.19.6) tại /dev/hidraw6
# RAM  : 2 thanh Corsair (0x19, 0x1b)
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
rgbctl set breathing 00aaff           # thở, đồng bộ fan/AIO/RAM
rgbctl set static ff8800 -t ram       # chỉ RAM
rgbctl set rainbow -t argb1 -s 5      # chỉ header ARGB_V2_1, nhanh nhất
rgbctl set cycle -b 40                # đổi màu, độ sáng 40%
rgbctl off                            # tắt đèn
rgbctl apply                          # áp dụng lại config đã lưu
rgbctl aio-temp --once                # gửi nhiệt độ lên màn hình AIO một lần (để thử)
rgbctl leds 64                        # số LED tối đa mỗi header ARGB
rgbctl gui                            # mở cửa sổ
rgbctl tray &                         # icon trên thanh trên cùng
rgbctl daemon                         # tiến trình nền (bình thường do systemd chạy)
rgbctl --version
```

**Hiệu ứng:**

| Hiệu ứng | Ai chạy | Ghi chú |
|---|---|---|
| `static`, `rainbow`, `off` | chip trên từng thiết bị | vẫn chạy khi daemon tắt; riêng `rainbow` trên card đồ hoạ do daemon chạy |
| `breathing`, `flash`, `cycle` | daemon (~30 khung hình/giây) | đồng bộ hoàn toàn giữa fan, AIO, 2 thanh RAM, card đồ hoạ; đèn đứng yên nếu daemon tắt |

**Tuỳ chọn của `set` / `off`:**

| Tuỳ chọn | Ý nghĩa | Mặc định |
|---|---|---|
| `color` | màu hex, ví dụ `ff8800` (bỏ qua với `cycle`/`rainbow`) | `ffffff` |
| `-t, --target` | `all`, `mb`, `argb1`, `argb2`, `argb3`, `board`, `ram`, `gpu` | `all` |
| `-s, --speed` | 1 (chậm) … 5 (nhanh) | 3 |
| `-b, --brightness` | 0 … 100 | 100 |
| `--flash` | ghi vào flash của main, nên màu giữ cả lúc boot trước khi đăng nhập (chỉ với `static`/`rainbow`/`off`) | tắt |
| `--no-save` | không ghi vào config (không dùng được với hiệu ứng của daemon) | tắt |

**Target:**

| Target | Gồm |
|---|---|
| `all` | `mb` + `ram` + `gpu` |
| `mb` | mọi vùng trên main: 3 header ARGB + LED onboard |
| `argb1` / `argb2` / `argb3` | header ARGB_V2_1 / _2 / _3 |
| `board` | LED onboard (Chipset Accent, LED_C) |
| `ram` | tất cả thanh RAM Corsair tìm thấy |
| `gpu` | đèn trang trí trên card đồ hoạ Colorful |

> `--flash` ghi vào bộ nhớ flash của chip trên main. Flash có giới hạn số lần ghi, nên chỉ dùng
> khi đã chốt màu, đừng dùng trong script chạy liên tục.

### GUI

`rgbctl gui`, hoặc mở **RGB Control** trong menu ứng dụng. Mở app thì tray cũng tự bật.

```
Thiết bị   [✓] Fan + AIO   [✓] RAM   [✓] Card đồ hoạ
Hiệu ứng   [ Cầu vồng ▾ ]
Màu        [■]  ● ● ● ● ● ● ● ● ●
Tốc độ     ───●───
Độ sáng    ──────●
           [ Lưu vào main ]
```

- **Mọi thay đổi áp dụng ngay** cho các thiết bị đang tick. Thanh kéo chờ dừng tay ~0,3 giây.
- Tick thêm một thiết bị thì nó nhận hiệu ứng đang chọn; bỏ tick thì nó giữ nguyên trạng thái.
  "Fan + AIO" gồm cả 3 header ARGB và LED trên main (chỉnh riêng từng header: CLI `-t argb1`…).
- Ô màu mờ đi với Đổi màu / Cầu vồng / Tắt; tốc độ mờ đi với Tĩnh / Tắt.
- **Lưu vào main**: ghi hiệu ứng của Fan + AIO vào flash của mainboard (tương đương `--flash`),
  chỉ bấm được với Tĩnh / Cầu vồng / Tắt.
- Mục **Màn hình AIO**: công tắc **Hiển thị** bật/tắt việc gửi nhiệt độ lên màn hình.

### Tray

Tự chạy khi đăng nhập, hoặc chạy tay `rgbctl tray &`. Menu gồm:

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

Cần extension **Ubuntu AppIndicators** (Ubuntu bật sẵn).

### Daemon

`rgbctl-daemon` (systemd user service) làm 2 việc:

1. **Màn hình AIO:** màn hình không tự đo nhiệt độ, nên daemon gửi nhiệt độ CPU 5 lần/giây.
   Không có ai gửi thì màn hình trống.
2. **Hiệu ứng thở / nháy / đổi màu:** tính màu theo một đồng hồ chung rồi gửi cho fan, AIO,
   LED main (lệnh "tĩnh + màu" của IT5711, 30 lần/giây), RAM (chế độ direct của Corsair,
   30 lần/giây) và card đồ hoạ (12 lần/giây). Tốn khoảng 8% một nhân CPU khi đang chạy hiệu ứng,
   gần như 0 khi không.

Daemon đọc lại config mỗi khi file đổi, nên đổi màu trong GUI/tray/CLI là có tác dụng ngay.
Khi không có hiệu ứng nào cần chạy, daemon chỉ thức 5 lần/giây cho màn hình AIO.

```sh
systemctl --user status rgbctl-daemon
journalctl --user -u rgbctl-daemon
```

Chữ **CPU** và **JONSBO** trên màn hình AIO là in cố định. Đã thử byte đơn vị (°C/°F) và byte
chế độ hiển thị trong protocol: màn hình này bỏ qua, chỉ hiện được một số 2 chữ số.

## Config

`~/.config/rgbctl/config.json`. GUI, tray và lệnh `set` tự ghi vào file này. Tray (lúc đăng
nhập), `rgbctl apply` và daemon đọc nó.

```json
{
  "mb":  { "mode": "breathing", "color": "ff0000", "speed": 3, "brightness": 100 },
  "ram": { "mode": "breathing", "color": "ff0000", "speed": 3, "brightness": 100 },
  "aio": { "enabled": true }
}
```

Có thể thêm `argb1`, `argb2`, `argb3`, `board` để đặt riêng từng header. Khi áp dụng, `mb`
chạy trước để các header riêng ghi đè lên. Đặt lại `mb` sẽ xoá các mục riêng lẻ đó.

## Cách hoạt động / protocol

### Gigabyte RGB Fusion 2 – ITE IT5711 (`rgbctl/fusion.py`)

- Interface HID vendor, usage page `0xFF89`. Mọi lệnh là **feature report 64 byte**, byte đầu
  là report ID `0xCC`. Gửi qua `ioctl(HIDIOCSFEATURE)` trên `/dev/hidrawN`.
- `CC 60` / `CC 61`, rồi đọc feature report: thông tin chip (tên, firmware, số LED mỗi header,
  thứ tự màu từng header). Trên máy này thứ tự màu của dải ARGB là **GRB**.
- `CC 20+n …`: hiệu ứng phần cứng cho vùng `n`. Gói gồm loại hiệu ứng, độ sáng, màu
  (`0x00RRGGBB`), 4 chu kỳ thời gian và 4 tham số. Sau đó gửi `CC 28 <mask>` để áp dụng.
  - Vùng trên B850M GAMING X WIFI6E: `argb1`=5, `argb2`=6, `argb3`=7, Chipset Accent=2, LED_C=4.
- `CC 32 <mask>`: header ARGB nào có bit = 1 thì chạy chế độ direct (máy gửi màu từng LED qua
  `CC 58/59/62`, tối đa 19 LED mỗi gói), còn lại chạy hiệu ứng của chip. rgbctl luôn để mask = 0:
  hiệu ứng phần mềm được tô bằng lệnh "tĩnh + màu" cho cả 5 vùng một lượt (~25 ms), nhanh hơn
  direct (~93 ms/khung cho 3 header × 64 LED) và không làm đèn chớp khi chuyển từ cầu vồng sang.
- `CC 34 …`: số LED tối đa mỗi header.
- `CC 47 1` + `CC 5E`: lưu trạng thái vào flash.

**Hai điều phát hiện trên chip này, khác với OpenRGB:**

1. Chip xuất xưởng để **số LED mỗi header = 0**. Khi đó hiệu ứng phần cứng *tắt hết* đèn ARGB,
   dù chế độ direct vẫn sáng. OpenRGB coi giá trị 0 là "32 LED". Tool tự đặt 64 trước khi gửi
   hiệu ứng nếu đang là 0.
2. Hiệu ứng **Wave (6)** cũng làm tắt đèn. Cầu vồng chạy được với **Wave 4 (12)**, nên
   `rainbow` dùng mã 12.

### Corsair Vengeance RGB DDR5 (`rgbctl/corsair_ram.py`)

- SMBus qua `/dev/i2c-N` (`ioctl I2C_SMBUS`). Chỉ quét `0x18–0x1F`. Nhận diện bằng thanh ghi
  `0x43 ∈ {1A,1B,1C}` và `0x44 ∈ {01,03,04}`.
- Đặt hiệu ứng: reset buffer (`0x0B`), bắt đầu (`0x21`), ghi 20 byte cấu hình qua `0x20`, đọc
  checksum CRC-8 ở `0x42` để so, khớp thì ghi `0x82 = 1` để áp dụng. Lệch thì thử lại tối đa 3 lần.
- **Chế độ tĩnh (`0x10`) không lấy màu trong gói hiệu ứng** mà lấy từ bộ đệm màu từng LED:
  ghi `10 LED × (R, G, B, FF)` theo cùng cách trên rồi `0x82 = 2`. Thiếu bước này RAM sáng
  trắng (màu mặc định). "Tắt" là chế độ tĩnh với màu đen.
- **Chế độ direct** (protocol ≥ 4): ghi một khối SMBus 32 byte `[10, R,G,B × 10, CRC-8]` vào
  `0x31`. Mất khoảng 4 ms mỗi thanh, nên daemon chạy được 30 khung hình/giây.

### Card đồ hoạ Colorful (`rgbctl/colorful_gpu.py`)

- Chip LED ở địa chỉ `0x61` trên bus I2C nội bộ của card (`NVIDIA i2c adapter 1`). Bus được
  tìm theo tên và mã PCI (`10de` + subsystem vendor `7377` của Colorful), không theo số `i2c-N`
  vì số này đổi sau mỗi lần khởi động.
- Nhận diện (protocol của OpenRGB `ColorfulGPUController`): đọc thử 1 byte xem có chip không,
  rồi ghi `AA EF 81 02 1C 02`, chip đúng trả về `AA EF 81 …`.
- Đặt màu: `AA EF 12 03 01 FF R G B` + tổng các byte (16 bit, little endian).
- Gói màu từng LED của dòng Vulcan/Neptune (`AA EF 01 04 88 26` + 38 LED) bị chip trên Battle-AX
  bỏ qua, nên đèn chỉ có một vùng màu. Hiệu ứng mặc định (đỏ chớp) do chip chạy nhưng lệnh của
  nó chưa được giải mã; mọi hiệu ứng động trên card do daemon gửi màu liên tục (~18 lệnh/giây
  đã thử ổn định).
- Bus này còn có chip điều áp của card: chỉ ghi vào `0x61`, và chỉ sau khi nhận diện đúng chip.
  Địa chỉ `0x50` (card đời 20) không bao giờ được thử vì trên bus nối ra màn hình đó là EEPROM EDID.

### Màn hình AIO Jonsbo (`rgbctl/aio_display.py`)

- USB HID `5131:2007`, tên `FBB`, usage page `0xFF00`, **không có report ID**, output report
  64 byte.
- Khung tin: `00 01 02 <nhiệt độ> <phần trăm> <đơn vị> 00 …`. Ghi vào hidraw với một byte
  `0x00` đứng đầu (report ID rỗng, kernel bỏ byte này), gửi lại mỗi 200 ms.
- Nhiệt độ đọc từ `k10temp` `temp1_input` (Tctl).

### Daemon (`rgbctl/daemon.py`, `rgbctl/effects.py`)

- Driver NVIDIA chờ bus I2C bằng cách chạy CPU suốt lúc truyền (~3.3 ms CPU mỗi lệnh), nên card
  đồ hoạ chỉ được cập nhật 12 lần/giây thay vì 30.

- Chip trên main và chip trên RAM có đồng hồ riêng, nên hiệu ứng phần cứng không bao giờ khớp
  nhau. Hai thanh RAM được ghi lần lượt nên cũng lệch pha. Vì vậy thở / nháy / đổi màu được tính
  trong `effects.py` theo `time.time()` và gửi cho mọi thiết bị trong cùng một khung hình.
- Chỉ gửi khi màu đổi. Thiết bị lỗi (rút ra, sleep/resume) thì 10 giây sau mở lại.
- Chống chạy trùng bằng `flock` trên `$XDG_RUNTIME_DIR/rgbctl-daemon.lock`. Tray chờ 10 giây
  mới tự chạy daemon (dự phòng), để service systemd luôn giữ khoá trước.
- Khi đổi sang hiệu ứng phần cứng, CLI/GUI/tray lưu config trước, chờ 150 ms cho daemon thôi gửi
  rồi mới ghi vào chip. Config được ghi kiểu atomic (file tạm + `rename`).

## Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| `Permission denied: '/dev/hidrawN'` | đăng xuất/đăng nhập lại sau khi cài gói; hoặc `sudo udevadm trigger` |
| `RAM : Không thấy SMBus PIIX4` | chưa thêm `acpi_enforce_resources=lax`, xem [phần trên](#bật-smbus-cho-ram-làm-1-lần) |
| `GPU : Không tìm thấy đèn card Colorful` | card không phải Colorful, hoặc driver NVIDIA không mở bus I2C (`ls /sys/class/i2c-dev/*/name` phải có "NVIDIA i2c adapter") |
| `RAM : Không tìm thấy thanh RAM Corsair RGB nào` | thử `sudo apt install i2c-tools && sudo i2cdetect -y <bus>` để xem địa chỉ nào trả lời |
| Đặt hiệu ứng xong fan/AIO tắt hẳn | báo lại hiệu ứng nào (xem mục phát hiện ở trên). Thử `rgbctl set static ff0000 -t mb` để chắc kết nối vẫn ổn |
| Thở/nháy/đổi màu đứng yên | daemon không chạy: `systemctl --user status rgbctl-daemon` |
| Fan chỉ sáng một phần dải LED | `rgbctl leds 256` |
| Màn hình AIO trống | `systemctl --user status rgbctl-daemon`; thử `rgbctl aio-temp --once` |
| Màn hình AIO chớp `88` rồi tắt | thiết bị vừa khởi động lại; daemon tự mở lại sau vài giây |
| Không thấy icon tray | kiểm tra `gnome-extensions list --enabled \| grep appindicator`; chạy `rgbctl tray` trong terminal để xem lỗi |
| Tray / daemon chạy 2 lần sau khi nâng cấp | `rgbctl uninstall-legacy` rồi đăng nhập lại |

## Gỡ cài đặt

```sh
sudo apt remove rgbctl
rm -r ~/.config/rgbctl        # nếu muốn xoá cả config
# nếu đã thêm: xoá acpi_enforce_resources=lax trong /etc/default/grub rồi sudo update-grub
```

## Phát triển

Chạy thẳng từ git clone, không cần cài: `./rgbctl.sh <lệnh>`. Muốn đọc/ghi thiết bị mà chưa cài
gói (chưa có udev rule) thì cần `sudo`. GUI và tray không chạy được bằng sudo trên Wayland.

```
.
├── build-deb.sh            # build dist/rgbctl_<version>_all.deb (chỉ cần dpkg-deb)
├── install.sh              # build + apt install + dọn bản cài cũ
├── rgbctl.sh               # chạy từ git clone
├── icons/                  # icon app (màu) + icon tray (symbolic)
├── packaging/              # control, postinst/prerm/postrm, udev rule, .desktop, service
├── .github/workflows/      # CI: build .deb mỗi lần push; tag v* thì tạo Release
└── rgbctl/
    ├── fusion.py           # Gigabyte RGB Fusion 2 / IT5711 qua hidraw
    ├── corsair_ram.py      # Corsair DDR5 qua SMBus
    ├── colorful_gpu.py     # đèn card đồ hoạ Colorful qua I2C của card
    ├── aio_display.py      # màn hình nhiệt độ AIO Jonsbo
    ├── effects.py          # hiệu ứng do phần mềm tính (thở / nháy / đổi màu)
    ├── daemon.py           # tiến trình nền: màn hình AIO + hiệu ứng đồng bộ
    ├── core.py             # gộp hiệu ứng cho main + RAM, đọc/ghi config
    ├── cli.py              # dòng lệnh
    ├── gui.py              # cửa sổ GTK4
    ├── tray.py             # icon tray (GTK3 + AyatanaAppIndicator)
    └── legacy.py           # dọn bản cài kiểu cũ
```

**Ra bản mới:**

1. Sửa `__version__` trong `rgbctl/__init__.py`, ví dụ `0.3.0`.
2. Commit, rồi `git tag v0.3.0 && git push --tags`.
3. GitHub Actions build `.deb` và tạo Release kèm file. Tag khác version trong code thì job báo lỗi.

## Ghi công

- [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB): protocol Gigabyte RGB Fusion 2 USB
  (`GigabyteRGBFusion2USBController`), Corsair DRAM (`CorsairDRAMController`) và Colorful GPU
  (`ColorfulGPUController`) được tham khảo từ source OpenRGB.
- [danieyal/jonsbolite](https://github.com/danieyal/jonsbolite): tài liệu reverse-engineering
  protocol màn hình Jonsbo `5131:2007`.
- [htkhiem/jonsbo-th-linux](https://github.com/htkhiem/jonsbo-th-linux): gợi ý ban đầu rằng
  `5131:2007` là màn hình nhiệt độ AIO.

Dùng với rủi ro của bạn: tool ghi trực tiếp vào phần cứng (USB HID, SMBus).
