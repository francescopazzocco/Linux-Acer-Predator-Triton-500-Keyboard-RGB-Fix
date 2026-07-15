#!/usr/bin/env python3
# Predator PT515-52 keyboard (Darfon 0d62:7cb1 controller, per-key RGB).
# Sets a static color from the firmware palette via a USB HID feature
# report. Used by predator-rgb.service (boot + resume).
#
# Payload: [0x08, 0x00, mode, 0x05, brightness, color_index, 0x00, checksum]
#   mode 0x01 = static
#   brightness 0x00-0x64
#   color_index (verified): 0=dark red 1=orange 2=teal 3=yellow-green
#     4=blue 5=light green 6=purple 7=white 8=RED
#   checksum = 0xFF - sum of the other 7 bytes

import os
import sys
import time

import usb.core
import usb.util

VENDOR_ID, PRODUCT_ID, INTERFACE = 0x0d62, 0x7cb1, 3
COLOR_INDEX = 0

MODE_FILE = "/var/lib/predator-rgb/mode"

# brightness: last value chosen with Fn+F7/F8 (see predator-rgb-fnkeys.py),
# default 100 if never touched
try:
    with open("/var/lib/predator-rgb/brightness") as f:
        BRIGHTNESS = min(100, max(0, int(f.read().strip())))
except (OSError, ValueError):
    BRIGHTNESS = 0x64

dev = None
for _ in range(30):
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is not None:
        break
    time.sleep(1)
if dev is None:
    sys.exit("Darfon 0d62:7cb1 keyboard not found")

payload = [0x08, 0x00, 0x01, 0x05, BRIGHTNESS, COLOR_INDEX, 0x00]
payload.append((0xFF - sum(payload)) & 0xFF)

if dev.is_kernel_driver_active(INTERFACE):
    dev.detach_kernel_driver(INTERFACE)
usb.util.claim_interface(dev, INTERFACE)
dev.ctrl_transfer(0x21, 0x09, 0x0300, INTERFACE, bytes(payload))
usb.util.release_interface(dev, INTERFACE)
# mode "static" so predator-rgb-fnkeys.py knows which payload to resend
os.makedirs(os.path.dirname(MODE_FILE), exist_ok=True)
with open(MODE_FILE, "w") as f:
    f.write("static\n")
# reattach usbhid: needed by hidraw2/3 (Fn+F7/F8 daemon) and by key reports
try:
    dev.attach_kernel_driver(INTERFACE)
except usb.core.USBError:
    pass
