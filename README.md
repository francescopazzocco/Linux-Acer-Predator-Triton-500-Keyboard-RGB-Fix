# Acer Predator Triton 500 – RGB Keyboard Flicker Fix (Linux)

Fix on-key RGB Keyboard Flicker on Acer Predator Triton 500 (Linux / Ubuntu 24.04) – A systemd + Python script to stop flickering and initialize RGB lighting via USB HID. Works on boot and resume. Tested on PT515-52.

This script fixes the keyboard flickering issue on the **Acer Predator Triton 500 (PT515-52)** when running Linux. 

The fix sends a custom USB HID command to the RGB keyboard via `pyusb` and sets a static color (a palette preset with brightness of your choice, see below).

It runs automatically on boot and after waking from suspend or hibernate.

# Supported Keyboards: per-key RGB, not 4-zone 

This repo supports full per-key RGB control on Predator laptops with individually addressable keys.  
For 4-zone keyboards and Turbo button support, see the wonderfull [JafarAkhondali's acer-predator-turbo-and-rgb-keyboard-linux-module](https://github.com/JafarAkhondali/acer-predator-turbo-and-rgb-keyboard-linux-module).

---

## Background

The RGB keyboard on this laptop uses a per-key RGB which start in a chaotic blinking mode, which makes the laptop almost unsusable with background lighting on.
It is also very unprofessional. This script sends a SET_REPORT command to reinitialize a stable static lighting configuration.

---

## Requirements

- only Python 3 with `pyusb` (Python USB library)
- systemd (used on most modern Linux systems)

## Auto-install-script

Just run this one-liner (and enter the sudo password + enter):

```bash
wget -O - https://raw.githubusercontent.com/DoStraTech/Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix/main/install.sh | sudo bash
```


### Manual Installation

If you don't trust random scripts from internet that ask you to sudo...
You can also install the fix manually by following these steps:

#### 1. Install dependencies

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-usb
```

#### 2. Clone the repository

```bash
git clone https://github.com/DoStraTech/Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix.git
cd Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix
```

#### 3. Copy the Python scripts

```bash
sudo cp fix_keyboard.py /usr/local/bin/fix_keyboard.py
sudo cp fn_brightness.py /usr/local/bin/fn_brightness.py
sudo chmod +x /usr/local/bin/fix_keyboard.py /usr/local/bin/fn_brightness.py
```

#### 4. Install the systemd services

```bash
sudo cp fix-keyboard.service /etc/systemd/system/fix-keyboard.service
sudo cp fn-brightness.service /etc/systemd/system/fn-brightness.service
```

#### 5. Enable and start the services

```bash
sudo systemctl daemon-reload
sudo systemctl enable fix-keyboard.service fn-brightness.service
sudo systemctl start fix-keyboard.service fn-brightness.service
```

#### 6. (Optional) Clean up the repo

```bash
cd ..
rm -rf Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix
```

---

## Choosing color and brightness

`fix_keyboard.py` accepts optional arguments (defaults reproduce the original behavior):

```bash
sudo fix_keyboard.py --color red --brightness 100
```

- `--color` — palette preset, by name or index `0-8`
- `--brightness` — `0-100` (default: last value set with Fn+F7/F8, or `50`)
- `--wait` — seconds to wait for the USB device to appear, useful at boot (default `10`)

To make your choice permanent, add the arguments to `ExecStart=` in
`/etc/systemd/system/fix-keyboard.service` and run
`sudo systemctl daemon-reload && sudo systemctl restart fix-keyboard.service`.
If you change the color, pass the same `--color` to `fn-brightness.service` too
(see below).

## Fn+F7/F8 brightness keys

Once a static color is set, the keyboard firmware stops adjusting its own
brightness: pressing Fn+F7/F8 only emits a vendor HID report that the Linux
kernel does not map to any key, so the keys appear dead (on Windows,
PredatorSense listens for those reports and answers with a new lighting
command).

`fn_brightness.py`, installed as the `fn-brightness` systemd service, restores
them: it listens for the vendor reports and re-sends the lighting command with
the brightness stepped by ±10 up to a ceiling of 50 (tune with `--step` and
`--max`; on the tested unit the firmware already renders 50 at full brightness,
so higher values would just be dead key presses). The chosen brightness is
saved to `/var/lib/fix-keyboard/brightness` and reused by `fix_keyboard.py` on
the next boot/resume, so it survives reboot and suspend unless an explicit
`--brightness` overrides it.

The daemon re-sends color `1` (orange) by default — if you changed the color,
add the same `--color` to `ExecStart=` in
`/etc/systemd/system/fn-brightness.service` as well.

### Firmware palette

As verified on a PT515-52 V1.10 (colors confirmed from photos, so they are actual
LED colors, not on-screen names). Your firmware revision may differ:

| Index | Name          | Color        |
|-------|---------------|--------------|
| 0     | `darkred`     | dark red     |
| 1     | `orange`      | orange (the project's original default) |
| 2     | `teal`        | teal / cyan  |
| 3     | `yellowgreen` | yellow-green |
| 4     | `blue`        | dark blue    |
| 5     | `green`       | light green  |
| 6     | `purple`      | purple / indigo |
| 7     | `white`       | white        |
| 8     | `red`         | red          |

### Protocol notes

The command is an 8-byte HID `SET_REPORT` (feature report `0x03`, `bmRequestType 0x21`,
`bRequest 0x09`, `wValue 0x0300`) on interface 3 of the Darfon `0d62:7cb1` controller:

```
[0x08, 0x00, mode, 0x05, brightness, color, 0x00, checksum]
 mode:       0x01 = static
 brightness: 0x00-0x64 (0-100); on the tested unit everything from ~0x32 (50)
             up renders at maximum — the usable range is effectively 0-50
 color:      palette index 0-8 (table above)
 checksum:   0xFF - (sum of the 7 preceding bytes)
```

Once a static color is set, pressing Fn+F7/F8 makes the keyboard emit a vendor
report on interface 2: report ID `0x04` followed by `0x7d` (Fn+F7, brightness
down) or `0x7c` (Fn+F8, brightness up). The firmware takes no action on its
own — host software is expected to react (see `fn_brightness.py`). Note that
lighting commands can also be sent through `/dev/hidraw*` of interface 3 with
`HIDIOCSFEATURE` (report ID 0), which does not require detaching the kernel
driver like the pyusb route does.

Per-key addressing and custom RGB values likely exist in the firmware (index 0-8 are
presets) but have not been reverse-engineered yet — contributions welcome.

---

After installation, the RGB keyboard fix will be applied on boot and after resume from suspend or hibernate.


