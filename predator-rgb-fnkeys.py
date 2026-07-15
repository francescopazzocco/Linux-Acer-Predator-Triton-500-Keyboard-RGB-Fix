#!/usr/bin/env python3
# Restores Fn+F7/F8 (keyboard brightness) on the Predator PT515-52.
#
# In static mode the Darfon firmware no longer adjusts brightness on its
# own: it just emits a vendor report (id 0x04, byte 0x7d=down(F7) /
# 0x7c=up(F8), verified on hardware) on interface 2, which the kernel does
# not map to any key. This daemon listens for those reports and re-sends
# the RGB command (via HIDIOCSFEATURE on interface 3) with the updated
# brightness.
#
# It has to resend a different payload depending on which lighting mode is
# active (read from /var/lib/predator-rgb/mode, written by
# predator-rgb-red.py and predator-rgb-perkey.py): always resending the
# static payload -- even in per-key mode -- used to silently overwrite it
# on every Fn+F7/F8 press, discarding the custom colors.
#
# The current brightness is persisted in /var/lib/predator-rgb/brightness,
# also read by predator-rgb-red.py at boot/resume.
# COLOR_INDEX must match the one in predator-rgb-red.py.

import fcntl
import glob
import os
import sys

COLOR_INDEX = 8       # red (verified palette index)
STEP = 10            # with a 50 ceiling: 6 real steps
MAX_BRIGHTNESS = 50  # the firmware already renders at max at 50: higher does nothing
STATE_FILE = "/var/lib/predator-rgb/brightness"
MODE_FILE = "/var/lib/predator-rgb/mode"

KEY_UP, KEY_DOWN = 0x7C, 0x7D  # F8 = up, F7 = down (as labeled on the keyboard)


def find_hidraw(iface):
    for dev in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(f"{dev}/device/uevent").read().upper()
        except OSError:
            continue
        if "0D62" in uevent and "7CB1" in uevent:
            path = os.path.realpath(f"{dev}/device")
            if f":1.{iface}/" in path + "/":
                return f"/dev/{os.path.basename(dev)}"
    return None


def hidiocsfeature(ctrl, buf):
    # HIDIOCSFEATURE = _IOC(READ|WRITE, 'H', 0x06, len)
    fcntl.ioctl(ctrl, (3 << 30) | (len(buf) << 16) | (0x48 << 8) | 0x06, buf)


def send_static(ctrl, brightness):
    payload = [0x08, 0x00, 0x01, 0x05, brightness, COLOR_INDEX, 0x00]
    payload.append((0xFF - sum(payload)) & 0xFF)
    hidiocsfeature(ctrl, bytes([0x00]) + bytes(payload))


def send_perkey_brightness(ctrl, brightness):
    # Same feature report perkey_rgb.py uses to enter per-key mode
    # (08 00 33 05 <brightness> 01 01 <checksum>). Doesn't touch the
    # already-loaded 512-byte frame buffer -- brightness only.
    payload = [0x08, 0x00, 0x33, 0x05, brightness, 0x01, 0x01]
    payload.append((0xFF - sum(payload)) & 0xFF)
    hidiocsfeature(ctrl, bytes([0x00]) + bytes(payload))


def load_brightness():
    try:
        return min(100, max(0, int(open(STATE_FILE).read().strip())))
    except (OSError, ValueError):
        return 100


def save_brightness(value):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(f"{value}\n")


def load_mode():
    try:
        return open(MODE_FILE).read().strip()
    except OSError:
        return "static"


def main():
    events_path, ctrl_path = find_hidraw(2), find_hidraw(3)
    if not events_path or not ctrl_path:
        sys.exit("Darfon 0d62:7cb1 keyboard not found")

    brightness = load_brightness()
    with open(events_path, "rb", buffering=0) as events, \
         open(ctrl_path, "wb", buffering=0) as ctrl:
        while True:
            report = events.read(64)
            if not report:
                sys.exit(1)  # device gone; let systemd restart us
            if report[0] == 0x04 and len(report) >= 2 and report[1] in (KEY_UP, KEY_DOWN):
                if report[1] == KEY_UP:
                    new_brightness = min(MAX_BRIGHTNESS, brightness + STEP)
                else:
                    new_brightness = max(0, brightness - STEP)
                if new_brightness == brightness:
                    # Already at the floor/ceiling: holding or mashing
                    # Fn+F7/F8 here used to keep re-sending the identical
                    # feature report on every repeat event. A burst of
                    # identical back-to-back writes appears to be what
                    # knocks the firmware into its fallback "idle" state --
                    # skip the resend once we're pinned at a limit.
                    continue
                brightness = new_brightness
                if load_mode() == "perkey":
                    send_perkey_brightness(ctrl, brightness)
                else:
                    send_static(ctrl, brightness)
                save_brightness(brightness)


if __name__ == "__main__":
    main()
