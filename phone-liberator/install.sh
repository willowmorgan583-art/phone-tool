#!/usr/bin/env bash
# Phone Liberator v4 — quick install script
set -e

INSTALL_DIR="$HOME/phone-liberator"
mkdir -p "$INSTALL_DIR/tools" "$INSTALL_DIR/backup" "$INSTALL_DIR/firmware"

echo "=== Installing Python / PyQt5 ==="
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pyqt5 adb fastboot

echo "=== Copying files ==="
cp liberator.py "$INSTALL_DIR/"

echo "=== Installing desktop icon ==="
cp phone-liberator.desktop ~/.local/share/applications/ 2>/dev/null || true
cp phone-liberator.desktop ~/Desktop/ 2>/dev/null || true
chmod +x ~/Desktop/phone-liberator.desktop 2>/dev/null || true
gio set ~/Desktop/phone-liberator.desktop metadata::trusted true 2>/dev/null || true

echo "=== Installing USB udev rules ==="
sudo tee /etc/udev/rules.d/51-phone-liberator.rules > /dev/null << 'EOF'
SUBSYSTEM=="usb",ATTR{idVendor}=="04e8",MODE="0666",GROUP="plugdev"
SUBSYSTEM=="usb",ATTR{idVendor}=="18d1",MODE="0666",GROUP="plugdev"
SUBSYSTEM=="usb",ATTR{idVendor}=="05c6",MODE="0666",GROUP="plugdev"
SUBSYSTEM=="usb",ATTR{idVendor}=="0e8d",MODE="0666",GROUP="plugdev"
SUBSYSTEM=="usb",ATTR{idVendor}=="2717",MODE="0666",GROUP="plugdev"
SUBSYSTEM=="usb",ATTR{idVendor}=="12d1",MODE="0666",GROUP="plugdev"
SUBSYSTEM=="usb",ATTR{idVendor}=="05ac",MODE="0666",GROUP="plugdev"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
sudo usermod -aG plugdev "$USER" 2>/dev/null || true

echo ""
echo "=== Done! Run with: python3 $INSTALL_DIR/liberator.py ==="
echo "=== Or double-click Phone Liberator on your Desktop ==="
