# Phone Liberator v4

A PyQt5 GUI tool for Android / iPhone device unlocking, Mkopa MDM removal,
feature phone AT commands, network unlock, and stock firmware restore.
Runs on Debian / Ubuntu Linux.

## Features

| Tab | What it does |
|---|---|
| **Android ADB** | Screen lock removal, FRP bypass, backup, APK install, sideload, screenshot, logcat |
| **Fastboot** | OEM unlock, erase FRP, factory reset, flash boot.img / firmware .zip |
| **Mkopa / PAYG** | MDM removal, MTK / Qualcomm / Samsung stock firmware flash, bootloader lock, Safaricom carrier unlock |
| **iPhone** | DFU guide, backup, jailbreak matrix (checkra1n / palera1n / Dopamine / TrollStore / unc0ver), SSH, IPA install, Activation Lock |
| **Feature Phone** | AT commands, IMEI read, factory reset, Nokia JAF/Phoenix (Wine), SP Flash Tool, DC-Unlocker |
| **Network Unlock** | AT+CLCK NCK unlock, unlock attempts, NCK generator, Qualcomm NV, MTK network unlock, IMEI check |
| **MTK / EDL** | mtkclient Fastboot mode, FRP erase, flash read; edl.py partition table, erase, read, flash |
| **Maintenance** | One-click install for every dependency (ADB, mtkclient, edl.py, checkra1n, palera1n, Heimdall, samloader, Wine…) |

## Requirements

```bash
sudo apt-get install python3-pyqt5 adb fastboot
```

## Run

```bash
python3 ~/phone-liberator/liberator.py
```

## Desktop icon (double-click to launch)

```bash
cp phone-liberator.desktop ~/.local/share/applications/
cp phone-liberator.desktop ~/Desktop/
chmod +x ~/Desktop/phone-liberator.desktop
gio set ~/Desktop/phone-liberator.desktop metadata::trusted true
```

## Tool directories

| Path | Purpose |
|---|---|
| `~/phone-liberator/tools/` | SP Flash Tool .tar.gz, JAF.exe, DC-Unlocker .exe |
| `~/phone-liberator/backup/` | ADB pull, MTK flash read, EDL dumps, iPhone backups |
| `~/phone-liberator/firmware/` | Samsung / MTK / QC stock firmware zips |

## Mkopa stock firmware restore flow

1. **Flash Stock Firmware** — auto-detects Samsung (samloader + Heimdall), MTK (SP Flash Tool), Qualcomm/generic (fastboot flash)
2. **Lock Bootloader** — re-locks after restore so Mkopa software does not reinstall

## Jailbreak matrix (2025)

| Tool | Chip | iOS | Devices |
|---|---|---|---|
| checkra1n | A5–A11 | 12–14.8.1 | 5s / 6 / 6s / SE1 / 7 / 8 / X |
| palera1n | A9–A17 | 15–17.0 | 6s – 15 Pro Max |
| unc0ver | A12–A14 | 11–14.8 | XS / 11 / 12 |
| Dopamine | A12–A15 | 15–16.6.1 | XS – 13 (rootless) |
| TrollStore | A9+ | 14–17.0 | No jailbreak needed |
| MacDirtyCow | A9+ | 15–16.1.2 | CVE-2022-46689 |
| **iPhone 16 Pro A18** | — | — | **No public JB (2025)** |

## Notes

- **Carrier unlock (Android only):** For Safaricom-locked Android handsets — visit any Safaricom shop with IMEI + ID.
- **iPhone carrier unlock:** Not supported — contact your carrier directly.
- **Activation Lock (deceased owner):** Apple official path — death certificate + ownership proof required.
- Feature phone serial commands use `/dev/ttyUSB0` by default (select the device port from the dropdown after scanning).

## License

MIT — use responsibly and only on devices you own or have authorisation to service.
