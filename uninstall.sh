#!/bin/bash
set -e

echo "[*] Stopping systemd services..."
systemctl stop predator-rgb.service predator-rgb-fnkeys.service predator-rgb-perkey.service || true

echo "[*] Disabling systemd services..."
systemctl disable predator-rgb.service predator-rgb-fnkeys.service predator-rgb-perkey.service || true

echo "[*] Removing systemd service files..."
rm -f /etc/systemd/system/predator-rgb.service
rm -f /etc/systemd/system/predator-rgb-fnkeys.service
rm -f /etc/systemd/system/predator-rgb-perkey.service

echo "[*] Removing RGB fix scripts..."
rm -f /usr/local/bin/predator-rgb-red.py
rm -f /usr/local/bin/predator-rgb-fnkeys.py
rm -f /usr/local/bin/predator-rgb-perkey.py

echo "[*] Reloading systemd daemon..."
systemctl daemon-reload

echo "[✔] Uninstallation complete."
echo ""
echo "[✔] Done. Press Enter to close this window."
read
