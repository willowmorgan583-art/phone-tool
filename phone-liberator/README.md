# Phone Liberator v5

A modern PyQt5 desktop tool for Android / iPhone device unlocking, Mkopa MDM
removal, feature-phone AT commands, network unlocks and stock-firmware restore.
Runs on Debian / Ubuntu Linux.

## Highlights — what's new in v5

- **Modern GUI** — sidebar navigation, card-grid operation layout, severity badges
  (`SAFE` / `INFO` / `WARN` / `DANGER` / `ROOT`), live search across every category,
  collapsible log panel, status bar with elapsed-time clock.
- **Dual themes** — Catppuccin **Mocha** (dark) and **Latte** (light). Toggle with
  `Ctrl+T`; preference is persisted via `QSettings`.
- **Keyboard shortcuts** — `Ctrl+R` scan, `Ctrl+F` search, `Ctrl+T` theme toggle,
  `Ctrl+L` clear log, `Ctrl+S` save log, `Ctrl+,` settings, `Esc` abort running op.
- **Settings dialog** — customise install / backup / firmware / tools / log paths,
  autorefresh interval, "reboot after operation" default.
- **Toast notifications** & **confirmation dialogs** for every `DANGER` operation.
- **130+ operations** across 13 categories (see below), each with an on-card
  description, tooltip, severity badge and searchable tool ID.
- **Sudo password dialog** — tools that need administrator access prompt for
  the Linux sudo password in a masked dialog and pass it through askpass without
  printing the real password in logs.
- **Bug fixes vs v4**:
  - `Abort` button now kills the entire process group (`os.killpg`) instead of
    just the parent shell — child processes no longer survive an abort.
  - Detector thread has a 4 s timeout per `adb` / `fastboot` call so a hung
    device cannot freeze the GUI.
  - All shell interpolation uses `shlex.quote()` — no more shell-injection via
    serial numbers, file paths or app names.
  - Detector thread lifecycle: auto-cleanup with `deleteLater`, no leaks on
    repeated scans.
  - Removed dead code (duplicate vars, double `setWidget`).

## Categories

| Category | Highlights |
|---|---|
| **Device** | Scan, device-info, scrcpy mirror / screen record, battery + network info, ADB shell, reboot target menu |
| **Android ADB** | Lock removal, FRP bypass, backup, APK install, sideload, screenshot, logcat, install-from-url, app permissions, intent launcher |
| **Wi-Fi ADB** | Pair + connect over TCP/IP, list connected devices, disconnect all |
| **App Manager** | List / disable / enable / uninstall / clear data / extract APK |
| **Fastboot** | OEM unlock, flashing-unlock, erase FRP, factory reset, flash boot/recovery/dtbo/vbmeta + boot.img boot, flash full ZIP, lock bootloader, disable verity, A/B slot manager |
| **Root** | Magisk patched-boot flow, KernelSU, root-status check |
| **Mkopa / PAYG** | MDM removal, stock firmware restore, lock bootloader, kiosk wipe, Safaricom unlock |
| **iPhone** | DFU guide, pair/info/backup, IPSW restore, diagnostics, jailbreak matrix (checkra1n, palera1n, unc0ver, Dopamine, Serotonin, TrollStore, MacDirtyCow), SSH, Sideloadly, Activation-Lock guidance |
| **Feature Phone** | AT info, IMEI read, factory reset, AT+CLCK unlock, custom AT command, SP Flash Tool, JAF/Phoenix |
| **Network Unlock** | Unlock attempts, NCK gen, QC NV, MTK net-unlock, IMEI check |
| **MTK / EDL** | mtkclient Fastboot/FRP/read, edl.py partitions/FRP/full-read/flash, chipset detector |
| **Vendor** | Xiaomi unlock-wait, OPPO/Realme codes, Huawei testpoint guide, Samsung Download mode, Samsung FRP checklist, LG bootloader, Motorola unlock, Pixel factory-image helpers |
| **Maintenance** | One-click install of every dependency (ADB, scrcpy, mtkclient, edl.py, checkra1n, palera1n, Heimdall, samloader, Wine, Spreadtrum/Unisoc support…) and `/etc/udev/rules.d/51-phone-liberator.rules`, plus toolchain verification |

## Requirements

```bash
sudo apt-get install python3-pyqt5 adb fastboot
```

`scrcpy`, `libimobiledevice-utils`, `usbmuxd`, `python3-serial` etc. are installed
on demand from the **Maintenance** category.

## Run

```bash
python3 ~/phone-liberator/liberator.py
```

## Desktop icon

```bash
cp phone-liberator.desktop ~/.local/share/applications/
cp phone-liberator.desktop ~/Desktop/
chmod +x ~/Desktop/phone-liberator.desktop
gio set ~/Desktop/phone-liberator.desktop metadata::trusted true
```

## Tool directories

All paths are configurable from **Settings** (`Ctrl+,`).

| Path | Purpose |
|---|---|
| `~/phone-liberator/tools/` | SP Flash Tool .tar.gz, JAF.exe, DC-Unlocker .exe, idevicerestore source |
| `~/phone-liberator/backup/` | ADB pull, MTK flash read, EDL dumps, iPhone backups, screen recordings |
| `~/phone-liberator/firmware/` | Samsung / MTK / QC stock firmware zips |
| `~/phone-liberator/logs/` | Saved operation logs (`Ctrl+S` → choose file) |

## Mkopa stock-firmware restore flow

1. **Flash Stock Firmware** — auto-detects Samsung (samloader + Heimdall), MTK (SP Flash Tool), Qualcomm/generic (fastboot flash)
2. **Lock Bootloader** — re-lock after restore so Mkopa software cannot reinstall

## Jailbreak matrix (2025)

| Tool | Chip | iOS | Devices |
|---|---|---|---|
| checkra1n | A5–A11 | 12–14.8.1 | 5s / 6 / 6s / SE1 / 7 / 8 / X |
| palera1n | A9–A17 | 15–17.0 | 6s – 15 Pro Max |
| unc0ver | A12–A14 | 11–14.8 | XS / 11 / 12 |
| Dopamine | A12–A15 | 15–16.6.1 | XS – 13 (rootless) |
| Serotonin | A12–A17 | 17 | RootHide rootless |
| TrollStore | A9+ | 14–17.0 | No jailbreak needed |
| MacDirtyCow | A9+ | 15–16.1.2 | CVE-2022-46689 |
| **iPhone 16 Pro A18** | — | — | **No public JB (2025)** |

## Keyboard reference

| Shortcut | Action |
|---|---|
| `Ctrl+R` | Scan devices |
| `Ctrl+F` | Focus search bar |
| `Ctrl+T` | Toggle dark / light theme |
| `Ctrl+L` | Clear log |
| `Ctrl+S` | Save log to file |
| `Ctrl+,` | Open Settings |
| `Esc` | Abort running operation |

## Notes

- **Carrier unlock (Android only):** For Safaricom-locked Android handsets — visit any Safaricom shop with IMEI + ID.
- **iPhone carrier unlock:** Not supported — contact your carrier directly.
- **Activation Lock (deceased owner):** Apple official path — death certificate + ownership proof required.
- Feature-phone serial commands default to the port chosen from the device dropdown after scanning.

## License

MIT — use responsibly and only on devices you own or have authorisation to service.
