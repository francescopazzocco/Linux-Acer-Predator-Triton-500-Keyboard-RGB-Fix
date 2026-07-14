#!/usr/bin/env python3
# Initializes the per-key RGB keyboard (Darfon 0d62:7cb1) on the Acer
# Predator Triton 500 (PT515-52) with a static color, stopping the
# chaotic blinking it boots with.
#
# Payload layout (8-byte HID SET_REPORT, feature report, interface 3):
#   [0x08, 0x00, mode, 0x05, brightness, color, 0x00, checksum]
#     mode:       0x01 = static
#     brightness: 0-100 (0x00-0x64)
#     color:      firmware palette index, see COLORS below
#     checksum:   0xFF - (sum of the 7 preceding bytes)
#
# Without arguments it sends the same payload this project always sent
# (color 1, brightness 50), so existing installs keep working unchanged.

import argparse
import sys
import time

import usb.core
import usb.util

VENDOR_ID = 0x0d62
PRODUCT_ID = 0x7cb1
INTERFACE = 3

# Last brightness chosen with the Fn+F7/F8 keys (written by fn_brightness.py)
STATE_FILE = "/var/lib/fix-keyboard/brightness"

# Palette indexes as verified on a PT515-52 V1.10 (photos analyzed for
# true RGB values). May vary with keyboard firmware revision.
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


def non_negative_int(value):
    seconds = int(value)
    if seconds < 0:
        raise argparse.ArgumentTypeError("--wait must be a non-negative integer")
    return seconds


def main():
    parser = argparse.ArgumentParser(
        description="Set static color/brightness on the Triton 500 per-key RGB keyboard.")
    parser.add_argument("--color", type=parse_color, default=1,
                        help="palette color, by name or index 0-8 (default: 1 = orange)")
    parser.add_argument("--brightness", type=int, default=None, choices=range(0, 101),
                        metavar="0-100",
                        help="backlight brightness (default: last value set with "
                             "Fn+F7/F8 if fn_brightness.py is installed, else 50)")
    parser.add_argument("--wait", type=non_negative_int, default=10, metavar="SECONDS",
                        help="seconds to wait for the USB device, useful at boot; "
                             "0 = single immediate attempt (default: 10)")
    args = parser.parse_args()

    if args.brightness is None:
        try:
            with open(STATE_FILE) as f:
                args.brightness = min(100, max(0, int(f.read().strip())))
        except (OSError, ValueError):
            args.brightness = 50

    dev = None
    # always attempt at least once; --wait 0 means a single immediate attempt
    for _ in range(max(args.wait, 1)):
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is not None:
            break
        time.sleep(1)
    if dev is None:
        sys.exit(f"keyboard {VENDOR_ID:04x}:{PRODUCT_ID:04x} not found")

    payload = [0x08, 0x00, 0x01, 0x05, args.brightness, args.color, 0x00]
    payload.append((0xFF - sum(payload)) & 0xFF)

    if dev.is_kernel_driver_active(INTERFACE):
        dev.detach_kernel_driver(INTERFACE)
    usb.util.claim_interface(dev, INTERFACE)
    dev.ctrl_transfer(0x21, 0x09, 0x0300, INTERFACE, bytes(payload))
    usb.util.release_interface(dev, INTERFACE)
    # Reattach the kernel driver: the EC routes the Fn brightness keys
    # through this interface, and they stop working if it stays detached.
    try:
        dev.attach_kernel_driver(INTERFACE)
    except usb.core.USBError:
        pass


if __name__ == "__main__":
    main()
