#!/system/bin/sh
# S24 Ultra spoof - runs late in boot via Magisk
mount -o bind /data/adb/modules/fake_proc/fake_version /proc/version 2>/dev/null

# Hardware
resetprop ro.hardware.egl angle
resetprop ro.hardware.gralloc adreno
resetprop ro.hardware.vulkan adreno
resetprop ro.hardware qcom
resetprop ro.board.platform pineapple
resetprop gralloc.gbm.device ""

# Build identity
resetprop ro.product.model SM-S928B
resetprop ro.product.brand samsung
resetprop ro.product.manufacturer Samsung
resetprop ro.product.device e3q
resetprop ro.product.name e3qxxx
resetprop ro.build.fingerprint "samsung/e3qxxx/e3q:14/UP1A.231005.007/S928BXXU1AXBA:user/release-keys"
resetprop ro.build.description "e3qxxx-user 14 UP1A.231005.007 S928BXXU1AXBA release-keys"
resetprop ro.build.characteristics phone
resetprop ro.build.tags release-keys
resetprop ro.build.type user
resetprop ro.build.user nobody
resetprop ro.build.host android-build
resetprop ro.build.display.id "e3qxxx-user 14 UP1A.231005.007 S928BXXU1AXBA release-keys"
resetprop ro.build.flavor user
resetprop ro.build.product e3q

# Sub-partition overrides (the leakers)
for part in system vendor odm product system_ext vendor_dlkm; do
    resetprop -n ro.product.${part}.brand samsung
    resetprop -n ro.product.${part}.device e3q
    resetprop -n ro.product.${part}.manufacturer Samsung
    resetprop -n ro.product.${part}.model SM-S928B
    resetprop -n ro.product.${part}.name e3qxxx
    resetprop -n ro.${part}.build.fingerprint "samsung/e3qxxx/e3q:14/UP1A.231005.007/S928BXXU1AXBA:user/release-keys"
    resetprop -n ro.${part}.build.tags release-keys
    resetprop -n ro.${part}.build.type user
done

# Erase LineageOS
for prop in ro.lineage.device ro.lineage.version ro.lineage.display.version ro.modversion ro.lineage.releasetype ro.lineage.build.version ro.lineage.build.version.plat.rev ro.lineage.build.version.plat.sdk ro.lineagelegal.url; do
    resetprop -n $prop ""
done

# Blank waydroid runtime props
for prop in $(getprop | grep -iE '^\[waydroid\.' | cut -d'[' -f2 | cut -d']' -f1); do
    resetprop "$prop" ""
done

# Display
wm size 1440x3120 2>/dev/null
wm density 560 2>/dev/null
resetprop ro.sf.lcd_density 560
