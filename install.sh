#!/bin/bash
set -e

echo "[*] Installing dependencies..."
apt-get update
apt-get install -y git python3 python3-usb

echo "[*] Cloning fix repository..."
git clone https://github.com/DoStraTech/Linux-Acer-Predator-Triton-500-Keyboard-RGB-Fix.git /tmp/keyboard-fix
cd /tmp/keyboard-fix

echo "[*] Copying scripts to /usr/local/bin..."
cp fix_keyboard.py /usr/local/bin/fix_keyboard.py
cp fn_brightness.py /usr/local/bin/fn_brightness.py
chmod +x /usr/local/bin/fix_keyboard.py /usr/local/bin/fn_brightness.py

echo "[*] Installing systemd services..."
cp fix-keyboard.service /etc/systemd/system/fix-keyboard.service
cp fn-brightness.service /etc/systemd/system/fn-brightness.service

echo "[*] Enabling and starting the services..."
systemctl daemon-reload
systemctl enable fix-keyboard.service fn-brightness.service
systemctl start fix-keyboard.service fn-brightness.service

echo "[*] Cleaning up..."
cd /
rm -rf /tmp/keyboard-fix

echo "[✔] Installation complete. The RGB keyboard fix is now active."
echo ""
echo "[✔] Done. Press Enter to close this window."
read
