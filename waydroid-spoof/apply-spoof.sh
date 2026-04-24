#!/bin/bash
# One-shot Waydroid S24 Ultra spoof installer + activator
# Run on your Debian host as: sudo bash apply-spoof.sh

set -e

USER_NAME="${SUDO_USER:-pirate101}"
WAYDROID_DATA="/home/${USER_NAME}/.local/share/waydroid/data"
MODULE_DIR="${WAYDROID_DATA}/adb/modules/fake_proc"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[+] Using Waydroid data path: ${WAYDROID_DATA}"

# 1. Ensure module dir exists
mkdir -p "${MODULE_DIR}"

# 2. Copy service.sh into the module
cp "${SCRIPT_DIR}/service.sh" "${MODULE_DIR}/service.sh"
chmod 755 "${MODULE_DIR}/service.sh"
echo "[+] service.sh installed"

# 3. Create fake kernel version file if missing
if [ ! -f "${MODULE_DIR}/fake_version" ]; then
    cat > "${MODULE_DIR}/fake_version" <<'EOF'
Linux version 5.15.104-android14-11-g4d8b1f3c2e8d-ab10987654 (build@build-host) (Android (8508608, based on r450784e) clang version 14.0.7, LLD 14.0.7) #1 SMP PREEMPT Thu Feb 29 20:45:01 UTC 2024
EOF
    chmod 644 "${MODULE_DIR}/fake_version"
    echo "[+] fake_version created"
fi

# 4. Make sure module is enabled (no disable/remove flags)
rm -f "${MODULE_DIR}/disable" "${MODULE_DIR}/remove"

# 5. Ensure module.prop exists
if [ ! -f "${MODULE_DIR}/module.prop" ]; then
    cat > "${MODULE_DIR}/module.prop" <<'EOF'
id=fake_proc
name=Fake Proc S24 Ultra Spoof
version=v1.0
versionCode=1
author=local
description=Spoofs Waydroid as Samsung Galaxy S24 Ultra
EOF
    echo "[+] module.prop created"
fi

# 6. Restart container
echo "[+] Restarting waydroid-container..."
systemctl restart waydroid-container
sleep 20

# 7. Verify container is up
if ! waydroid status | grep -q "RUNNING"; then
    echo "[!] Container not running, starting session..."
    sudo -u "${USER_NAME}" waydroid session start &
    sleep 10
fi

# 8. Inject props live (in case service.sh hasn't run yet)
echo "[+] Force-injecting props live..."
waydroid shell /data/adb/modules/fake_proc/service.sh || true

# 9. Verify
echo ""
echo "================ VERIFICATION ================"
echo "--- Should be Samsung/S24: ---"
waydroid shell getprop ro.product.model
waydroid shell getprop ro.product.brand
waydroid shell getprop ro.build.fingerprint
echo ""
echo "--- Should be empty/samsung (not waydroid/lineage): ---"
waydroid shell getprop | grep -iE 'waydroid\.|lineage|product\.(odm|system|vendor)\.brand' | head -20
echo "=============================================="
echo ""
echo "[+] DONE. If anything still shows waydroid/lineage above, reboot and check again."
