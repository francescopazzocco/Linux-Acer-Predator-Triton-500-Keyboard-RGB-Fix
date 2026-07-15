#!/usr/bin/env python3
# Sets per-key RGB colors on the Triton 500 per-key keyboard (Darfon
# 0d62:7cb1), for the subset of keys whose firmware slot address is known
# (see KEY_SLOTS below). Reverse-engineered from a Windows/PredatorSense USB
# capture plus a direct Linux sweep; see perkey-capture-brief.md.
#
# Frame layout (interface 3, endpoint 0x06 OUT, 8x64-byte interrupt
# transfers = one 512-byte buffer of 128 slots):
#   slot = [0x00(pad), R, G, B]   -- pad-first, NOT pad-last
# Unaddressed slots must stay 0x00000000; never write 0x00AEC7 (the
# firmware's internal "unassigned slot" sentinel -- doing so causes visible
# flicker across many unrelated slots).
#
# Required send sequence (all via pyusb; plain hidraw write() silently
# no-ops the Output report on this device):
#   1. feature report 12 00 00 08 00 00 00 e5  (undecoded, but required)
#   2. feature report 08 00 33 05 <brightness> 01 01 <checksum>  (enters
#      per-key render mode)
#   3. the 512-byte frame, 8x64B interrupt-OUT writes to endpoint 0x06

import argparse
import json
import os
import sys
import time

import usb.core
import usb.util

VENDOR_ID = 0x0d62
PRODUCT_ID = 0x7cb1
INTERFACE = 3
OUT_ENDPOINT = 0x06
NUM_SLOTS = 128

FORBIDDEN = (0x00, 0xAE, 0xC7)  # firmware's "unassigned slot" sentinel - never write this

# Last per-key colors successfully applied, so --replay can restore them
# after suspend/resume or reboot (the keyboard forgets custom per-key state
# on its own -- only the palette-based static color in fix_keyboard.py
# survives that). Same /var/lib/predator-rgb directory the locally deployed
# brightness state file already uses.
STATE_FILE = "/var/lib/predator-rgb/perkey_state.json"

# Confirmed via a full 0-127 Linux sweep, cross-validated against the
# earlier partial round-based sweep (they agree on every slot both covered),
# plus a targeted re-check of the handful of slots that disagreed between
# sessions (57, 67, 82, 95, 99). Slots 108-127 confirmed entirely unused
# (padding). Side is unconfirmed for "alt" (only one of the two Alt keys was
# found; AltGr is separately confirmed at slot 60).
KEY_SLOTS = {
    "esc": 5, "tab": 3, "capslock": 2, "fn": 6,
    "ctrl_left": 0, "ctrl_right": 78, "alt": 18, "alt_gr": 60,
    "shift_left": 1, "shift_right": 85,
    "space": 24, "enter": 86, "backspace": 82, "delete": 95,
    "0": 64, "1": 10, "2": 16, "3": 22, "4": 28, "5": 34, "6": 40,
    "7": 46, "8": 52, "9": 58,
    "a": 20, "b": 41, "c": 31, "d": 32, "e": 27, "f": 38, "g": 44,
    "h": 50, "i": 57, "j": 56, "k": 62, "l": 68, "m": 55, "n": 49,
    "o": 63, "p": 69, "q": 15, "r": 33, "s": 26, "t": 39, "u": 51,
    "v": 37, "w": 21, "x": 25, "y": 45, "z": 19,
    "f1": 11, "f2": 17, "f3": 23, "f4": 29, "f5": 35, "f6": 43,
    "f7": 47, "f8": 53, "f9": 59, "f10": 65, "f11": 71, "f12": 77,
    "apostrophe": 70, "comma": 61, "period": 67, "minus": 73, "iso_backslash": 4,
    "iso_less_than": 13,  # possibly the same physical key as iso_backslash, logged differently between sessions
    "a_grave": 80, "e_accent": 75, "i_grave": 76, "o_accent": 74, "u_grave": 87,
    "plus": 81, "print_screen": 83, "insert": 89, "windows": 12, "menu": 72,
    "arrow_left": 84, "arrow_right": 102, "arrow_up": 90, "arrow_down": 96,
    "volume_mute": 103, "volume_down": 104, "volume_up": 105,
    "predator_key": 106, "power": 107,
}


def parse_hex_color(value):
    value = value.lstrip("#")
    if len(value) != 6:
        raise argparse.ArgumentTypeError(f"{value!r}: expected 6 hex digits, e.g. FF0000")
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r}: not valid hex")
    return r, g, b


def parse_set(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"{value!r}: expected KEY=RRGGBB")
    key, color = value.split("=", 1)
    key = key.strip().lower()
    if key not in KEY_SLOTS:
        raise argparse.ArgumentTypeError(
            f"unknown key {key!r}; known keys: {', '.join(sorted(KEY_SLOTS))}")
    rgb = parse_hex_color(color.strip())
    if rgb == FORBIDDEN:
        raise argparse.ArgumentTypeError(
            f"refusing to set {key} to {FORBIDDEN} -- collides with the firmware's "
            "reserved sentinel color and causes flicker")
    return key, rgb


def non_negative_int(value):
    seconds = int(value)
    if seconds < 0:
        raise argparse.ArgumentTypeError("--wait must be a non-negative integer")
    return seconds


def load_state():
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    keys = {k: v for k, v in data.get("keys", {}).items() if k in KEY_SLOTS}
    if not keys:
        return None
    return data.get("brightness", 0x32), keys


def save_state(brightness, key_colors):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    data = {
        "brightness": brightness,
        "keys": {key: "%02X%02X%02X" % rgb for key, rgb in key_colors.items()},
    }
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)


def build_frame(slot_colors):
    buf = bytearray(NUM_SLOTS * 4)
    for slot, (r, g, b) in slot_colors.items():
        buf[slot * 4:slot * 4 + 4] = bytes([0x00, r, g, b])
    return bytes(buf)


def send_feature(dev, payload7):
    payload = list(payload7)
    payload.append((0xFF - sum(payload)) & 0xFF)
    dev.ctrl_transfer(0x21, 0x09, 0x0300, INTERFACE, bytes(payload))


def send_frame(dev, frame):
    for i in range(8):
        dev.write(OUT_ENDPOINT, frame[i * 64:(i + 1) * 64])
        time.sleep(0.015)


def main():
    parser = argparse.ArgumentParser(
        description="Set per-key RGB colors on the Triton 500 per-key keyboard, "
                     "for the subset of keys with a known slot address.",
        epilog=f"Known keys: {', '.join(sorted(KEY_SLOTS))}",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", dest="assignments", action="append", type=parse_set,
                         metavar="KEY=RRGGBB", default=[],
                         help="assign a color to a key; repeatable")
    parser.add_argument("--brightness", type=int, default=0x32, choices=range(0, 101),
                         metavar="0-100", help="per-key mode brightness (default: 50)")
    parser.add_argument("--wait", type=non_negative_int, default=0, metavar="SECONDS",
                         help="seconds to wait for the USB device (default: 0, single attempt)")
    parser.add_argument("--list-keys", action="store_true", help="print known keys and exit")
    parser.add_argument("--replay", action="store_true",
                         help="restore the last colors saved by a previous --set run "
                              "(no-op if nothing was ever saved); used by "
                              "predator-rgb-perkey.service at boot/resume")
    args = parser.parse_args()

    if args.list_keys:
        for key in sorted(KEY_SLOTS):
            print(f"{key} -> slot {KEY_SLOTS[key]}")
        return

    key_colors = {}
    brightness = args.brightness
    if args.replay:
        state = load_state()
        if state is not None:
            brightness, saved_keys = state
            key_colors = {key: parse_hex_color(color) for key, color in saved_keys.items()}

    for key, rgb in args.assignments:
        key_colors[key] = rgb

    if not key_colors:
        if args.replay:
            print("nothing saved yet, leaving keyboard as-is")
            return
        sys.exit("nothing to do: pass at least one --set KEY=RRGGBB (or --list-keys/--replay)")

    slot_colors = {KEY_SLOTS[key]: rgb for key, rgb in key_colors.items()}

    dev = None
    for _ in range(max(args.wait, 1)):
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is not None:
            break
        time.sleep(1)
    if dev is None:
        sys.exit(f"keyboard {VENDOR_ID:04x}:{PRODUCT_ID:04x} not found")

    frame = build_frame(slot_colors)

    if dev.is_kernel_driver_active(INTERFACE):
        dev.detach_kernel_driver(INTERFACE)
    usb.util.claim_interface(dev, INTERFACE)
    try:
        send_feature(dev, [0x12, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00])
        time.sleep(0.2)
        send_feature(dev, [0x08, 0x00, 0x33, 0x05, brightness, 0x01, 0x01])
        time.sleep(0.2)
        send_frame(dev, frame)
        save_state(brightness, key_colors)
    finally:
        usb.util.release_interface(dev, INTERFACE)
        try:
            dev.attach_kernel_driver(INTERFACE)
        except usb.core.USBError:
            pass


if __name__ == "__main__":
    main()
