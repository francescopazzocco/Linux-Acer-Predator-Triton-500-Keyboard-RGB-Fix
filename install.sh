#!/bin/bash
set -e

echo "[*] Installing dependencies..."
apt-get update
apt-get install -y git python3 python3-usb

echo "[*] Cloning fix repository..."
git clone https://github.com/francescopazzocco/Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix.git /tmp/keyboard-fix
cd /tmp/keyboard-fix

echo "[*] Copying scripts to /usr/local/bin..."
cp predator-rgb-red.py /usr/local/bin/predator-rgb-red.py
cp predator-rgb-fnkeys.py /usr/local/bin/predator-rgb-fnkeys.py
cp perkey_rgb.py /usr/local/bin/predator-rgb-perkey.py
chmod +x /usr/local/bin/predator-rgb-red.py /usr/local/bin/predator-rgb-fnkeys.py /usr/local/bin/predator-rgb-perkey.py

echo "[*] Installing systemd services..."
cp predator-rgb.service /etc/systemd/system/predator-rgb.service
cp predator-rgb-fnkeys.service /etc/systemd/system/predator-rgb-fnkeys.service
cp predator-rgb-perkey.service /etc/systemd/system/predator-rgb-perkey.service

echo "[*] Enabling and starting the services..."
systemctl daemon-reload
systemctl enable predator-rgb.service predator-rgb-fnkeys.service predator-rgb-perkey.service
systemctl start predator-rgb.service predator-rgb-fnkeys.service predator-rgb-perkey.service

echo "[*] Cleaning up..."
cd /
rm -rf /tmp/keyboard-fix

echo "[✔] Installation complete. The RGB keyboard fix is now active."
echo ""
echo "[✔] Done. Press Enter to close this window."
read
