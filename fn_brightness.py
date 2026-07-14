#!/usr/bin/env python3
# Restores the Fn+F7/F8 keyboard-backlight brightness keys on the Acer
# Predator Triton 500 (PT515-52).
#
# Once a static color has been set (see fix_keyboard.py) the keyboard
# firmware no longer adjusts its own brightness. Pressing Fn+F7/F8 only
# emits a vendor report on USB interface 2 -- report ID 0x04, byte 0x7d
# for brightness down (Fn+F7) or 0x7c for up (Fn+F8) -- which the kernel
# does not map to any key. On Windows, PredatorSense listens for these
# reports and answers with a new lighting command; this daemon does the
# same on Linux: it re-sends the static-color payload with the adjusted
# brightness via HIDIOCSFEATURE on interface 3 (which, unlike the pyusb
# route, needs no kernel-driver detach).
#
# The current brightness persists in /var/lib/fix-keyboard/brightness and
# fix_keyboard.py picks it up on the next boot/resume.

import argparse
import fcntl
import glob
import os
import sys

VENDOR_ID = 0x0d62
PRODUCT_ID = 0x7cb1
EVENTS_INTERFACE = 2   # Fn key vendor reports arrive here
CONTROL_INTERFACE = 3  # lighting commands go here

KEY_DOWN, KEY_UP = 0x7D, 0x7C  # Fn+F7, Fn+F8 (as labeled on the keyboard)

STATE_FILE = "/var/lib/fix-keyboard/brightness"

# Same palette as fix_keyboard.py; keep --color in sync between the two
# services if you changed it.
COLORS = {
    "darkred": 0,
    "orange": 1,
    "teal": 2,
    "yellowgreen": 3,
    "blue": 4,
    "green": 5,
    "purple": 6,
    "white": 7,
    "red": 8,
}


def parse_color(value):
    if value in COLORS:
        return COLORS[value]
    try:
        index = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"unknown color {value!r}; use 0-8 or one of: {', '.join(COLORS)}")
    if not 0 <= index <= 8:
        raise argparse.ArgumentTypeError("color index must be 0-8")
    return index


def positive_int(value):
    step = int(value)
    if step <= 0:
        raise argparse.ArgumentTypeError("--step must be a positive integer")
    return step


def find_hidraw(interface):
    for dev in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(f"{dev}/device/uevent").read().upper()
        except OSError:
            continue
        if f"{VENDOR_ID:08X}:{PRODUCT_ID:08X}" in uevent:
            path = os.path.realpath(f"{dev}/device")
            if f":1.{interface}/" in path + "/":
                return f"/dev/{os.path.basename(dev)}"
    return None


def send_rgb(ctrl, color, brightness):
    payload = [0x08, 0x00, 0x01, 0x05, brightness, color, 0x00]
    payload.append((0xFF - sum(payload)) & 0xFF)
    buf = bytes([0x00]) + bytes(payload)  # report ID 0 + 8-byte payload
    # HIDIOCSFEATURE(len) = _IOC(_IOC_READ|_IOC_WRITE, 'H', 0x06, len)
    fcntl.ioctl(ctrl, (3 << 30) | (len(buf) << 16) | (0x48 << 8) | 0x06, buf)


def load_brightness():
    try:
        return min(100, max(0, int(open(STATE_FILE).read().strip())))
    except (OSError, ValueError):
        return 50


def save_brightness(value):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(f"{value}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Handle the Fn+F7/F8 keyboard brightness keys.")
    parser.add_argument("--color", type=parse_color, default=1,
                        help="palette color to re-send, by name or index 0-8 "
                             "(default: 1 = orange; keep in sync with fix_keyboard.py)")
    parser.add_argument("--step", type=positive_int, default=10, metavar="PERCENT",
                        help="brightness change per key press (default: 10)")
    parser.add_argument("--max", dest="max_brightness", type=positive_int, default=50,
                        metavar="PERCENT",
                        help="brightness ceiling (default: 50 — on the tested unit the "
                             "firmware already renders 50 at full brightness, values up "
                             "to 100 are accepted but look identical)")
    args = parser.parse_args()
    if args.max_brightness > 100:
        parser.error("--max cannot exceed 100")

    events_path = find_hidraw(EVENTS_INTERFACE)
    ctrl_path = find_hidraw(CONTROL_INTERFACE)
    if not events_path or not ctrl_path:
        sys.exit(f"keyboard {VENDOR_ID:04x}:{PRODUCT_ID:04x} not found")

    brightness = load_brightness()
    with open(events_path, "rb", buffering=0) as events, \
         open(ctrl_path, "wb", buffering=0) as ctrl:
        while True:
            report = events.read(64)
            if not report:
                sys.exit(1)  # device gone; let systemd restart us
            if report[0] == 0x04 and len(report) >= 2 and report[1] in (KEY_UP, KEY_DOWN):
                if report[1] == KEY_UP:
                    brightness = min(args.max_brightness, brightness + args.step)
                else:
                    brightness = max(0, brightness - args.step)
                send_rgb(ctrl, args.color, brightness)
                save_brightness(brightness)


if __name__ == "__main__":
    main()
