# Acer Predator Triton 500 – RGB Keyboard Flicker Fix (Linux)

Fix on-key RGB Keyboard Flicker on Acer Predator Triton 500 (Linux / Ubuntu 24.04) – A systemd + Python fix to stop flickering, set a static color, and (new) drive full **per-key** custom RGB via USB HID. Works on boot and resume. Tested on PT515-52.

The fix talks to the RGB keyboard's USB HID controller directly via `pyusb`/`hidraw`, either to set a static palette color (default) or to light every key individually with an arbitrary color.

It runs automatically on boot and after waking from suspend or hibernate.

# Supported Keyboards: per-key RGB, not 4-zone 

This repo supports full per-key RGB control on Predator laptops with individually addressable keys.  
For 4-zone keyboards and Turbo button support, see the wonderfull [JafarAkhondali's acer-predator-turbo-and-rgb-keyboard-linux-module](https://github.com/JafarAkhondali/acer-predator-turbo-and-rgb-keyboard-linux-module).

---

## Background

The RGB keyboard on this laptop uses per-key RGB which starts in a chaotic blinking mode, which makes the laptop almost unusable with background lighting on.
It is also very unprofessional. This fix sends SET_REPORT commands to reinitialize a stable lighting configuration -- either one static color, or a fully custom per-key layout.

---

## Requirements

- only Python 3 with `pyusb` (Python USB library)
- systemd (used on most modern Linux systems)

## Auto-install-script

Just run this one-liner (and enter the sudo password + enter):

```bash
wget -O - https://raw.githubusercontent.com/francescopazzocco/Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix/color-brightness-options/install.sh | sudo bash
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
git clone https://github.com/francescopazzocco/Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix.git
cd Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix
```

#### 3. Copy the Python scripts

```bash
sudo cp predator-rgb-red.py /usr/local/bin/predator-rgb-red.py
sudo cp predator-rgb-fnkeys.py /usr/local/bin/predator-rgb-fnkeys.py
sudo cp perkey_rgb.py /usr/local/bin/predator-rgb-perkey.py
sudo chmod +x /usr/local/bin/predator-rgb-red.py /usr/local/bin/predator-rgb-fnkeys.py /usr/local/bin/predator-rgb-perkey.py
```

#### 4. Install the systemd services

```bash
sudo cp predator-rgb.service /etc/systemd/system/predator-rgb.service
sudo cp predator-rgb-fnkeys.service /etc/systemd/system/predator-rgb-fnkeys.service
sudo cp predator-rgb-perkey.service /etc/systemd/system/predator-rgb-perkey.service
```

#### 5. Enable and start the services

```bash
sudo systemctl daemon-reload
sudo systemctl enable predator-rgb.service predator-rgb-fnkeys.service predator-rgb-perkey.service
sudo systemctl start predator-rgb.service predator-rgb-fnkeys.service predator-rgb-perkey.service
```

#### 6. (Optional) Clean up the repo

```bash
cd ..
rm -rf Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix
```

---

## Choosing a static color

`predator-rgb-red.py` has no CLI -- edit the `COLOR_INDEX` constant near the
top of the file to one of the palette values below, then re-copy it to
`/usr/local/bin/predator-rgb-red.py` and run
`sudo systemctl restart predator-rgb.service`.

If you change `COLOR_INDEX`, also update it in `predator-rgb-fnkeys.py` (both
files hardcode it independently; on the unit this was tested on they are
intentionally different -- the boot-time static color is `0` (dark red) while
the Fn-key daemon's static fallback is `8` (red) -- keep them in sync only if
you actually want the same shade in both places).

## Per-key custom RGB

`perkey_rgb.py` (installed as `predator-rgb-perkey.py`) sets an arbitrary
color on any of the 87 keys whose firmware slot address has been mapped:

```bash
sudo predator-rgb-perkey.py --set esc=FF0000 --set a=00FF00 --set enter=0000FF
sudo predator-rgb-perkey.py --list-keys   # show all known keys
```

Every call sends the full 512-slot frame, so unset keys go dark -- each
invocation replaces the whole per-key display, it does not layer on top of
the previous one. Colors set this way are saved to
`/var/lib/predator-rgb/perkey_state.json`; `predator-rgb-perkey.service`
replays them automatically on boot and after resume (the keyboard forgets
custom per-key colors on its own on every suspend cycle), layered after
`predator-rgb.service` so they take priority over the static fallback.

See `perkey-capture-brief.md` for the full USB protocol writeup and how the
87-key slot map was derived.

## Fn+F7/F8 brightness keys

Once a static or per-key color is set, the keyboard firmware stops adjusting
its own brightness: pressing Fn+F7/F8 only emits a vendor HID report that the
Linux kernel does not map to any key, so the keys appear dead (on Windows,
PredatorSense listens for those reports and answers with a new lighting
command).

`predator-rgb-fnkeys.py`, installed as the `predator-rgb-fnkeys` systemd
service, restores them: it listens for the vendor reports and re-sends a
lighting command with the brightness stepped by `STEP = 10` up to a ceiling
of `MAX_BRIGHTNESS = 50` (on the tested unit the firmware already renders 50
at full brightness, so higher values would just be dead key presses). It
resends whichever payload matches the *currently active* lighting mode --
static or per-key -- read from `/var/lib/predator-rgb/mode` (written by
`predator-rgb-red.py` and `predator-rgb-perkey.py`); an earlier version
always resent the static payload regardless of mode, which silently
discarded custom per-key colors on every Fn+F7/F8 press. It also skips
resending when the brightness is already pinned at the floor or ceiling --
mashing/holding the key at a limit used to flood the firmware with identical
back-to-back writes and could reset it into a fallback "idle" animation.

The current brightness is saved to `/var/lib/predator-rgb/brightness` and
reused by `predator-rgb-red.py`/`predator-rgb-perkey.py` on the next
boot/resume, so it survives reboot and suspend.

### Firmware palette

As verified on a PT515-52 V1.10 (colors confirmed from photos, so they are actual
LED colors, not on-screen names). Your firmware revision may differ:

| Index | Color        |
|-------|--------------|
| 0     | dark red     |
| 1     | orange       |
| 2     | teal / cyan  |
| 3     | yellow-green |
| 4     | dark blue    |
| 5     | light green  |
| 6     | purple / indigo |
| 7     | white        |
| 8     | red          |

### Protocol notes

Static-color command: an 8-byte HID `SET_REPORT` (feature report `0x03`,
`bmRequestType 0x21`, `bRequest 0x09`, `wValue 0x0300`) on interface 3 of the
Darfon `0d62:7cb1` controller:

```
[0x08, 0x00, mode, 0x05, brightness, color, 0x00, checksum]
 mode:       0x01 = static
 brightness: 0x00-0x64 (0-100); on the tested unit everything from ~0x32 (50)
             up renders at maximum -- the usable range is effectively 0-50
 color:      palette index 0-8 (table above)
 checksum:   0xFF - (sum of the 7 preceding bytes)
```

Per-key custom RGB uses the same feature-report channel to enter mode `0x33`
plus a separate 512-byte frame (8 slots of 4 bytes each, `[0x00, R, G, B]`)
written as 8x64-byte packets to the interrupt OUT endpoint `0x06`. Full byte
layout, the required send sequence, and the 87-key slot map: see
`perkey-capture-brief.md` and `perkey_rgb.py`.

Once a color is set (static or per-key), pressing Fn+F7/F8 makes the
keyboard emit a vendor report on interface 2: report ID `0x04` followed by
`0x7d` (Fn+F7, brightness down) or `0x7c` (Fn+F8, brightness up). The
firmware takes no action on its own -- host software is expected to react
(see `predator-rgb-fnkeys.py`). Note that lighting commands can also be sent
through `/dev/hidraw*` of interface 3 with `HIDIOCSFEATURE` (report ID 0),
which does not require detaching the kernel driver like the pyusb route
does; the pyusb route (with detach) is only needed for the per-key frame,
which goes out over the interrupt endpoint rather than a feature report.

---

After installation, the RGB keyboard fix will be applied on boot and after resume from suspend or hibernate.
