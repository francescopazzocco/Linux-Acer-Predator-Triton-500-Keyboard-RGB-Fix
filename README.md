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

#### 3. Copy the Python script

```bash
sudo cp fix_keyboard.py /usr/local/bin/fix_keyboard.py
sudo chmod +x /usr/local/bin/fix_keyboard.py
```

#### 4. Install the systemd service

```bash
sudo cp fix-keyboard.service /etc/systemd/system/fix-keyboard.service
```

#### 5. Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable fix-keyboard.service
sudo systemctl start fix-keyboard.service
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
- `--brightness` — `0-100` (default `50`)
- `--wait` — seconds to wait for the USB device to appear, useful at boot (default `10`)

To make your choice permanent, add the arguments to `ExecStart=` in
`/etc/systemd/system/fix-keyboard.service` and run
`sudo systemctl daemon-reload && sudo systemctl restart fix-keyboard.service`.

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
 brightness: 0x00-0x64 (0-100)
 color:      palette index 0-8 (table above)
 checksum:   0xFF - (sum of the 7 preceding bytes)
```

Per-key addressing and custom RGB values likely exist in the firmware (index 0-8 are
presets) but have not been reverse-engineered yet — contributions welcome.

---

After installation, the RGB keyboard fix will be applied on boot and after resume from suspend or hibernate.


