#!/usr/bin/env python3
"""
Phone Liberator v5
==================
A modern PyQt5 GUI for Android / iPhone / feature-phone servicing:

    * ADB / Wi-Fi ADB / scrcpy / app manager / screen record
    * Fastboot OEM unlock, FRP erase, flash boot/recovery/firmware
    * Mkopa / PAYG MDM removal and stock-firmware restore
    * iPhone DFU / pair / backup / jailbreak matrix / TrollStore
    * Feature-phone AT commands, IMEI read, factory reset
    * Network unlock (AT+CLCK NCK, QC NV, MTK)
    * MTK / EDL partition tools (mtkclient + edl.py)
    * Magisk patched-boot flow, KernelSU status
    * Vendor helpers: Xiaomi mi-flash-unlock, OPPO/Realme, Huawei
    * Maintenance (one-click install of every dependency)

Single-file design — copy ~/phone-liberator/liberator.py and run.
Tested on Debian / Ubuntu with python3-pyqt5, adb, fastboot.
"""
from __future__ import annotations

import os
import re
import shlex
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import (
    QEvent,
    QSettings,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QKeySequence,
    QTextCursor,
)
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QStyle,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Phone Liberator"
APP_VERSION = "5.0"
ORG_NAME = "PhoneLiberator"
SETTINGS_NAME = "v5"

HOME = Path.home()
INSTALL_DIR = HOME / "phone-liberator"
DEFAULT_PATHS = {
    "tools_dir": str(INSTALL_DIR / "tools"),
    "backup_dir": str(INSTALL_DIR / "backup"),
    "firmware_dir": str(INSTALL_DIR / "firmware"),
    "log_dir": str(INSTALL_DIR / "logs"),
}

# ───────────────────────── Themes ─────────────────────────
THEMES: dict[str, dict[str, str]] = {
    # Catppuccin Mocha
    "dark": {
        "bg":            "#11111b",
        "surface":       "#1e1e2e",
        "surface2":      "#181825",
        "surface3":      "#313244",
        "border":        "#313244",
        "border_hi":     "#45475a",
        "muted":         "#6c7086",
        "text":          "#cdd6f4",
        "text_dim":      "#a6adc8",
        "accent":        "#89b4fa",
        "accent_hi":     "#b4befe",
        "info":          "#89dceb",
        "ok":            "#a6e3a1",
        "warn":          "#fab387",
        "danger":        "#f38ba8",
        "purple":        "#cba6f7",
        "yellow":        "#f9e2af",
        "ok_btn":        "#40a02b",
        "warn_btn":      "#df8e1d",
        "danger_btn":    "#d20f39",
    },
    # Catppuccin Latte
    "light": {
        "bg":            "#eff1f5",
        "surface":       "#ffffff",
        "surface2":      "#e6e9ef",
        "surface3":      "#dce0e8",
        "border":        "#bcc0cc",
        "border_hi":     "#9ca0b0",
        "muted":         "#7c7f93",
        "text":          "#4c4f69",
        "text_dim":      "#5c5f77",
        "accent":        "#1e66f5",
        "accent_hi":     "#7287fd",
        "info":          "#04a5e5",
        "ok":            "#40a02b",
        "warn":          "#df8e1d",
        "danger":        "#d20f39",
        "purple":        "#8839ef",
        "yellow":        "#df8e1d",
        "ok_btn":        "#40a02b",
        "warn_btn":      "#df8e1d",
        "danger_btn":    "#d20f39",
    },
}

# Severity → (label, fg colour key, bg colour key)
SEVERITY_BADGES: dict[str, tuple[str, str, str]] = {
    "safe":   ("SAFE",   "ok",     "surface3"),
    "normal": ("INFO",   "info",   "surface3"),
    "warn":   ("WARN",   "warn",   "surface3"),
    "danger": ("DANGER", "danger", "surface3"),
}


def stylesheet(t: dict[str, str]) -> str:
    """Build a full Qt stylesheet from the active theme dict."""
    return f"""
    QMainWindow, QWidget {{ background:{t['bg']}; color:{t['text']}; }}
    QToolTip {{ background:{t['surface3']}; color:{t['text']};
                border:1px solid {t['border_hi']}; padding:8px 10px; border-radius:6px; }}
    QMessageBox, QInputDialog, QFileDialog {{
        background:{t['surface']}; color:{t['text']};
    }}
    QFrame#sidebar {{ background:{t['surface']}; border-right:1px solid {t['border']}; }}
    QListWidget#sidebarList {{
        background:transparent; border:none; outline:none;
        padding:6px; font-size:13px;
    }}
    QListWidget#sidebarList::item {{
        padding:8px 12px; margin:2px 4px; border-radius:6px;
        color:{t['text_dim']};
    }}
    QListWidget#sidebarList::item:hover    {{ background:{t['surface2']}; color:{t['text']}; }}
    QListWidget#sidebarList::item:selected {{ background:{t['accent']}; color:{t['bg']}; }}
    QFrame#topbar {{ background:{t['surface']}; border-bottom:1px solid {t['border']}; }}
    QFrame#statusframe {{ background:{t['surface2']}; border-top:1px solid {t['border']}; }}
    QFrame#opcard {{
        background:{t['surface']}; border:1px solid {t['border']}; border-radius:8px;
    }}
    QFrame#opcard:hover {{ border:1px solid {t['accent']}; }}
    QFrame#heroCard {{
        background:{t['surface2']}; border:1px solid {t['border']}; border-radius:10px;
    }}
    QLabel#cardTitle    {{ font-weight:600; font-size:13px; color:{t['text']}; }}
    QLabel#cardDesc     {{ color:{t['text_dim']}; font-size:11px; line-height:1.35; }}
    QLabel#heroTitle    {{ color:{t['text']}; font-size:16px; font-weight:700; }}
    QLabel#heroDesc     {{ color:{t['text_dim']}; font-size:12px; }}
    QLabel#sectionHdr   {{ color:{t['text_dim']}; font-weight:600;
                           font-size:11px; letter-spacing:1px; }}
    QLabel#bigTitle     {{ font-size:18px; font-weight:600; color:{t['text']}; }}
    QLabel#statusLabel  {{ color:{t['text_dim']}; padding:4px 8px; }}
    QLabel#deviceLabel  {{ color:{t['text']}; font-weight:500; }}
    QLabel.badge {{
        padding:2px 8px; border-radius:8px; font-size:10px; font-weight:700;
        background:{t['surface3']}; color:{t['text_dim']};
    }}
    QPushButton {{
        background:{t['surface3']}; color:{t['text']}; border:none;
        border-radius:6px; padding:6px 14px; min-height:24px;
    }}
    QPushButton:hover    {{ background:{t['border_hi']}; }}
    QPushButton:pressed  {{ background:{t['border']}; }}
    QPushButton:disabled {{ background:{t['surface2']}; color:{t['muted']}; }}
    QPushButton#runBtn {{
        background:{t['accent']}; color:{t['bg']}; font-weight:600;
    }}
    QPushButton#runBtn:hover {{ background:{t['accent_hi']}; }}
    QPushButton#runBtn:focus {{
        border:2px solid {t['accent_hi']}; padding:4px 12px;
    }}
    QPushButton[severity="safe"]   {{ background:{t['ok_btn']};      color:#fff; font-weight:600; }}
    QPushButton[severity="warn"]   {{ background:{t['warn_btn']};    color:#fff; font-weight:600; }}
    QPushButton[severity="danger"] {{ background:{t['danger_btn']};  color:#fff; font-weight:600; }}
    QPushButton[severity="safe"]:hover   {{ background:{t['ok']}; }}
    QPushButton[severity="warn"]:hover   {{ background:{t['warn']}; }}
    QPushButton[severity="danger"]:hover {{ background:{t['danger']}; }}
    QPushButton#abortBtn {{
        background:{t['danger_btn']}; color:#fff; font-weight:700;
    }}
    QPushButton#abortBtn:disabled {{ background:{t['surface2']}; color:{t['muted']}; }}
    QPushButton#flatBtn  {{ background:transparent; padding:6px 10px; }}
    QPushButton#flatBtn:hover {{ background:{t['surface2']}; }}
    QToolButton {{
        background:transparent; color:{t['text_dim']};
        border:none; border-radius:6px; padding:6px 10px;
    }}
    QToolButton:hover    {{ background:{t['surface2']}; color:{t['text']}; }}
    QToolButton:pressed  {{ background:{t['surface3']}; }}
    QToolButton:checked  {{ background:{t['surface3']}; color:{t['text']}; }}
    QLineEdit, QTextEdit {{
        background:{t['surface2']}; color:{t['text']};
        border:1px solid {t['border']}; border-radius:6px; padding:6px 10px;
        selection-background-color:{t['accent']}; selection-color:{t['bg']};
    }}
    QLineEdit:focus, QTextEdit:focus {{ border:1px solid {t['accent']}; }}
    QTextEdit#logBox {{
        background:{t['bg']}; color:{t['text']};
        font-family:'JetBrains Mono','Fira Code','Cascadia Code','Source Code Pro','Menlo','Consolas','monospace';
        font-size:12px; padding:8px;
    }}
    QComboBox {{
        background:{t['surface2']}; color:{t['text']};
        border:1px solid {t['border']}; padding:5px 10px; border-radius:6px;
        min-width:240px;
    }}
    QComboBox:hover {{ border:1px solid {t['border_hi']}; }}
    QComboBox QAbstractItemView {{
        background:{t['surface2']}; color:{t['text']};
        selection-background-color:{t['accent']}; selection-color:{t['bg']};
        border:1px solid {t['border']};
    }}
    QCheckBox {{ color:{t['text']}; spacing:6px; }}
    QCheckBox::indicator {{ width:16px; height:16px; border-radius:3px;
                            background:{t['surface3']}; border:1px solid {t['border']}; }}
    QCheckBox::indicator:checked {{ background:{t['accent']}; border:1px solid {t['accent']}; }}
    QSpinBox {{
        background:{t['surface2']}; color:{t['text']};
        border:1px solid {t['border']}; padding:4px 8px; border-radius:6px;
    }}
    QScrollArea, QListWidget {{ border:none; background:transparent; }}
    QScrollBar:vertical, QScrollBar:horizontal {{
        background:{t['surface2']}; border:none; width:10px; height:10px;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background:{t['border_hi']}; border-radius:5px; min-height:30px; min-width:30px;
    }}
    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
        background:{t['muted']};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ background:none; height:0; width:0; }}
    QSplitter::handle {{ background:{t['border']}; }}
    QStatusBar {{ background:{t['surface2']}; color:{t['text_dim']}; border-top:1px solid {t['border']}; }}
    QMenu {{
        background:{t['surface']}; color:{t['text']};
        border:1px solid {t['border']}; padding:4px;
    }}
    QMenu::item {{ padding:6px 24px; border-radius:4px; }}
    QMenu::item:selected {{ background:{t['accent']}; color:{t['bg']}; }}
    QDialog {{ background:{t['surface']}; color:{t['text']}; }}
    """


# ───────────────────────── Operations table ─────────────────────────
@dataclass
class Op:
    cat: str
    op_id: str
    label: str
    desc: str
    severity: str = "normal"          # safe|normal|warn|danger
    needs_root: bool = False
    keywords: tuple[str, ...] = field(default_factory=tuple)


CATEGORIES: list[tuple[str, str]] = [
    ("DEV",   "Device"),
    ("ADB",   "Android ADB"),
    ("WADB",  "Wi-Fi ADB"),
    ("APP",   "App Manager"),
    ("FB",    "Fastboot"),
    ("ROOT",  "Root (Magisk/KSU)"),
    ("MKP",   "Mkopa / PAYG"),
    ("IOS",   "iPhone"),
    ("FTR",   "Feature Phone"),
    ("NET",   "Network Unlock"),
    ("MTK",   "MTK / EDL"),
    ("VND",   "Vendor"),
    ("MAINT", "Maintenance"),
]

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "DEV": "Identify connected devices, collect diagnostics, mirror screens, and reboot into service modes.",
    "ADB": "Safe Android maintenance over ADB: backups, app installs, logs, screenshots, and guided repair tools.",
    "WADB": "Pair, connect, list, and disconnect Android devices over Wi-Fi ADB.",
    "APP": "Inspect, extract, enable, disable, uninstall, and clear Android app packages.",
    "FB": "Bootloader and firmware repair workflows for Android devices in fastboot mode.",
    "ROOT": "Root-oriented Magisk and KernelSU helpers for owned development or repair devices.",
    "MKP": "PAYG and MDM repair flows for authorized technicians servicing owned Android handsets.",
    "IOS": "iPhone pairing, backup, diagnostics, DFU, restore, and jailbreak-compatibility references.",
    "FTR": "Feature-phone and modem tools using serial AT commands and legacy service utilities.",
    "NET": "Carrier-lock diagnostics and legal unlock helpers for authorized device servicing.",
    "MTK": "MediaTek, Qualcomm EDL, and chipset service utilities for low-level repair.",
    "VND": "Brand-specific guides for Samsung, Xiaomi, OPPO, Huawei, LG, Pixel, Motorola, and more.",
    "MAINT": "Install, verify, and repair host-side dependencies used by Phone Liberator.",
}

OPS: list[Op] = [
    # ── Device ─────────────────────────────────────────────────────────────
    Op("DEV", "dev.scan",         "Scan Devices",     "Find connected Android, iPhone, fastboot, and serial devices.", "safe"),
    Op("DEV", "dev.info",         "Device Info",      "Collect model, OS, build fingerprint, battery, CPU, and root status."),
    Op("DEV", "dev.scrcpy",       "Screen Mirror (scrcpy)", "Mirror an Android screen on the desktop with scrcpy.", "safe", keywords=("mirror", "screen")),
    Op("DEV", "dev.screenrec",    "Screen Record",    "Record the Android screen to an MP4 in the backup folder."),
    Op("DEV", "dev.battery",      "Battery / Health", "Show battery level, temperature, charging, and health data."),
    Op("DEV", "dev.network",      "Network Info",     "Show Wi-Fi, IP, MAC, DNS, and radio/network details."),
    Op("DEV", "dev.terminal",     "Open ADB Shell",   "Open an interactive shell for the selected Android device."),
    Op("DEV", "dev.reboot_menu",  "Reboot Menu",      "Choose Android reboot target: system, recovery, bootloader, or sideload.", "safe", keywords=("restart", "recovery")),

    # ── Android ADB ───────────────────────────────────────────────────────
    Op("ADB", "adb.lock_remove",  "Remove Screen Lock", "Delete Android lock database files on rooted devices you own.", "warn", needs_root=True, keywords=("password", "pin", "pattern")),
    Op("ADB", "adb.frp_bypass",   "FRP Bypass",         "Open setup-wizard and FRP troubleshooting commands for owned devices.", "warn"),
    Op("ADB", "adb.backup_sd",    "Backup /sdcard",     "Copy user-visible Android storage into the backup directory.", "safe"),
    Op("ADB", "adb.install_apk",  "Install APK",        "Install a local APK with runtime permissions granted."),
    Op("ADB", "adb.sideload_zip", "Sideload ZIP",       "Send an OTA or recovery ZIP to a device in sideload mode."),
    Op("ADB", "adb.reboot_fb",    "Reboot → Fastboot",  "Restart Android into bootloader/fastboot mode."),
    Op("ADB", "adb.reboot_rec",   "Reboot → Recovery",  "Restart Android into recovery mode."),
    Op("ADB", "adb.screenshot",   "Screenshot",         "Capture a PNG screenshot into the backup folder.", "safe"),
    Op("ADB", "adb.logcat",       "Logcat (live)",      "Stream Android logs until stopped or aborted."),
    Op("ADB", "adb.dump_props",   "Dump Props",         "Export Android system properties for diagnostics."),
    Op("ADB", "adb.sysinfo",      "Sysinfo",            "Snapshot CPU, RAM, storage, and package diagnostics."),
    Op("ADB", "adb.dns_override", "Set Private DNS",    "Configure Android private DNS hostname via settings."),
    Op("ADB", "adb.demo_mode",    "Toggle Demo Mode",   "Enable or disable clean status-bar demo mode for screenshots."),
    Op("ADB", "adb.permissions",  "App Permissions",    "List requested and granted permissions for one Android app.", "safe", keywords=("package", "permission")),
    Op("ADB", "adb.intent",       "Launch Intent",      "Start an Android activity/action safely from a guided form.", "safe", keywords=("activity", "am start")),

    # ── Wi-Fi ADB ─────────────────────────────────────────────────────────
    Op("WADB", "wadb.tcpip",      "Enable TCP/IP",      "adb tcpip 5555 (USB once, then wireless)", "safe"),
    Op("WADB", "wadb.connect",    "Connect by IP",      "adb connect <ip>:<port>", "safe"),
    Op("WADB", "wadb.pair",       "Pair (Android 11+)", "adb pair host:port + 6-digit code", "safe"),
    Op("WADB", "wadb.disconnect", "Disconnect All",     "adb disconnect"),
    Op("WADB", "wadb.list",       "List Wireless",      "adb devices -l"),

    # ── App Manager ───────────────────────────────────────────────────────
    Op("APP", "app.list",         "List Packages",      "Filter installed packages with regex"),
    Op("APP", "app.uninstall",    "Uninstall App",      "Uninstall by package name", "warn"),
    Op("APP", "app.disable",      "Disable App",        "pm disable-user --user 0", "warn"),
    Op("APP", "app.enable",       "Enable App",         "Re-enable a disabled Android package for the current user.", "safe"),
    Op("APP", "app.clear",        "Clear App Data",     "pm clear <pkg>", "warn"),
    Op("APP", "app.extract",      "Extract APK",        "Pull installed APK to backup dir", "safe"),
    Op("APP", "app.bloat",        "Disable Bloatware",  "Disable common preset bloat list", "warn"),

    # ── Fastboot ──────────────────────────────────────────────────────────
    Op("FB", "fb.oem_unlock",     "OEM Unlock",         "Unlock older Android bootloaders; this wipes user data.", "danger"),
    Op("FB", "fb.flashing_unlock","Flashing Unlock",    "Unlock modern Android bootloaders; this wipes user data.", "danger"),
    Op("FB", "fb.frp_erase",      "Erase FRP",          "Erase fastboot FRP partition when supported by the device.", "warn"),
    Op("FB", "fb.factory_reset",  "Factory Reset",      "Run fastboot wipe for userdata and cache.", "danger"),
    Op("FB", "fb.reboot",         "Fastboot Reboot",    "Restart a device out of fastboot mode."),
    Op("FB", "fb.lock_bl",        "Lock Bootloader",    "Re-lock bootloader after restoring verified stock firmware.", "warn"),
    Op("FB", "fb.flash_boot",     "Flash boot.img",     "Flash a selected boot image to the boot partition.", "warn"),
    Op("FB", "fb.flash_recovery", "Flash recovery.img", "Flash a selected recovery image to recovery partition.", "warn"),
    Op("FB", "fb.flash_dtbo",     "Flash dtbo.img",     "Flash a selected DTBO image to device-tree overlay.", "warn"),
    Op("FB", "fb.flash_vbmeta",   "Disable Verity",     "Flash vbmeta with verification disabled for repair workflows.", "warn"),
    Op("FB", "fb.boot_temp",      "Boot temp boot.img", "Boot an image once without flashing it.", "safe"),
    Op("FB", "fb.flash_zip",      "Flash firmware .zip","Extract and flash matching partition images from a firmware ZIP.", "warn"),
    Op("FB", "fb.getvar",         "Bootloader Info",    "Print all fastboot variables for identification and service logs."),
    Op("FB", "fb.slot",           "A/B Slot Manager",   "Show or switch active fastboot slot on A/B devices.", "warn", keywords=("slot", "set_active")),
    Op("FB", "fb.nuke",           "NUKE ALL ⚠",         "Erase key partitions irreversibly; last-resort lab use only.", "danger", needs_root=True),

    # ── Root ──────────────────────────────────────────────────────────────
    Op("ROOT", "root.magisk_pull",   "Pull Stock boot.img", "Read stock boot via mtkclient/edl/dd", "safe"),
    Op("ROOT", "root.magisk_install","Install Magisk APK",  "adb install latest Magisk + open it", "warn"),
    Op("ROOT", "root.magisk_flash",  "Flash Patched boot",  "fastboot flash boot magisk_patched.img", "warn"),
    Op("ROOT", "root.kernelsu",      "KernelSU Status",     "Check KernelSU module list (root)"),
    Op("ROOT", "root.shamiko",       "Shamiko Hide Tip",    "Print steps for hiding root from apps"),
    Op("ROOT", "root.check",         "Check Root",          "Detect su / Magisk / KernelSU"),

    # ── Mkopa / PAYG ──────────────────────────────────────────────────────
    Op("MKP", "mkp.remove_mdm",   "Remove MDM (ADB)",   "Clear Mkopa device-policy packages", "warn"),
    Op("MKP", "mkp.mtk_unlock",   "MTK Unlock",         "mtkclient payload → fastboot unlock", "warn"),
    Op("MKP", "mkp.qc_edl",       "Qualcomm EDL Unlock","edl.py erase frp + protect", "warn"),
    Op("MKP", "mkp.flash_stock",  "Flash Stock Firmware","Auto-detect Samsung / MTK / QC", "danger"),
    Op("MKP", "mkp.lock_bl",      "Lock Bootloader",    "Lock BL after stock restore", "warn"),
    Op("MKP", "mkp.payg_kiosk",   "Disable Kiosk App",  "Disable PAYG kiosk / lock app", "warn"),
    Op("MKP", "mkp.safcom",       "Safaricom Carrier Unlock", "Android handsets locked to Safaricom"),

    # ── iPhone ────────────────────────────────────────────────────────────
    Op("IOS", "ios.info",         "Info / UDID",        "Device info via libimobiledevice"),
    Op("IOS", "ios.pair",         "Pair / Trust",       "Pair and trust iPhone", "safe"),
    Op("IOS", "ios.backup",       "Backup",             "idevicebackup2 → backup dir", "safe"),
    Op("IOS", "ios.restore_ipsw",  "Restore IPSW",       "Restore a selected Apple IPSW with idevicerestore.", "danger", keywords=("firmware", "ipsw")),
    Op("IOS", "ios.diagnostics",   "Diagnostics",        "Collect iPhone diagnostics, syslog hint, and lockdown status.", "safe"),
    Op("IOS", "ios.dfu",          "DFU Guide",          "Step-by-step DFU instructions"),
    Op("IOS", "ios.passcode",     "Passcode Reset",     "Recovery + restore via iTunes / idevicerestore", "danger"),
    Op("IOS", "ios.jb_matrix",    "Jailbreak Matrix",   "2025 jailbreak compatibility chart"),
    Op("IOS", "ios.checkra1n",    "checkra1n (A5–A11)", "checkra1n GUI"),
    Op("IOS", "ios.palera1n",     "palera1n (A9–A17)",  "palera1n CLI"),
    Op("IOS", "ios.uncover",      "unc0ver (A12–A14)",  "Sideload unc0ver IPA"),
    Op("IOS", "ios.dopamine",     "Dopamine (A12–A15)", "Rootless A12-A15"),
    Op("IOS", "ios.serotonin",    "Serotonin (A12+)",   "RootHide rootless A12+"),
    Op("IOS", "ios.trollstore",   "TrollStore",         "Permanent IPA, no jailbreak"),
    Op("IOS", "ios.macdirtycow",  "MacDirtyCow",        "CVE-2022-46689 tweaks"),
    Op("IOS", "ios.ssh",          "SSH (post-JB)",      "ssh -p 2222 root@localhost"),
    Op("IOS", "ios.sideloadly",   "Sideloadly",         "Launch Sideloadly"),
    Op("IOS", "ios.activation",   "Activation Lock",    "Apple official path (deceased owner)"),

    # ── Feature Phone ─────────────────────────────────────────────────────
    Op("FTR", "ftr.at_info",      "AT Info",            "Model / IMEI / signal via AT"),
    Op("FTR", "ftr.imei",         "Read IMEI",          "Read handset IMEI from the selected serial modem."),
    Op("FTR", "ftr.factory",      "Factory Reset",      "AT reset (multi-brand)", "warn"),
    Op("FTR", "ftr.at_unlock",    "AT Network Unlock",  "Send an AT+CLCK network unlock code to a feature phone.", "warn"),
    Op("FTR", "ftr.nokia",        "Nokia JAF/Phoenix",  "Launch via Wine"),
    Op("FTR", "ftr.spft",         "SP Flash Tool",      "Launch SP Flash Tool"),
    Op("FTR", "ftr.dcunlock",     "DC-Unlocker",        "Launch dc-unlocker via Wine"),
    Op("FTR", "ftr.custom_at",     "Custom AT Command",  "Send one technician-entered AT command to the selected serial port.", "warn", keywords=("serial", "modem")),

    # ── Network Unlock ────────────────────────────────────────────────────
    Op("NET", "net.clck",         "AT+CLCK Carrier Unlock", "Send NCK via AT+CLCK=PN,0", "warn"),
    Op("NET", "net.attempts",     "Read Unlock Attempts",   "AT+CPIN? remaining attempts"),
    Op("NET", "net.nck_gen",      "NCK Generator (IMEI)",   "IMEI-based NCK hint + Luhn"),
    Op("NET", "net.qc_nv",        "Qualcomm NV SIM Unlock", "edl.py NV item 10", "warn"),
    Op("NET", "net.mtk_unlock",   "MTK Network Unlock",     "mtkclient + fastboot unlock", "warn"),
    Op("NET", "net.imei_check",   "IMEI Check (online)",    "Open imei.info in browser"),

    # ── MTK / EDL ─────────────────────────────────────────────────────────
    Op("MTK", "mtk.fastboot",     "MTK → Fastboot",     "mtkclient payload → FASTBOOT", "warn"),
    Op("MTK", "mtk.frp_erase",    "MTK FRP Erase",      "Payload + fastboot erase frp", "warn"),
    Op("MTK", "mtk.read",         "MTK Read Flash",     "Read preloader / boot / system", "safe"),
    Op("MTK", "edl.parts",        "EDL Partitions",     "edl.py partition table"),
    Op("MTK", "edl.frp",          "EDL Erase FRP",      "Erase frp + protect_f", "warn"),
    Op("MTK", "edl.full_read",    "EDL Read Full Flash","Full device flash dump", "safe"),
    Op("MTK", "edl.flash_part",   "EDL Flash Partition","Flash one partition", "warn"),
    Op("MTK", "mtk.detect",       "Chipset Detector",   "Probe connected device with ADB, fastboot, MTK, and EDL tools.", "safe", keywords=("qualcomm", "mediatek", "spreadtrum")),

    # ── Vendor ────────────────────────────────────────────────────────────
    Op("VND", "vnd.xiaomi",       "Xiaomi Unlock Wait", "mi-flash-unlock auth-wait guide"),
    Op("VND", "vnd.oppo",         "OPPO/Realme Codes",  "Engineering & deep-test dialer codes"),
    Op("VND", "vnd.huawei",       "Huawei Testpoint",   "DC-Phoenix + testpoint guide"),
    Op("VND", "vnd.samsung_dl",   "Samsung Download",   "Download Mode entry guide"),
    Op("VND", "vnd.samsung_frp",  "Samsung FRP Guide",  "Official-mode Samsung FRP and stock restore checklist.", "warn", keywords=("odin", "heimdall")),
    Op("VND", "vnd.lg",           "LG Bridge",          "LG Bridge / LGUP guide"),
    Op("VND", "vnd.motorola",     "Motorola Unlock",    "Motorola bootloader unlock-data collection and portal guide.", "warn"),
    Op("VND", "vnd.pixel",        "Google Pixel Tools", "Pixel fastboot flashing, slot, and factory-image helpers.", "warn"),

    # ── Maintenance ───────────────────────────────────────────────────────
    Op("MAINT", "mnt.udev",       "USB udev Rules",     "Install /etc/udev/rules.d/51-phone-liberator.rules", "safe"),
    Op("MAINT", "mnt.adb",        "ADB + Fastboot",     "apt install android-tools-adb/fastboot", "safe"),
    Op("MAINT", "mnt.platform",   "Platform Tools",     "Google official platform-tools", "safe"),
    Op("MAINT", "mnt.scrcpy",     "scrcpy",             "apt install scrcpy", "safe"),
    Op("MAINT", "mnt.mtkclient",  "mtkclient",          "git clone bkerler/mtkclient → /opt/", "safe"),
    Op("MAINT", "mnt.edl",        "edl.py",             "git clone bkerler/edl → /opt/", "safe"),
    Op("MAINT", "mnt.libimobile", "libimobiledevice",   "apt install idevice tools", "safe"),
    Op("MAINT", "mnt.iderestore", "idevicerestore",     "Build idevicerestore from source", "safe"),
    Op("MAINT", "mnt.checkra1n",  "checkra1n",          "Add checkra1n apt repo", "safe"),
    Op("MAINT", "mnt.palera1n",   "palera1n",           "Download palera1n binary", "safe"),
    Op("MAINT", "mnt.sideloadly", "Sideloadly",         "Open sideloadly.io + dpkg install", "safe"),
    Op("MAINT", "mnt.heimdall",   "Heimdall",           "apt install heimdall-flash", "safe"),
    Op("MAINT", "mnt.samloader",  "samloader",          "pip3 install samloader", "safe"),
    Op("MAINT", "mnt.spflash",    "SP Flash Tool",      "Open spflashtools.com/linux", "safe"),
    Op("MAINT", "mnt.pyserial",   "pyserial",           "pip3 install pyserial", "safe"),
    Op("MAINT", "mnt.pyusb",      "pyusb",              "pip3 install pyusb", "safe"),
    Op("MAINT", "mnt.spreadtrum", "Spreadtrum / SPD",   "Install research tooling and show SPD service-mode notes.", "safe", keywords=("unisoc", "spd")),
    Op("MAINT", "mnt.verify",     "Verify Toolchain",   "Check installed phone service tools and show versions.", "safe"),
    Op("MAINT", "mnt.wine",       "Wine",               "apt install wine wine32 wine64", "safe"),
    Op("MAINT", "mnt.all",        "Install ALL ⚡",     "Install every dependency in one shot", "safe"),
]

OP_BY_ID: dict[str, Op] = {o.op_id: o for o in OPS}


# ───────────────────────── Helpers ─────────────────────────
def shq(s: str) -> str:
    """Shell-quote *s* safely; empty / no-arg yields empty string."""
    if s in ("", None, "—", "?"):
        return ""
    return shlex.quote(str(s))


def ensure_dirs() -> None:
    for p in DEFAULT_PATHS.values():
        Path(p).mkdir(parents=True, exist_ok=True)


def _sudo_token_spans(cmd: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    command_expected = True
    i = 0
    while i < len(cmd):
        ch = cmd[i]
        if ch.isspace():
            if ch == "\n":
                command_expected = True
            i += 1
            continue
        if ch in ";|&":
            command_expected = True
            i += 2 if cmd[i:i + 2] in ("&&", "||") else 1
            continue
        start = i
        text: list[str] = []
        quoted = False
        quote = ""
        while i < len(cmd):
            ch = cmd[i]
            if quote:
                quoted = True
                if ch == quote:
                    quote = ""
                elif ch == "\\" and quote == '"' and i + 1 < len(cmd):
                    i += 1
                    text.append(cmd[i])
                else:
                    text.append(ch)
                i += 1
                continue
            if ch in ("'", '"'):
                quote = ch
                quoted = True
                i += 1
                continue
            if ch.isspace() or ch in ";|&":
                break
            if ch == "\\" and i + 1 < len(cmd):
                i += 1
                text.append(cmd[i])
            else:
                text.append(ch)
            i += 1
        word = "".join(text)
        if command_expected:
            if word == "sudo" and not quoted:
                spans.append((start, i))
                command_expected = False
            elif re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
                command_expected = True
            else:
                command_expected = False
    return spans


def has_sudo_command(cmd: str) -> bool:
    return bool(_sudo_token_spans(cmd))


def sudo_wrap(cmd: str, password: str) -> str:
    if not password:
        return cmd
    spans = _sudo_token_spans(cmd)
    if not spans:
        return cmd
    out: list[str] = []
    last = 0
    for start, end in spans:
        out.append(cmd[last:start])
        out.append("sudo -A -p ''")
        last = end
    out.append(cmd[last:])
    return "".join(out)


def sudo_askpass_prefix() -> str:
    script = (
        "ASKPASS=$(mktemp /tmp/phone-liberator-askpass.XXXXXX); "
        "printf '%s\\n' '#!/bin/sh' 'printf %s \"$PHONE_LIBERATOR_SUDO_PASSWORD\"' > \"$ASKPASS\"; "
        "chmod 700 \"$ASKPASS\"; export SUDO_ASKPASS=\"$ASKPASS\"; "
        "trap 'rm -f \"$ASKPASS\"' EXIT; "
    )
    return script


def open_terminal_cmd(cmd: str) -> str:
    """Build a shell command that launches *cmd* in any available terminal."""
    return (
        f"x-terminal-emulator -e bash -c {shq(cmd + '; exec bash')} 2>/dev/null "
        f"|| gnome-terminal -- bash -c {shq(cmd + '; exec bash')} 2>/dev/null "
        f"|| konsole -e bash -c {shq(cmd + '; exec bash')} 2>/dev/null "
        f"|| xfce4-terminal -e {shq('bash -c ' + shq(cmd + '; exec bash'))} 2>/dev/null "
        f"|| xterm -e bash -c {shq(cmd + '; exec bash')} 2>/dev/null "
        f"|| alacritty -e bash -c {shq(cmd + '; exec bash')} 2>/dev/null"
    )


def open_browser_cmd(url: str) -> str:
    return f"xdg-open {shq(url)} >/dev/null 2>&1 || sensible-browser {shq(url)}"


# ───────────────────────── Worker / Detector ─────────────────────────
class Worker(QThread):
    """Sequentially run shell commands, streaming output back to the GUI."""

    log = pyqtSignal(str, str)
    done = pyqtSignal(int)

    def __init__(self, cmds: list[str], label: str = "", sudo_password: str = "") -> None:
        super().__init__()
        self.cmds = cmds
        self.label = label
        self.sudo_password = sudo_password
        self._abort = False
        self._proc: subprocess.Popen | None = None

    def abort(self) -> None:
        self._abort = True
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    proc.terminate()
                except Exception:
                    pass

    def run(self) -> None:
        rc_final = 0
        for cmd in self.cmds:
            if self._abort:
                self.log.emit("[ABORTED]", "danger")
                self.done.emit(-1)
                return
            run_cmd = sudo_wrap(cmd, self.sudo_password)
            if self.sudo_password:
                run_cmd = sudo_askpass_prefix() + run_cmd
            log_cmd = cmd if not self.sudo_password else sudo_wrap(cmd, "••••••••")
            self.log.emit(f"$ {log_cmd}", "info")
            try:
                self._proc = subprocess.Popen(
                    run_cmd,
                    shell=True,
                    executable="/bin/bash",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True,
                    env={
                        **os.environ,
                        "PHONE_LIBERATOR_SUDO_PASSWORD": self.sudo_password,
                    } if self.sudo_password else None,
                )
                assert self._proc.stdout is not None
                for line in self._proc.stdout:
                    if self._abort:
                        try:
                            os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                        except Exception:
                            self._proc.terminate()
                        break
                    self.log.emit(line.rstrip("\n"), "text")
                self._proc.wait()
                rc = self._proc.returncode
                if rc != 0 and not self._abort:
                    self.log.emit(f"[exit {rc}]", "warn")
                    rc_final = rc
            except Exception as e:
                self.log.emit(f"[ERROR] {e}", "danger")
                rc_final = 1
        self.done.emit(-1 if self._abort else rc_final)


@dataclass
class Device:
    sn: str = ""
    brand: str = ""
    model: str = ""
    cpu: str = ""
    method: str = "adb"          # adb|fastboot|serial|ios|none
    android: str = "?"
    display: str = "No device detected"


class Detector(QThread):
    """Background device scan with strict timeouts so the GUI never hangs."""

    found = pyqtSignal(list)

    @staticmethod
    def _run(cmd: str, timeout: float = 4.0) -> str:
        try:
            return subprocess.check_output(
                cmd, shell=True, text=True, stderr=subprocess.DEVNULL, timeout=timeout
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            return ""

    def run(self) -> None:
        devs: list[Device] = []

        # ADB
        adb_out = self._run("adb devices -l")
        for line in adb_out.splitlines()[1:]:
            line = line.strip()
            if not line or "offline" in line or "unauthorized" in line:
                continue
            parts = line.split()
            sn = parts[0]
            raw = " ".join(parts[2:])
            props: dict[str, str] = {}
            for p in raw.split():
                if ":" in p:
                    k, _, v = p.partition(":")
                    props[k] = v
            brand = props.get("brand", "Android")
            model = props.get("model", sn[:12])
            cpu = self._run(f"adb -s {shq(sn)} shell getprop ro.hardware", 3).strip()
            android = self._run(
                f"adb -s {shq(sn)} shell getprop ro.build.version.release", 3
            ).strip()
            devs.append(
                Device(
                    sn=sn,
                    brand=brand,
                    model=model,
                    cpu=cpu,
                    method="adb",
                    android=android or "?",
                    display=f"{brand} {model}  [{sn[:10]}]  ADB",
                )
            )

        # Fastboot
        fb_out = self._run("fastboot devices")
        for line in fb_out.splitlines():
            parts = line.split()
            if not parts:
                continue
            sn = parts[0]
            devs.append(
                Device(
                    sn=sn,
                    brand="Fastboot",
                    model="Device",
                    method="fastboot",
                    display=f"Fastboot  [{sn[:14]}]",
                )
            )

        # iOS
        ios_out = self._run("idevice_id -l")
        for line in ios_out.splitlines():
            udid = line.strip()
            if not udid:
                continue
            name = self._run(f"ideviceinfo -u {shq(udid)} -k DeviceName", 3).strip() or "iPhone"
            ios = (
                self._run(f"ideviceinfo -u {shq(udid)} -k ProductVersion", 3).strip() or "?"
            )
            devs.append(
                Device(
                    sn=udid,
                    brand="Apple",
                    model=name,
                    method="ios",
                    android=ios,
                    display=f"Apple {name}  [{udid[:10]}]  iOS {ios}",
                )
            )

        # Serial / feature phones
        for port in ("/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"):
            if Path(port).exists():
                devs.append(
                    Device(
                        sn=port,
                        brand="Feature",
                        model="Phone",
                        method="serial",
                        display=f"Feature Phone  [{port}]",
                    )
                )

        if not devs:
            devs.append(Device())
        self.found.emit(devs)


# ───────────────────────── UI Widgets ─────────────────────────
class Toast(QLabel):
    """Lightweight bottom-right toast."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setStyleSheet(
            "padding:10px 16px; border-radius:8px;"
            "background:#313244; color:#cdd6f4;"
            "font-weight:500;"
        )
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_msg(self, msg: str, ms: int = 2200) -> None:
        self.setText(msg)
        self.adjustSize()
        if self.parent():
            pw = self.parent()
            assert isinstance(pw, QWidget)
            self.move(pw.width() - self.width() - 24, pw.height() - self.height() - 32)
        self.show()
        self.raise_()
        self._timer.start(ms)


class OpCard(QFrame):
    """A clickable card representing one operation."""

    triggered = pyqtSignal(str)

    def __init__(self, op: Op, theme: dict[str, str]) -> None:
        super().__init__()
        self.op = op
        self.setObjectName("opcard")
        self.setToolTip(f"<b>{op.label}</b><br>{op.desc}<br><br>ID: {op.op_id}")
        self.setMinimumWidth(280)
        self.setMinimumHeight(132)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        title = QLabel(op.label)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        hdr.addWidget(title, 1)

        sev_label, sev_fg, sev_bg = SEVERITY_BADGES.get(
            op.severity, SEVERITY_BADGES["normal"]
        )
        badge = QLabel(sev_label)
        badge.setProperty("class", "badge")
        badge.setStyleSheet(
            f"padding:1px 6px; border-radius:6px; font-size:9px; font-weight:700;"
            f"background:{theme[sev_bg]}; color:{theme[sev_fg]};"
        )
        hdr.addWidget(badge)
        if op.needs_root:
            r = QLabel("ROOT")
            r.setStyleSheet(
                f"padding:1px 6px; border-radius:6px; font-size:9px; font-weight:700;"
                f"background:{theme['surface3']}; color:{theme['warn']};"
            )
            hdr.addWidget(r)

        lay.addLayout(hdr)
        desc = QLabel(op.desc)
        desc.setObjectName("cardDesc")
        desc.setWordWrap(True)
        lay.addWidget(desc, 1)
        meta = QLabel(f"Tool ID: {op.op_id}")
        meta.setObjectName("cardDesc")
        meta.setToolTip("Use this ID when searching logs or reporting a tool issue.")
        lay.addWidget(meta)

        run_row = QHBoxLayout()
        run_row.addStretch()
        btn = QPushButton("Run ▸")
        btn.setObjectName("runBtn")
        btn.setToolTip(f"Run {op.label}: {op.desc}")
        if op.severity in ("safe", "warn", "danger"):
            btn.setProperty("severity", op.severity)
        btn.clicked.connect(lambda: self.triggered.emit(op.op_id))
        run_row.addWidget(btn)
        lay.addLayout(run_row)


class CategoryPage(QWidget):
    op_triggered = pyqtSignal(str)

    def __init__(self, cat: str, ops: list[Op], theme: dict[str, str]) -> None:
        super().__init__()
        self.cat = cat
        self._cards: list[OpCard] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 14, 20, 14)
        outer.setSpacing(10)

        title = next((name for key, name in CATEGORIES if key == cat), cat)
        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_lay = QHBoxLayout(hero)
        hero_lay.setContentsMargins(16, 12, 16, 12)
        hero_lay.setSpacing(10)
        text_lay = QVBoxLayout()
        text_lay.setSpacing(3)
        hero_title = QLabel(title)
        hero_title.setObjectName("heroTitle")
        text_lay.addWidget(hero_title)
        hero_desc = QLabel(CATEGORY_DESCRIPTIONS.get(cat, "Phone servicing tools."))
        hero_desc.setObjectName("heroDesc")
        hero_desc.setWordWrap(True)
        text_lay.addWidget(hero_desc)
        hero_lay.addLayout(text_lay, 1)
        count = QLabel(f"{len(ops)} tools")
        count.setObjectName("sectionHdr")
        hero_lay.addWidget(count)
        outer.addWidget(hero)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self.grid = QGridLayout(inner)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        for op in ops:
            card = OpCard(op, theme)
            card.triggered.connect(self.op_triggered)
            self._cards.append(card)

        self._relayout("")

    def _relayout(self, query: str) -> None:
        # Remove every widget currently in the grid (cards + empty-state label)
        # without destroying our cards — we re-add the visible ones below.
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            w = item.widget() if item else None
            if w is None:
                continue
            self.grid.removeWidget(w)
            if w not in self._cards:
                w.setParent(None)
                w.deleteLater()
        col_count = 2
        row = col = 0
        q = query.strip().lower()
        any_visible = False
        for card in self._cards:
            text = (
                card.op.label
                + " "
                + card.op.desc
                + " "
                + " ".join(card.op.keywords)
                + " "
                + card.op.op_id
            ).lower()
            if q and q not in text:
                card.hide()
                continue
            self.grid.addWidget(card, row, col)
            card.show()
            any_visible = True
            col += 1
            if col >= col_count:
                col = 0
                row += 1
        # bottom filler so cards stay top-aligned
        self.grid.setRowStretch(row + 1, 1)
        if not any_visible:
            empty = QLabel("No operations match your search.")
            empty.setObjectName("cardDesc")
            empty.setAlignment(Qt.AlignCenter)
            self.grid.addWidget(empty, 0, 0, 1, col_count)

    def filter(self, query: str) -> int:
        self._relayout(query)
        return sum(1 for c in self._cards if c.isVisible())


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget, settings: QSettings) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(540)
        self._s = settings
        form = QFormLayout(self)

        def _path_row(key: str, default: str) -> QHBoxLayout:
            le = QLineEdit(self._s.value(key, default))
            br = QPushButton("Browse…")
            br.setObjectName("flatBtn")

            def _pick() -> None:
                p = QFileDialog.getExistingDirectory(self, "Choose directory", le.text())
                if p:
                    le.setText(p)

            br.clicked.connect(_pick)
            row = QHBoxLayout()
            row.addWidget(le, 1)
            row.addWidget(br)
            self._inputs[key] = le
            return row

        self._inputs: dict[str, QLineEdit] = {}
        form.addRow("Backup directory:",   _path_row("backup_dir",   DEFAULT_PATHS["backup_dir"]))
        form.addRow("Firmware directory:", _path_row("firmware_dir", DEFAULT_PATHS["firmware_dir"]))
        form.addRow("Tools directory:",    _path_row("tools_dir",    DEFAULT_PATHS["tools_dir"]))
        form.addRow("Log directory:",      _path_row("log_dir",      DEFAULT_PATHS["log_dir"]))

        self._auto = QCheckBox("Auto-refresh devices every 5 s")
        self._auto.setChecked(self._s.value("auto_refresh", "false") == "true")
        form.addRow(self._auto)

        self._confirm = QCheckBox("Confirm before running DANGER operations")
        self._confirm.setChecked(self._s.value("confirm_danger", "true") != "false")
        form.addRow(self._confirm)

        self._save_log = QCheckBox("Save every session log to log dir")
        self._save_log.setChecked(self._s.value("save_logs", "false") == "true")
        form.addRow(self._save_log)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _save(self) -> None:
        for k, le in self._inputs.items():
            self._s.setValue(k, le.text())
        self._s.setValue("auto_refresh",   "true" if self._auto.isChecked() else "false")
        self._s.setValue("confirm_danger", "true" if self._confirm.isChecked() else "false")
        self._s.setValue("save_logs",      "true" if self._save_log.isChecked() else "false")
        for v in self._inputs.values():
            try:
                Path(v.text()).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        self.accept()


# ───────────────────────── Main App ─────────────────────────
class App(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(ORG_NAME, SETTINGS_NAME)
        ensure_dirs()
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self._theme_name = self.settings.value("theme", "dark")
        if self._theme_name not in THEMES:
            self._theme_name = "dark"
        self._devs: list[Device] = [Device()]
        self._worker: Worker | None = None
        self._history: list[str] = []
        self._op_started_at: float = 0.0
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._scan)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)

        self._build_ui()
        self._apply_theme()
        self._scan()
        if self.settings.value("auto_refresh", "false") == "true":
            self._poll_timer.start(5000)

    # ── UI construction ────────────────────────────────────────────────
    def _build_ui(self) -> None:
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        top = QFrame()
        top.setObjectName("topbar")
        top.setFixedHeight(54)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(16, 8, 16, 8)
        tl.setSpacing(10)

        title = QLabel(f"{APP_NAME}")
        title.setObjectName("bigTitle")
        tl.addWidget(title)
        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("cardDesc")
        tl.addWidget(ver)
        tl.addSpacing(20)

        tl.addWidget(QLabel("Device:"))
        self.dev_combo = QComboBox()
        self.dev_combo.setMinimumWidth(360)
        self.dev_combo.addItem("Click Scan to detect devices")
        self.dev_combo.currentIndexChanged.connect(self._update_status_dev)
        tl.addWidget(self.dev_combo, 1)

        self.btn_scan = QToolButton()
        self.btn_scan.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.btn_scan.setText("⟳ Scan")
        self.btn_scan.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_scan.setToolTip("Scan for devices  (Ctrl+R)")
        self.btn_scan.clicked.connect(self._scan)
        tl.addWidget(self.btn_scan)

        self.chk_auto = QCheckBox("Auto-refresh")
        self.chk_auto.setChecked(self.settings.value("auto_refresh", "false") == "true")
        self.chk_auto.toggled.connect(self._toggle_auto)
        tl.addWidget(self.chk_auto)

        tl.addSpacing(8)
        self.chk_rb = QCheckBox("Reboot after")
        tl.addWidget(self.chk_rb)
        tl.addSpacing(8)

        self.btn_theme = QToolButton()
        self.btn_theme.setText("☾" if self._theme_name == "dark" else "☼")
        self.btn_theme.setToolTip("Toggle theme  (Ctrl+T)")
        self.btn_theme.clicked.connect(self._toggle_theme)
        tl.addWidget(self.btn_theme)

        self.btn_settings = QToolButton()
        self.btn_settings.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.btn_settings.setText("⚙")
        self.btn_settings.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_settings.setToolTip("Settings  (Ctrl+,)")
        self.btn_settings.clicked.connect(self._open_settings)
        tl.addWidget(self.btn_settings)

        self.btn_abort = QPushButton("■ Abort")
        self.btn_abort.setObjectName("abortBtn")
        self.btn_abort.setEnabled(False)
        self.btn_abort.clicked.connect(self._abort)
        tl.addWidget(self.btn_abort)

        root.addWidget(top)

        # Body
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body_w = QWidget()
        body_w.setLayout(body)
        root.addWidget(body_w, 1)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(8, 12, 8, 8)
        sl.setSpacing(6)
        nav_hdr = QLabel("CATEGORIES")
        nav_hdr.setObjectName("sectionHdr")
        nav_hdr.setContentsMargins(8, 0, 0, 4)
        sl.addWidget(nav_hdr)

        self.nav = QListWidget()
        self.nav.setObjectName("sidebarList")
        for cat, name in CATEGORIES:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, cat)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._switch_cat)
        sl.addWidget(self.nav, 1)

        body.addWidget(sidebar)

        # Right side: search + pages + log
        right = QSplitter(Qt.Vertical)

        pages_w = QWidget()
        pages_lay = QVBoxLayout(pages_w)
        pages_lay.setContentsMargins(0, 0, 0, 0)
        pages_lay.setSpacing(0)

        # Search bar
        search_bar = QFrame()
        search_bar.setObjectName("topbar")
        sb = QHBoxLayout(search_bar)
        sb.setContentsMargins(20, 10, 20, 10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search operations…  (Ctrl+F)")
        self.search.textChanged.connect(self._filter_ops)
        sb.addWidget(self.search, 1)
        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("cardDesc")
        sb.addWidget(self.lbl_count)
        pages_lay.addWidget(search_bar)

        # Stack of category pages
        self.pages: dict[str, CategoryPage] = {}
        self.page_stack = QWidget()
        self.page_stack_lay = QVBoxLayout(self.page_stack)
        self.page_stack_lay.setContentsMargins(0, 0, 0, 0)
        self.page_stack_lay.setSpacing(0)
        for cat, _ in CATEGORIES:
            page = CategoryPage(cat, [o for o in OPS if o.cat == cat], THEMES[self._theme_name])
            page.op_triggered.connect(self._run)
            page.hide()
            self.pages[cat] = page
            self.page_stack_lay.addWidget(page)
        pages_lay.addWidget(self.page_stack, 1)

        right.addWidget(pages_w)

        # Log panel
        log_w = QWidget()
        log_lay = QVBoxLayout(log_w)
        log_lay.setContentsMargins(0, 0, 0, 0)
        log_lay.setSpacing(0)

        log_bar = QFrame()
        log_bar.setObjectName("statusframe")
        lb = QHBoxLayout(log_bar)
        lb.setContentsMargins(12, 6, 12, 6)
        lb.setSpacing(6)
        log_lbl = QLabel("OUTPUT")
        log_lbl.setObjectName("sectionHdr")
        lb.addWidget(log_lbl)
        lb.addStretch()
        for txt, slot, tip in (
            ("Save",  self._save_log,   "Save log to file (Ctrl+S)"),
            ("Copy",  self._copy_log,   "Copy log to clipboard"),
            ("Clear", self._clear_log,  "Clear log (Ctrl+L)"),
        ):
            b = QToolButton()
            b.setText(txt)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            lb.addWidget(b)
        log_lay.addWidget(log_bar)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(160)
        log_lay.addWidget(self.log_box, 1)

        right.addWidget(log_w)
        right.setSizes([560, 240])

        body.addWidget(right, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.lbl_status = QLabel("Idle")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_dev = QLabel("")
        self.lbl_dev.setObjectName("deviceLabel")
        self.lbl_elapsed = QLabel("")
        self.lbl_elapsed.setObjectName("statusLabel")
        self.status_bar.addWidget(self.lbl_status, 1)
        self.status_bar.addPermanentWidget(self.lbl_dev)
        self.status_bar.addPermanentWidget(self.lbl_elapsed)
        self.setStatusBar(self.status_bar)

        self.toast = Toast(self)

        # Default selected category
        self.nav.setCurrentRow(0)

        # Shortcuts
        self._shortcut(self, "Ctrl+R", self._scan)
        self._shortcut(self, "F5", self._scan)
        self._shortcut(self, "Ctrl+L", self._clear_log)
        self._shortcut(self, "Ctrl+S", self._save_log)
        self._shortcut(self, "Ctrl+,", self._open_settings)
        self._shortcut(self, "Ctrl+T", self._toggle_theme)
        self._shortcut(self, "Ctrl+F", lambda: (self.search.setFocus(), self.search.selectAll()))
        self._shortcut(self, "Esc", self._abort_or_clear_search)
        self._shortcut(self, "Ctrl+Q", self.close)

        self._log_intro()

    @staticmethod
    def _shortcut(parent: QWidget, keys: str, slot: Callable[[], None]) -> QShortcut:
        sc = QShortcut(QKeySequence(keys), parent)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(slot)
        return sc

    def _log_intro(self) -> None:
        self._log(
            f"{APP_NAME} v{APP_VERSION} ready — pick a category, search, and click Run.",
            "ok",
        )
        self._log(
            "Tips: Ctrl+F search · Ctrl+R scan · Ctrl+T theme · Ctrl+, settings · Esc abort.",
            "info",
        )

    # ── Theming ────────────────────────────────────────────────────────
    def _apply_theme(self) -> None:
        t = THEMES[self._theme_name]
        self.setStyleSheet(stylesheet(t))
        # Recreate pages so card badges pick up new theme colours
        for cat, page in self.pages.items():
            for card in page._cards:
                # rebuild the badge styles
                pass
        # Recreate cards entirely to refresh per-card stylesheet
        new_pages: dict[str, CategoryPage] = {}
        for cat, _name in CATEGORIES:
            old = self.pages[cat]
            self.page_stack_lay.removeWidget(old)
            old.setParent(None)
            page = CategoryPage(cat, [o for o in OPS if o.cat == cat], t)
            page.op_triggered.connect(self._run)
            page.hide()
            new_pages[cat] = page
            self.page_stack_lay.addWidget(page)
        self.pages = new_pages
        # show the previously-selected category
        cur = self.nav.currentRow()
        self._switch_cat(cur if cur >= 0 else 0)
        # also re-apply the current search filter
        self._filter_ops(self.search.text())

    def _toggle_theme(self) -> None:
        self._theme_name = "light" if self._theme_name == "dark" else "dark"
        self.settings.setValue("theme", self._theme_name)
        self.btn_theme.setText("☾" if self._theme_name == "dark" else "☼")
        self._apply_theme()

    # ── Settings / persistence ─────────────────────────────────────────
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self, self.settings)
        if dlg.exec_() == QDialog.Accepted:
            if self.settings.value("auto_refresh", "false") == "true":
                if not self._poll_timer.isActive():
                    self._poll_timer.start(5000)
            else:
                self._poll_timer.stop()
            self.chk_auto.setChecked(self._poll_timer.isActive())
            self.toast.show_msg("Settings saved")

    def _toggle_auto(self, on: bool) -> None:
        self.settings.setValue("auto_refresh", "true" if on else "false")
        if on:
            self._poll_timer.start(5000)
        else:
            self._poll_timer.stop()

    def _path(self, key: str) -> str:
        return self.settings.value(key, DEFAULT_PATHS[key])

    # ── Navigation / search ────────────────────────────────────────────
    def _switch_cat(self, row: int) -> None:
        if row < 0 or row >= len(CATEGORIES):
            return
        cat = CATEGORIES[row][0]
        for c, page in self.pages.items():
            page.setVisible(c == cat)
        self._filter_ops(self.search.text())

    def _filter_ops(self, query: str) -> None:
        cur_row = self.nav.currentRow()
        if cur_row < 0:
            return
        cat = CATEGORIES[cur_row][0]
        page = self.pages[cat]
        n = page.filter(query)
        total = sum(1 for o in OPS if o.cat == cat)
        if query.strip():
            self.lbl_count.setText(f"{n}/{total} match")
        else:
            self.lbl_count.setText(f"{total} ops")

    # ── Scanning ───────────────────────────────────────────────────────
    def _scan(self) -> None:
        # Guard against re-entry while a previous scan is still running.
        prev = getattr(self, "_det", None)
        try:
            if prev is not None and prev.isRunning():
                return
        except RuntimeError:
            pass  # underlying C++ object was deleted; safe to start a fresh one
        self.lbl_status.setText("Scanning devices…")
        d = Detector()
        d.found.connect(self._on_found)
        d.finished.connect(d.deleteLater)
        d.start()
        self._det = d

    def _on_found(self, devs: list[Device]) -> None:
        # Preserve previous selection by serial when possible
        prev_sn = self._cur_dev().sn
        self._devs = devs
        self.dev_combo.blockSignals(True)
        self.dev_combo.clear()
        for d in devs:
            self.dev_combo.addItem(d.display)
        self.dev_combo.blockSignals(False)
        # restore previous selection
        for i, d in enumerate(devs):
            if d.sn and d.sn == prev_sn:
                self.dev_combo.setCurrentIndex(i)
                break
        self._update_status_dev()
        self.lbl_status.setText("Idle")

    def _cur_dev(self) -> Device:
        idx = self.dev_combo.currentIndex()
        if 0 <= idx < len(self._devs):
            return self._devs[idx]
        return Device()

    def _update_status_dev(self) -> None:
        d = self._cur_dev()
        if d.sn:
            self.lbl_dev.setText(
                f"{d.brand} {d.model} · {d.method.upper()} · {d.android}"
            )
        else:
            self.lbl_dev.setText("No device")

    # ── Logging ────────────────────────────────────────────────────────
    def _log(self, msg: str, kind: str = "text") -> None:
        t = THEMES[self._theme_name]
        color = {
            "text":   t["text"],
            "info":   t["info"],
            "ok":     t["ok"],
            "warn":   t["warn"],
            "danger": t["danger"],
            "purple": t["purple"],
        }.get(kind, t["text"])
        self.log_box.setTextColor(QColor(color))
        self.log_box.append(msg)
        self.log_box.moveCursor(QTextCursor.End)

    def _clear_log(self) -> None:
        self.log_box.clear()
        self._log_intro()

    def _copy_log(self) -> None:
        QApplication.clipboard().setText(self.log_box.toPlainText())
        self.toast.show_msg("Log copied")

    def _save_log(self) -> None:
        log_dir = Path(self._path("log_dir"))
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(log_dir / f"liberator_{ts}.log")
        fn, _ = QFileDialog.getSaveFileName(self, "Save Log", default, "Log (*.log *.txt)")
        if not fn:
            return
        Path(fn).write_text(self.log_box.toPlainText(), encoding="utf-8")
        self.toast.show_msg(f"Saved {Path(fn).name}")

    # ── Running ops ────────────────────────────────────────────────────
    def _run(self, op_id: str) -> None:
        op = OP_BY_ID.get(op_id)
        if op is None:
            return
        if op.severity == "danger" and self.settings.value("confirm_danger", "true") != "false":
            r = QMessageBox.question(
                self,
                "Confirm DANGER",
                f"<b>{op.label}</b><br><br>{op.desc}<br><br>"
                "This is a destructive operation. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                self._log(f"[{op.label}] cancelled by user", "warn")
                return
        d = self._cur_dev()
        cmds = self._build(op, d)
        if cmds is None:
            return
        if not cmds:
            self._log(f"[{op.label}] — no commands generated", "warn")
            return
        sudo_password = ""
        if any(self._needs_sudo(c) for c in cmds):
            sudo_password = self._sudo_password(op)
            if sudo_password is None:
                self._log(f"[{op.label}] sudo password entry cancelled", "warn")
                return
        self._log("", "text")
        self._log(f"=== {op.label} ===", "purple")
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(1500)
        self._history.append(op.op_id)
        self._worker = Worker(cmds, op.label, sudo_password)
        self._worker.log.connect(self._log)
        self._worker.done.connect(self._done)
        self._worker.start()
        self._set_running(True, op.label)

    @staticmethod
    def _needs_sudo(cmd: str) -> bool:
        return has_sudo_command(cmd)

    def _sudo_password(self, op: Op) -> str | None:
        password, ok = QInputDialog.getText(
            self,
            "Sudo password required",
            f"{op.label} needs administrator access.\nEnter your Linux sudo password:",
            QLineEdit.Password,
            "",
        )
        if not ok:
            return None
        if not password:
            QMessageBox.warning(
                self,
                "Sudo password required",
                "Enter a sudo password or press Cancel to skip this operation.",
            )
            return None
        return password

    def _set_running(self, running: bool, label: str = "") -> None:
        self.btn_abort.setEnabled(running)
        self.lbl_status.setText(f"Running: {label}" if running else "Idle")
        if running:
            self._op_started_at = time.time()
            self._elapsed_timer.start(500)
        else:
            self._elapsed_timer.stop()
            self.lbl_elapsed.setText("")

    def _tick_elapsed(self) -> None:
        secs = int(time.time() - self._op_started_at)
        self.lbl_elapsed.setText(f"⏱ {secs // 60:02d}:{secs % 60:02d}")

    def _done(self, rc: int) -> None:
        self._set_running(False)
        if rc == 0:
            self._log("=== Done ===", "ok")
            self.toast.show_msg("Operation finished")
        elif rc == -1:
            self._log("=== Aborted ===", "danger")
            self.toast.show_msg("Aborted")
        else:
            self._log(f"=== Finished (exit {rc}) ===", "warn")
            self.toast.show_msg(f"Finished with exit {rc}")
        if self.settings.value("save_logs", "false") == "true":
            log_dir = Path(self._path("log_dir"))
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / f"liberator_{datetime.now():%Y%m%d_%H%M%S}.log").write_text(
                self.log_box.toPlainText(), encoding="utf-8"
            )

    def _abort(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._log("[User abort requested]", "danger")

    def _abort_or_clear_search(self) -> None:
        if self._worker and self._worker.isRunning():
            self._abort()
            return
        if self.search.text():
            self.search.clear()

    # ── Op resize handling for toast ───────────────────────────────────
    def resizeEvent(self, ev: QEvent) -> None:  # type: ignore[override]
        super().resizeEvent(ev)
        if self.toast.isVisible():
            self.toast.move(
                self.width() - self.toast.width() - 24,
                self.height() - self.toast.height() - 32,
            )

    # ── Operation builder ──────────────────────────────────────────────
    def _build(self, op: Op, dev: Device) -> list[str] | None:
        rb_a = f"; adb -s {shq(dev.sn)} reboot" if self.chk_rb.isChecked() else ""
        rb_f = f" && fastboot {('-s ' + shq(dev.sn)) if dev.sn else ''} reboot" if self.chk_rb.isChecked() else ""
        adb = f"adb -s {shq(dev.sn)}" if dev.sn else "adb"
        fs = f"-s {shq(dev.sn)}" if dev.sn else ""
        ser = dev.sn if (dev.sn and "/dev/tty" in dev.sn) else "/dev/ttyUSB0"
        backup_dir = self._path("backup_dir")
        firmware_dir = self._path("firmware_dir")
        tools_dir = self._path("tools_dir")
        brand = (dev.brand or "").lower()
        cpu = (dev.cpu or "").lower()
        meth = dev.method
        sn = dev.sn

        def _udid() -> str:
            return f"-u {shq(sn)}" if sn else ""

        # ── Device ─────────────────────────────────────────────────────
        if op.op_id == "dev.scan":
            self._scan()
            return []
        if op.op_id == "dev.info":
            if meth == "adb":
                return [
                    f"echo '=== Android device info ==='",
                    f"{adb} shell getprop ro.product.brand",
                    f"{adb} shell getprop ro.product.model",
                    f"{adb} shell getprop ro.build.version.release",
                    f"{adb} shell getprop ro.build.fingerprint",
                    f"{adb} shell getprop ro.product.cpu.abi",
                    f"{adb} shell getprop ro.boot.serialno",
                    f"{adb} shell dumpsys battery | head -20",
                    f"{adb} shell uname -a",
                    f"{adb} shell which su 2>/dev/null && echo 'su present' || echo 'no su'",
                    f"{adb} shell pm list packages | grep -iE 'magisk|kernelsu' || echo 'no magisk/kernelsu'",
                ]
            if meth == "fastboot":
                return [f"fastboot {fs} getvar all"]
            if meth == "ios":
                return [f"ideviceinfo {_udid()}"]
            return ["echo 'No device selected'"]
        if op.op_id == "dev.scrcpy":
            if meth != "adb":
                return ["echo 'scrcpy requires an ADB device'"]
            return [
                "which scrcpy >/dev/null 2>&1 || { echo 'Install scrcpy: Maintenance → scrcpy'; exit 1; }",
                f"scrcpy -s {shq(sn)} --max-size=1280 --max-fps=60 &",
            ]
        if op.op_id == "dev.screenrec":
            secs, ok = QInputDialog.getInt(self, "Screen record", "Seconds (max 180):", 30, 5, 180, 5)
            if not ok:
                return None
            dst = f"{backup_dir}/screenrec_{datetime.now():%Y%m%d_%H%M%S}.mp4"
            return [
                f"{adb} shell screenrecord --time-limit {secs} /sdcard/__rec.mp4",
                f"{adb} pull /sdcard/__rec.mp4 {shq(dst)}",
                f"{adb} shell rm /sdcard/__rec.mp4",
                f"echo 'Saved: {dst}'",
            ]
        if op.op_id == "dev.battery":
            return [f"{adb} shell dumpsys battery", f"{adb} shell cat /sys/class/power_supply/battery/uevent 2>/dev/null || true"]
        if op.op_id == "dev.network":
            return [
                f"{adb} shell ip addr show wlan0 2>/dev/null | head -10 || true",
                f"{adb} shell dumpsys wifi | grep -E 'mWifiInfo|SSID|BSSID|IP|RSSI' | head -10 || true",
                f"{adb} shell getprop net.dns1",
                f"{adb} shell getprop net.dns2",
            ]
        if op.op_id == "dev.terminal":
            if meth == "adb":
                cmd = f"{adb} shell"
            elif meth == "fastboot":
                cmd = "fastboot getvar all"
            elif meth == "ios":
                cmd = "ssh -p 2222 root@localhost"
            else:
                cmd = "screen /dev/ttyUSB0 115200"
            subprocess.Popen(open_terminal_cmd(cmd), shell=True, executable="/bin/bash")
            return []
        if op.op_id == "dev.reboot_menu":
            choices = {
                "System": f"{adb} reboot",
                "Recovery": f"{adb} reboot recovery",
                "Bootloader / Fastboot": f"{adb} reboot bootloader",
                "Sideload": f"{adb} reboot sideload",
            }
            choice, ok = QInputDialog.getItem(
                self, "Reboot target", "Choose reboot target:", list(choices), 0, False
            )
            if not ok:
                return None
            return [choices[choice]]

        # ── ADB ────────────────────────────────────────────────────────
        if op.op_id == "adb.lock_remove":
            return [
                f"{adb} shell su -c 'rm -f "
                "/data/system/locksettings.db /data/system/locksettings.db-shm "
                "/data/system/locksettings.db-wal /data/system/gesture.key "
                f"/data/system/password.key /data/system/pin.key' {rb_a}"
            ]
        if op.op_id == "adb.frp_bypass":
            return [
                f"{adb} shell content insert --uri content://settings/secure "
                "--bind name:s:user_setup_complete --bind value:s:1",
                f"{adb} shell content insert --uri content://settings/global "
                "--bind name:s:device_provisioned --bind value:s:1",
                f"{adb} shell settings put global setup_wizard_has_run 1 2>/dev/null || true",
                f"{adb} shell pm disable com.google.android.setupwizard 2>/dev/null || true",
            ]
        if op.op_id == "adb.backup_sd":
            dst = f"{backup_dir}/{sn or 'device'}_sdcard"
            Path(dst).mkdir(parents=True, exist_ok=True)
            return [f"{adb} pull /sdcard {shq(dst)}", f"echo 'Saved to {dst}'"]
        if op.op_id == "adb.install_apk":
            apk, _ = QFileDialog.getOpenFileName(self, "Select APK", "", "APK (*.apk)")
            return None if not apk else [f"{adb} install -r -g {shq(apk)}"]
        if op.op_id == "adb.sideload_zip":
            zf, _ = QFileDialog.getOpenFileName(self, "Select ZIP", "", "ZIP (*.zip)")
            return None if not zf else [f"{adb} sideload {shq(zf)}"]
        if op.op_id == "adb.reboot_fb":
            return [f"{adb} reboot bootloader"]
        if op.op_id == "adb.reboot_rec":
            return [f"{adb} reboot recovery"]
        if op.op_id == "adb.screenshot":
            dst = f"{backup_dir}/screen_{datetime.now():%Y%m%d_%H%M%S}.png"
            return [
                f"{adb} shell screencap -p /sdcard/__sc.png",
                f"{adb} pull /sdcard/__sc.png {shq(dst)}",
                f"{adb} shell rm /sdcard/__sc.png",
                f"echo 'Saved: {dst}'",
            ]
        if op.op_id == "adb.logcat":
            subprocess.Popen(open_terminal_cmd(f"{adb} logcat -v threadtime"), shell=True, executable="/bin/bash")
            return []
        if op.op_id == "adb.dump_props":
            return [f"{adb} shell getprop"]
        if op.op_id == "adb.sysinfo":
            return [
                f"{adb} shell uname -a",
                f"{adb} shell cat /proc/cpuinfo | head -25",
                f"{adb} shell cat /proc/meminfo | head -8",
                f"{adb} shell df -h /data /sdcard 2>/dev/null || {adb} shell df -h",
            ]
        if op.op_id == "adb.dns_override":
            host, ok = QInputDialog.getText(
                self,
                "Private DNS",
                "Hostname (e.g. dns.google) or empty to disable:",
                QLineEdit.Normal,
                "dns.google",
            )
            if not ok:
                return None
            if host:
                return [
                    f"{adb} shell settings put global private_dns_mode hostname",
                    f"{adb} shell settings put global private_dns_specifier {shq(host)}",
                ]
            return [f"{adb} shell settings put global private_dns_mode off"]
        if op.op_id == "adb.demo_mode":
            return [
                f"{adb} shell settings put global sysui_demo_allowed 1",
                f"{adb} shell am broadcast -a com.android.systemui.demo -e command enter",
                f"{adb} shell am broadcast -a com.android.systemui.demo -e command clock -e hhmm 0930",
                f"{adb} shell am broadcast -a com.android.systemui.demo -e command battery -e level 100 -e plugged false",
                f"{adb} shell am broadcast -a com.android.systemui.demo -e command network -e wifi show -e level 4",
                f"{adb} shell am broadcast -a com.android.systemui.demo -e command notifications -e visible false",
                "echo 'Demo mode ON. Run again with: am broadcast -a com.android.systemui.demo -e command exit'",
            ]
        if op.op_id == "adb.permissions":
            pkg, ok = QInputDialog.getText(self, "App Permissions", "Package:", QLineEdit.Normal, "")
            if not ok or not pkg:
                return None
            return [
                f"{adb} shell dumpsys package {shq(pkg)} | "
                "sed -n '/requested permissions:/,/install permissions:/p; /runtime permissions:/,/User 0:/p'"
            ]
        if op.op_id == "adb.intent":
            action, ok = QInputDialog.getText(
                self,
                "Launch Intent",
                "Action or component:",
                QLineEdit.Normal,
                "android.settings.SETTINGS",
            )
            if not ok or not action:
                return None
            data, ok2 = QInputDialog.getText(
                self, "Launch Intent", "Optional data URI:", QLineEdit.Normal, ""
            )
            if not ok2:
                return None
            if "/" in action and not action.startswith("android."):
                return [f"{adb} shell am start -n {shq(action)}" + (f" -d {shq(data)}" if data else "")]
            return [f"{adb} shell am start -a {shq(action)}" + (f" -d {shq(data)}" if data else "")]

        # ── Wi-Fi ADB ──────────────────────────────────────────────────
        if op.op_id == "wadb.tcpip":
            return [f"{adb} tcpip 5555", "echo 'Now disconnect USB and connect via Wi-Fi'"]
        if op.op_id == "wadb.connect":
            ipport, ok = QInputDialog.getText(
                self, "Connect Wi-Fi ADB", "host:port", QLineEdit.Normal, "192.168.1.100:5555"
            )
            return None if not ok or not ipport else [f"adb connect {shq(ipport)}"]
        if op.op_id == "wadb.pair":
            ipport, ok = QInputDialog.getText(
                self, "Pair (Android 11+)", "host:port from device:", QLineEdit.Normal, "192.168.1.100:37000"
            )
            if not ok or not ipport:
                return None
            code, ok2 = QInputDialog.getText(
                self, "Pair (Android 11+)", "6-digit pairing code:", QLineEdit.Normal, ""
            )
            if not ok2:
                return None
            return [
                f"echo 'Pairing with' {shq(ipport)}",
                f"echo {shq(code)} | adb pair {shq(ipport)}",
            ]
        if op.op_id == "wadb.disconnect":
            return ["adb disconnect"]
        if op.op_id == "wadb.list":
            return ["adb devices -l"]

        # ── App Manager ────────────────────────────────────────────────
        if op.op_id == "app.list":
            patt, ok = QInputDialog.getText(
                self, "List Packages", "Filter regex (empty = all):", QLineEdit.Normal, ""
            )
            if not ok:
                return None
            grep = f" | grep -iE {shq(patt)}" if patt else ""
            return [f"{adb} shell pm list packages -f{grep} | sort"]
        if op.op_id == "app.uninstall":
            pkg, ok = QInputDialog.getText(self, "Uninstall App", "Package:", QLineEdit.Normal, "")
            if not ok or not pkg:
                return None
            return [f"{adb} uninstall {shq(pkg)} || {adb} shell pm uninstall --user 0 {shq(pkg)}"]
        if op.op_id == "app.disable":
            pkg, ok = QInputDialog.getText(self, "Disable App", "Package:", QLineEdit.Normal, "")
            if not ok or not pkg:
                return None
            return [f"{adb} shell pm disable-user --user 0 {shq(pkg)}"]
        if op.op_id == "app.enable":
            pkg, ok = QInputDialog.getText(self, "Enable App", "Package:", QLineEdit.Normal, "")
            if not ok or not pkg:
                return None
            return [f"{adb} shell pm enable {shq(pkg)}"]
        if op.op_id == "app.clear":
            pkg, ok = QInputDialog.getText(self, "Clear Data", "Package:", QLineEdit.Normal, "")
            if not ok or not pkg:
                return None
            return [f"{adb} shell pm clear {shq(pkg)}"]
        if op.op_id == "app.extract":
            pkg, ok = QInputDialog.getText(self, "Extract APK", "Package:", QLineEdit.Normal, "")
            if not ok or not pkg:
                return None
            dst_dir = f"{backup_dir}/apks"
            Path(dst_dir).mkdir(parents=True, exist_ok=True)
            out_path = f"{dst_dir}/{pkg}.apk"
            return [
                f"PATH_APK=$({adb} shell pm path {shq(pkg)} | head -1 | cut -d: -f2 | tr -d '\\r')",
                'echo "$PATH_APK"',
                f'[ -n "$PATH_APK" ] && {adb} pull "$PATH_APK" {shq(out_path)} || echo \'package not found\'',
                f"echo 'Saved to' {shq(out_path)}",
            ]
        if op.op_id == "app.bloat":
            preset = [
                "com.facebook.katana", "com.facebook.system", "com.facebook.appmanager",
                "com.facebook.services", "com.netflix.partner.activation",
                "com.linkedin.android", "com.amazon.kindle",
                "com.microsoft.skydrive", "com.microsoft.office.outlook",
            ]
            return [f"{adb} shell pm disable-user --user 0 {shq(p)} 2>/dev/null || true" for p in preset] + [
                "echo 'Bloat disable preset complete (only those installed were affected).'"
            ]

        # ── Fastboot ──────────────────────────────────────────────────
        if op.op_id == "fb.oem_unlock":      return [f"fastboot {fs} oem unlock{rb_f}"]
        if op.op_id == "fb.flashing_unlock": return [f"fastboot {fs} flashing unlock{rb_f}"]
        if op.op_id == "fb.frp_erase":       return [f"fastboot {fs} erase frp{rb_f}"]
        if op.op_id == "fb.factory_reset":   return [f"fastboot {fs} -w{rb_f}"]
        if op.op_id == "fb.reboot":          return [f"fastboot {fs} reboot"]
        if op.op_id == "fb.lock_bl":         return [f"fastboot {fs} oem lock{rb_f}"]
        if op.op_id == "fb.flash_boot":
            img, _ = QFileDialog.getOpenFileName(self, "Select boot.img", "", "IMG (*.img)")
            return None if not img else [f"fastboot {fs} flash boot {shq(img)}{rb_f}"]
        if op.op_id == "fb.flash_recovery":
            img, _ = QFileDialog.getOpenFileName(self, "Select recovery.img", "", "IMG (*.img)")
            return None if not img else [f"fastboot {fs} flash recovery {shq(img)}{rb_f}"]
        if op.op_id == "fb.flash_dtbo":
            img, _ = QFileDialog.getOpenFileName(self, "Select dtbo.img", "", "IMG (*.img)")
            return None if not img else [f"fastboot {fs} flash dtbo {shq(img)}{rb_f}"]
        if op.op_id == "fb.flash_vbmeta":
            img, _ = QFileDialog.getOpenFileName(self, "Select vbmeta.img", "", "IMG (*.img)")
            if not img:
                return None
            return [f"fastboot {fs} --disable-verity --disable-verification flash vbmeta {shq(img)}{rb_f}"]
        if op.op_id == "fb.boot_temp":
            img, _ = QFileDialog.getOpenFileName(self, "Select boot.img", "", "IMG (*.img)")
            return None if not img else [f"fastboot {fs} boot {shq(img)}"]
        if op.op_id == "fb.flash_zip":
            zf, _ = QFileDialog.getOpenFileName(self, "Select firmware", "", "ZIP (*.zip)")
            if not zf:
                return None
            return [
                "rm -rf /tmp/_lfw && mkdir -p /tmp/_lfw",
                f"unzip -o {shq(zf)} -d /tmp/_lfw",
                "cd /tmp/_lfw && for p in preloader lk boot recovery system "
                "system_ext vendor vendor_dlkm product dtbo vbmeta vbmeta_system vbmeta_vendor; do "
                f"[ -f $p.img ] && fastboot {fs} flash $p $p.img && echo flashed $p || true; done",
                f"fastboot {fs} reboot",
            ]
        if op.op_id == "fb.getvar":
            return [f"fastboot {fs} getvar all 2>&1"]
        if op.op_id == "fb.slot":
            choice, ok = QInputDialog.getItem(
                self,
                "A/B Slot Manager",
                "Choose action:",
                ["Show current slot", "Set slot A", "Set slot B"],
                0,
                False,
            )
            if not ok:
                return None
            if choice == "Set slot A":
                return [f"fastboot {fs} --set-active=a", f"fastboot {fs} getvar current-slot 2>&1"]
            if choice == "Set slot B":
                return [f"fastboot {fs} --set-active=b", f"fastboot {fs} getvar current-slot 2>&1"]
            return [f"fastboot {fs} getvar current-slot 2>&1", f"fastboot {fs} getvar slot-count 2>&1"]
        if op.op_id == "fb.nuke":
            if meth == "fastboot":
                return [
                    "for p in system system_ext vendor product userdata cache "
                    "boot dtbo vbmeta vbmeta_system vbmeta_vendor; do "
                    f"fastboot {fs} erase $p 2>/dev/null && echo wiped $p || true; done",
                    f"fastboot {fs} reboot-bootloader",
                ]
            return [
                f"{adb} shell su -c '"
                "for blk in userdata frp; do "
                "b=$(readlink -f /dev/block/by-name/$blk 2>/dev/null); "
                "[ -n \"$b\" ] && dd if=/dev/zero of=$b bs=4096 count=2048 || true; "
                "done; reboot'"
            ]

        # ── Root ───────────────────────────────────────────────────────
        if op.op_id == "root.magisk_pull":
            dst = f"{backup_dir}/boot_stock_{datetime.now():%Y%m%d_%H%M%S}.img"
            if meth == "fastboot":
                return [
                    f"echo 'Reading boot via mtkclient (MTK) or use stock firmware extraction'",
                    f"[ -d /opt/mtkclient ] && python3 /opt/mtkclient/mtk r boot {shq(dst)} || echo 'Manual: extract boot.img from stock firmware zip'",
                ]
            return [
                f"{adb} shell su -c 'BLK=$(readlink -f /dev/block/by-name/boot); dd if=$BLK of=/sdcard/__boot.img bs=4M'",
                f"{adb} pull /sdcard/__boot.img {shq(dst)}",
                f"{adb} shell rm /sdcard/__boot.img",
                f"echo 'Stock boot.img → {dst}  Push to phone, patch in Magisk app, then Root → Flash Patched boot.'",
            ]
        if op.op_id == "root.magisk_install":
            return [
                "MAGISK_URL=$(curl -s https://api.github.com/repos/topjohnwu/Magisk/releases/latest | grep -oE 'https://[^\"]+Magisk-v[0-9.]+\\.apk' | head -1)",
                "echo \"Downloading $MAGISK_URL\"",
                f"curl -L -o /tmp/magisk.apk \"$MAGISK_URL\"",
                f"{adb} install -r /tmp/magisk.apk",
                f"{adb} shell monkey -p com.topjohnwu.magisk 1",
                "echo 'Open Magisk → Install → Select and Patch a File → choose stock boot.img from Root → Pull Stock boot.img output.'",
            ]
        if op.op_id == "root.magisk_flash":
            img, _ = QFileDialog.getOpenFileName(self, "Select magisk_patched.img", "", "IMG (*.img)")
            if not img:
                return None
            return [f"fastboot {fs} flash boot {shq(img)}{rb_f}"]
        if op.op_id == "root.kernelsu":
            return [
                f"{adb} shell su -c 'ksud module list 2>/dev/null || echo no-kernelsu'",
                f"{adb} shell ls /data/adb/ksu 2>/dev/null && echo 'KernelSU present' || echo 'No KernelSU'",
            ]
        if op.op_id == "root.shamiko":
            return [
                "echo '=== Hide root from apps ==='",
                "echo '1. In Magisk app → Settings → enable Zygisk + Enforce DenyList'",
                "echo '2. Add target apps to DenyList'",
                "echo '3. Install Shamiko module: github.com/LSPosed/LSPosed.github.io/releases'",
                "echo '4. Reboot. Apps should no longer detect root.'",
            ]
        if op.op_id == "root.check":
            return [
                f"{adb} shell which su 2>/dev/null && echo 'su present' || echo 'no su'",
                f"{adb} shell pm list packages | grep -iE 'magisk|kernelsu' || echo 'no manager apps'",
                f"{adb} shell getprop ro.build.tags",
                f"{adb} shell ls /system/xbin/su /system/bin/su 2>/dev/null || true",
            ]

        # ── Mkopa / PAYG ──────────────────────────────────────────────
        if op.op_id == "mkp.remove_mdm":
            # Use the serial-qualified `{adb}` inside the command-substitution
            # too, otherwise on multi-device hosts the inner `adb` may target
            # a different device than the outer commands.
            #
            # The ADMIN capture and the dpm removal must live in the *same*
            # bash invocation, otherwise the variable is lost between
            # subprocesses (Worker.run() spawns a fresh /bin/bash per item).
            admin_block = (
                f"ADMIN=$({adb} shell dumpsys device_policy 2>/dev/null | "
                "grep -oE '[a-z]+\\.mkopa\\.[a-z]+/[A-Za-z.]+' | head -1); "
                f'[ -n "$ADMIN" ] && {adb} shell dpm remove-active-admin '
                '"$ADMIN" 2>/dev/null || true'
            )
            return [
                f"{adb} shell pm list packages | grep -iE 'mkopa|mdm|devicepolicy' || true",
                f"{adb} shell pm clear com.mkopa.devicesecurity 2>/dev/null || true",
                f"{adb} shell pm clear com.mkopa.devicemanager  2>/dev/null || true",
                admin_block,
                "echo 'MDM removal attempted'",
                f"{adb} reboot",
            ]
        if op.op_id == "mkp.mtk_unlock":
            return [
                "[ -d /opt/mtkclient ] || { echo 'Install mtkclient: Maintenance tab'; exit 1; }",
                "python3 /opt/mtkclient/mtk payload --metamode FASTBOOT",
                "sleep 4",
                "fastboot oem unlock",
                "fastboot erase frp",
                "fastboot erase userdata",
                "fastboot reboot",
            ]
        if op.op_id == "mkp.qc_edl":
            return [
                "[ -d /opt/edl ] || { echo 'Install edl.py: Maintenance tab'; exit 1; }",
                "python3 /opt/edl/edl.py partition 2>/dev/null | head -20 || true",
                "python3 /opt/edl/edl.py e frp 2>/dev/null || true",
                "python3 /opt/edl/edl.py e protect_f 2>/dev/null || true",
                "python3 /opt/edl/edl.py reset",
            ]
        if op.op_id == "mkp.flash_stock":
            fw = firmware_dir
            Path(fw).mkdir(parents=True, exist_ok=True)
            if "samsung" in brand:
                return [
                    f"echo '=== Samsung stock flash: {dev.model} ==='",
                    f"which samloader >/dev/null 2>&1 && samloader -m {shq(dev.model)} -r DBT -O {shq(fw)} || echo 'Install samloader: Maintenance tab'",
                    f"echo 'Place .tar.md5 in {fw}/ then enter Download Mode (Vol Down + Bixby/Home + Power)'",
                    f"which heimdall >/dev/null 2>&1 || echo 'Install Heimdall: Maintenance tab'",
                    f"ls {shq(fw)}/*.tar.md5 2>/dev/null | head -3 || echo 'No .tar.md5 files yet'",
                    "echo 'After flash: Mkopa/PAYG → Lock Bootloader'",
                ]
            if "mediatek" in cpu or meth == "mtk":
                return [
                    f"echo '=== MTK stock flash: {dev.model} ==='",
                    f"echo 'Place firmware .zip in {fw}/'",
                    f"ls {shq(fw)}/*.zip 2>/dev/null | head -1 | while read z; do unzip -o \"$z\" -d {shq(fw)}/extracted; done || true",
                    "echo 'Open SP Flash Tool: Feature tab → SP Flash Tool'",
                    "echo 'Load scatter file → Download Only → Download'",
                    "echo 'After flash: Mkopa/PAYG → Lock Bootloader'",
                ]
            return [
                f"echo '=== QC/Generic stock flash: {dev.model} ==='",
                f"echo 'Place firmware .zip in {fw}/'",
                f"ls {shq(fw)}/*.zip 2>/dev/null | head -1 | while read z; do mkdir -p /tmp/_fw && unzip -o \"$z\" -d /tmp/_fw; done",
                f"cd /tmp/_fw 2>/dev/null && for img in *.img; do [ -f \"$img\" ] && fastboot {fs} flash \"${{img%.img}}\" \"$img\" || true; done",
                f"fastboot {fs} -w",
                f"fastboot {fs} reboot",
                "echo 'After flash: Mkopa/PAYG → Lock Bootloader'",
            ]
        if op.op_id == "mkp.lock_bl":
            return [
                "echo '=== Locking bootloader (device must be in fastboot) ==='",
                f"fastboot {fs} oem lock 2>/dev/null || fastboot {fs} flashing lock",
                "echo 'Bootloader locked. Mkopa software will NOT reinstall.'",
                f"fastboot {fs} reboot",
            ]
        if op.op_id == "mkp.payg_kiosk":
            return [
                f"{adb} shell pm list packages | grep -iE 'lock|kiosk|payg|mkopa|safaricom' || true",
                f"{adb} shell settings put global policy_control immersive.full=* 2>/dev/null || true",
                "echo 'Run: adb shell pm disable <package> for permanent fix'",
            ]
        if op.op_id == "mkp.safcom":
            return [
                "echo '=== Android Safaricom Carrier Unlock ==='",
                "echo 'For Android handsets manufactured SIM-locked to Safaricom'",
                f"{adb} shell service call iphonesubinfo 1 2>/dev/null | "
                "grep -oP \"'[0-9.]+'\" | tr -d \"'. \" || echo 'Dial *#06# for IMEI'",
                "echo 'Call Safaricom 100 or visit My Safaricom App → Device Unlock'",
                "echo 'Bring IMEI + National ID + proof of purchase to any Safaricom shop'",
            ]

        # ── iPhone ─────────────────────────────────────────────────────
        if op.op_id == "ios.info":
            return [f"ideviceinfo {_udid()}"]
        if op.op_id == "ios.pair":
            return [f"idevicepair {_udid()} pair", "echo 'Tap Trust on the iPhone if prompted'"]
        if op.op_id == "ios.backup":
            dst = f"{backup_dir}/iphone_{sn or 'device'}_{datetime.now():%Y%m%d_%H%M%S}"
            Path(dst).mkdir(parents=True, exist_ok=True)
            return [f"idevicebackup2 {_udid()} backup --full {shq(dst)}", f"echo 'Saved: {dst}'"]
        if op.op_id == "ios.restore_ipsw":
            ipsw, _ = QFileDialog.getOpenFileName(self, "Select IPSW", firmware_dir, "IPSW (*.ipsw)")
            if not ipsw:
                return None
            mode, ok = QInputDialog.getItem(
                self,
                "Restore IPSW",
                "Restore mode:",
                ["Update/restore without erase where supported", "Erase restore"],
                0,
                False,
            )
            if not ok:
                return None
            erase_flag = "-e " if mode == "Erase restore" else ""
            return [
                "which idevicerestore >/dev/null 2>&1 || { echo 'Install idevicerestore: Maintenance'; exit 1; }",
                f"idevicerestore {erase_flag}{_udid()} {shq(ipsw)}",
            ]
        if op.op_id == "ios.diagnostics":
            return [
                f"idevicepair {_udid()} validate 2>&1 || true",
                f"ideviceinfo {_udid()} -k ProductType -k ProductVersion -k SerialNumber 2>&1 || ideviceinfo {_udid()}",
                f"idevicediagnostics {_udid()} diagnostics 2>&1 || true",
                "echo 'Live syslog: run idevicesyslog in a terminal if deeper logs are needed.'",
            ]
        if op.op_id == "ios.dfu":
            # The DFU button-combo depends on the iPhone *model*, not the iOS
            # version. Read the ProductType from libimobiledevice and pick
            # instructions from that; print all three combos as a fallback so
            # the user can always follow the correct one.
            #
            # The whole detect-and-switch must live in ONE bash invocation,
            # otherwise $PT is lost and the case/esac fragments each become
            # syntactically invalid (Worker.run() spawns a fresh /bin/bash
            # per list item).
            udid = _udid()
            dfu_script = "\n".join([
                "echo '=== iPhone DFU Guide ==='",
                f"PT=$(ideviceinfo {udid} -k ProductType 2>/dev/null || true)",
                'echo "Detected ProductType: ${PT:-unknown}"',
                'case "$PT" in',
                '  iPhone1,*|iPhone2,*|iPhone3,*|iPhone4,*|iPhone5,*|iPhone6,*|iPhone7,*|iPhone8,*)',
                "    echo 'iPhone 4S-6s/SE1: hold Home+Power 10s -> release Power, keep Home 5s' ;;",
                '  iPhone9,*)',
                "    echo 'iPhone 7/7+: hold Side+Vol Down 10s -> release Side, keep Vol Down 5s' ;;",
                '  iPhone10,*|iPhone11,*|iPhone12,*|iPhone13,*|iPhone14,*|iPhone15,*|iPhone16,*|iPhone17,*)',
                "    echo 'iPhone 8 / X / 11 / 12 / 13 / 14 / 15 / 16: quick-press Vol Up, quick-press Vol Down, hold Side 10s, then hold Side+Vol Down 5s, release Side, keep Vol Down 5s' ;;",
                '  *)',
                "    echo 'Unknown / no device. All combos:'",
                "    echo '  4S-6s/SE1: Home+Power 10s -> release Power, keep Home 5s'",
                "    echo '  7/7+    : Side+Vol Down 10s -> release Side, keep Vol Down 5s'",
                "    echo '  8+      : Vol Up tap, Vol Down tap, hold Side 10s, then Side+Vol Down 5s, release Side, keep Vol Down 5s'",
                "    ;;",
                'esac',
            ])
            return [dfu_script, "idevice_id -l"]
        if op.op_id == "ios.passcode":
            return [
                "echo 'WARNING: full device erase — all data lost'",
                f"ideviceenterrecovery {_udid() or shq(sn)} 2>/dev/null || true",
                "echo 'Connect to iTunes/Finder and click Restore'",
                "echo 'Linux: idevicerestore -e <firmware.ipsw>'",
            ]
        if op.op_id == "ios.jb_matrix":
            return [
                "echo '=== iPhone Jailbreak Matrix (2025) ==='",
                f"echo 'Device: {dev.model}  iOS: {dev.android}'",
                "echo 'checkra1n  A5-A11  iOS 12-14.8.1  5s/6/6s/SE1/7/8/X'",
                "echo 'palera1n   A9-A17  iOS 15-17.0    6s-15 Pro Max (tethered A9-A11)'",
                "echo 'unc0ver    A12-A14 iOS 11-14.8    XS/11/12 via Sideloadly'",
                "echo 'Dopamine   A12-A15 iOS 15-16.6.1  XS-13 rootless'",
                "echo 'Serotonin  A12+    iOS 16.0-16.6.1 RootHide rootless'",
                "echo 'TrollStore A9+     iOS 14-17.0    no jailbreak needed'",
                "echo 'MacDirtyCow A9+    iOS 15-16.1.2  CVE-2022-46689'",
                "echo 'iPhone 16 Pro A18: NO public jailbreak as of 2025'",
            ]
        if op.op_id == "ios.checkra1n":
            return [
                "[ -x /usr/local/bin/checkra1n ] || { echo 'Not installed → Maintenance → checkra1n'; exit 1; }",
                "echo 'Put device in DFU mode first'",
                "checkra1n -G &",
            ]
        if op.op_id == "ios.palera1n":
            return [
                "[ -x /usr/local/bin/palera1n ] || { echo 'Not installed → Maintenance → palera1n'; exit 1; }",
                f"palera1n {_udid()} 2>&1",
                "echo 'Tip: palera1n -l for tethered A9-A11'",
            ]
        if op.op_id == "ios.uncover":
            return [
                "echo 'unc0ver: A12-A14, iOS 11-14.8 via Sideloadly'",
                "echo 'Get from unc0ver.dev'",
                "which sideloadly >/dev/null 2>&1 && sideloadly & || echo 'Install Sideloadly: Maintenance'",
            ]
        if op.op_id == "ios.dopamine":
            return [
                "echo 'Dopamine: A12-A15, iOS 15-16.6.1, rootless'",
                "echo 'Get from ellekit.space/dopamine'",
                "which sideloadly >/dev/null 2>&1 && sideloadly & || echo 'Install Sideloadly: Maintenance'",
            ]
        if op.op_id == "ios.serotonin":
            return [
                "echo 'Serotonin: A12+, iOS 16.0-16.6.1, rootless'",
                "echo 'Get from github.com/RootHide/Serotonin/releases'",
                "which sideloadly >/dev/null 2>&1 && sideloadly & || echo 'Install Sideloadly: Maintenance'",
            ]
        if op.op_id == "ios.trollstore":
            return [
                "echo 'TrollStore: permanent IPA, no jailbreak, iOS 14-17, A9+'",
                "echo 'METHOD A: TrollInstallerX → github.com/opa334/TrollInstallerX'",
                f"echo 'METHOD B (iOS 14-15.4 A9-A12): ideviceinstaller {_udid()} -i TrollHelper.ipa'",
                "which sideloadly >/dev/null 2>&1 && sideloadly & || echo 'Install Sideloadly: Maintenance'",
            ]
        if op.op_id == "ios.macdirtycow":
            return [
                "echo 'MacDirtyCow: CVE-2022-46689, iOS 15-16.1.2'",
                "echo 'Cowabunga: github.com/leminlimez/Cowabunga/releases'",
                "which sideloadly >/dev/null 2>&1 && sideloadly & || echo 'Install Sideloadly: Maintenance'",
            ]
        if op.op_id == "ios.ssh":
            return ["ssh -o StrictHostKeyChecking=no -p 2222 root@localhost"]
        if op.op_id == "ios.sideloadly":
            return ["which sideloadly >/dev/null 2>&1 && sideloadly & || echo 'Install Sideloadly: Maintenance'"]
        if op.op_id == "ios.activation":
            return [
                "echo '=== Activation Lock: Deceased Owner (Apple official path) ==='",
                "echo 'iPhone 16 Pro A18: NO software bypass exists in 2025'",
                "echo 'Required: death certificate + ownership proof + your national ID'",
                f"ideviceinfo {_udid()} -k SerialNumber 2>/dev/null || echo 'Check original box for serial number'",
                "echo 'Submit to Apple: support.apple.com/en-us/HT208054'",
            ]

        # ── Feature Phone ──────────────────────────────────────────────
        if op.op_id == "ftr.at_info":
            return [
                f"echo '=== AT info on {ser} ==='",
                f"(echo 'AT' && sleep 1 && echo 'ATI' && sleep 1 && echo 'AT+CGMM' && sleep 1 && echo 'AT+CGSN' && sleep 1 && echo 'AT+CSQ' && sleep 1) | "
                f"timeout 8 socat - file:{shq(ser)},raw,echo=0,b115200 || echo 'No response on {ser} (try Feature Phone tab → DC-Unlocker)'",
            ]
        if op.op_id == "ftr.imei":
            return [f"(echo AT+CGSN; sleep 1) | timeout 5 socat - file:{shq(ser)},raw,echo=0,b115200"]
        if op.op_id == "ftr.factory":
            return [
                f"echo '=== Sending common factory-reset AT codes to {ser} ==='",
                f"(echo 'AT&F' && sleep 1 && echo 'AT+CFUN=1,1' && sleep 1 && echo '*#7370#' && sleep 1) | "
                f"timeout 8 socat - file:{shq(ser)},raw,echo=0,b115200",
            ]
        if op.op_id == "ftr.at_unlock":
            nck, ok = QInputDialog.getText(self, "AT Unlock", "NCK code:", QLineEdit.Normal, "")
            if not ok or not nck:
                return None
            # Build the AT command in Python and feed it to the modem via a
            # single shell argument that goes through `shq()` so the user's
            # NCK value cannot escape into the surrounding shell context.
            at = f'AT+CLCK="PN",0,"{nck}"'
            return [
                f"(printf '%s\\r\\n' {shq(at)}; sleep 2) | timeout 5 socat - file:{shq(ser)},raw,echo=0,b115200"
            ]
        if op.op_id == "ftr.nokia":
            return [
                f"which wine >/dev/null 2>&1 || {{ echo 'Install Wine: Maintenance → Wine'; exit 1; }}",
                f"ls {shq(tools_dir)}/JAF*.exe {shq(tools_dir)}/Phoenix*.exe 2>/dev/null || echo 'Place JAF.exe / Phoenix.exe in {tools_dir}'",
                f"cd {shq(tools_dir)} && wine JAF*.exe 2>/dev/null & disown; true",
            ]
        if op.op_id == "ftr.spft":
            return [open_browser_cmd("https://spflashtools.com/linux"),
                    "echo 'Once installed, run flash_tool.sh from the SP Flash Tool dir'"]
        if op.op_id == "ftr.dcunlock":
            return [
                f"which wine >/dev/null 2>&1 || {{ echo 'Install Wine: Maintenance → Wine'; exit 1; }}",
                f"ls {shq(tools_dir)}/dc-unlocker2client.exe 2>/dev/null || echo 'Download from dc-unlocker.com → place in {tools_dir}'",
                f"cd {shq(tools_dir)} && wine dc-unlocker2client.exe 2>/dev/null & disown; true",
            ]
        if op.op_id == "ftr.custom_at":
            at, ok = QInputDialog.getText(self, "Custom AT Command", "AT command:", QLineEdit.Normal, "AT")
            if not ok or not at:
                return None
            if not at.upper().startswith("AT"):
                QMessageBox.warning(self, "Custom AT Command", "Command must start with AT.")
                return None
            return [
                f"(printf '%s\\r\\n' {shq(at)}; sleep 2) | timeout 8 socat - file:{shq(ser)},raw,echo=0,b115200"
            ]

        # ── Network Unlock ─────────────────────────────────────────────
        if op.op_id == "net.clck":
            nck, ok = QInputDialog.getText(self, "AT+CLCK Unlock", "NCK code:", QLineEdit.Normal, "")
            if not ok or not nck:
                return None
            at = f'AT+CLCK="PN",0,"{nck}"'
            return [
                f"(printf '%s\\r\\n' {shq(at)}; sleep 2) | timeout 5 socat - file:{shq(ser)},raw,echo=0,b115200"
            ]
        if op.op_id == "net.attempts":
            return [f"(echo 'AT+CPIN?' && sleep 1) | timeout 5 socat - file:{shq(ser)},raw,echo=0,b115200"]
        if op.op_id == "net.nck_gen":
            imei, ok = QInputDialog.getText(self, "NCK Generator", "IMEI:", QLineEdit.Normal, "")
            if not ok or not imei:
                return None
            # Reject obviously bogus inputs up-front (defense in depth) and
            # pass the value as `argv` to python3 so it cannot break out of
            # the shell *or* python string contexts.
            if not imei.isdigit() or not (8 <= len(imei) <= 17):
                QMessageBox.warning(self, "NCK Generator",
                                    "IMEI must be 8–17 digits.")
                return None
            py = (
                "import sys; i=sys.argv[1]; "
                "s=sum((2*int(d)-9 if 2*int(d)>9 else 2*int(d)) "
                "if (len(i)-idx-1)%2 else int(d) for idx,d in enumerate(i)); "
                "print('Luhn valid:', s%10==0)"
            )
            return [
                f"echo 'Calculating NCK hint for IMEI' {shq(imei)}",
                f"python3 -c {shq(py)} {shq(imei)}",
                "echo 'Note: real NCK requires the carrier MCC+MNC + master keys; "
                "use a paid IMEI service if needed.'",
            ]
        if op.op_id == "net.qc_nv":
            return [
                "[ -d /opt/edl ] || { echo 'Install edl.py: Maintenance tab'; exit 1; }",
                "python3 /opt/edl/edl.py nv 10",
                "echo 'NV item 10 read. Modify only if you know the carrier lock layout.'",
            ]
        if op.op_id == "net.mtk_unlock":
            return [
                "[ -d /opt/mtkclient ] || { echo 'Install mtkclient: Maintenance tab'; exit 1; }",
                "python3 /opt/mtkclient/mtk payload --metamode FASTBOOT",
                "sleep 4",
                "fastboot oem unlock",
                "fastboot reboot",
            ]
        if op.op_id == "net.imei_check":
            return [open_browser_cmd("https://imei.info")]

        # ── MTK / EDL ─────────────────────────────────────────────────
        if op.op_id == "mtk.fastboot":
            return [
                "[ -d /opt/mtkclient ] || { echo 'Install mtkclient: Maintenance tab'; exit 1; }",
                "python3 /opt/mtkclient/mtk payload --metamode FASTBOOT",
            ]
        if op.op_id == "mtk.frp_erase":
            return [
                "[ -d /opt/mtkclient ] || { echo 'Install mtkclient: Maintenance tab'; exit 1; }",
                "python3 /opt/mtkclient/mtk payload --metamode FASTBOOT",
                "sleep 4",
                "fastboot erase frp",
                "fastboot reboot",
            ]
        if op.op_id == "mtk.read":
            dst = f"{backup_dir}/mtk_{datetime.now():%Y%m%d_%H%M%S}"
            Path(dst).mkdir(parents=True, exist_ok=True)
            return [
                "[ -d /opt/mtkclient ] || { echo 'Install mtkclient: Maintenance tab'; exit 1; }",
                f"cd {shq(dst)} && python3 /opt/mtkclient/mtk r preloader,boot,system",
                f"echo 'Saved: {dst}'",
            ]
        if op.op_id == "edl.parts":
            return [
                "[ -d /opt/edl ] || { echo 'Install edl.py: Maintenance tab'; exit 1; }",
                "python3 /opt/edl/edl.py partition",
            ]
        if op.op_id == "edl.frp":
            return [
                "[ -d /opt/edl ] || { echo 'Install edl.py: Maintenance tab'; exit 1; }",
                "python3 /opt/edl/edl.py e frp",
                "python3 /opt/edl/edl.py e protect_f 2>/dev/null || true",
                "python3 /opt/edl/edl.py reset",
            ]
        if op.op_id == "edl.full_read":
            dst = f"{backup_dir}/edl_full_{datetime.now():%Y%m%d_%H%M%S}.bin"
            return [
                "[ -d /opt/edl ] || { echo 'Install edl.py: Maintenance tab'; exit 1; }",
                f"python3 /opt/edl/edl.py rf {shq(dst)}",
                f"echo 'Saved: {dst}'",
            ]
        if op.op_id == "edl.flash_part":
            part, ok = QInputDialog.getText(self, "EDL Flash", "Partition name (e.g. boot):", QLineEdit.Normal, "boot")
            if not ok or not part:
                return None
            img, _ = QFileDialog.getOpenFileName(self, "Select image", "", "IMG (*.img *.bin)")
            if not img:
                return None
            return [
                "[ -d /opt/edl ] || { echo 'Install edl.py: Maintenance tab'; exit 1; }",
                f"python3 /opt/edl/edl.py w {shq(part)} {shq(img)}",
                "python3 /opt/edl/edl.py reset",
            ]
        if op.op_id == "mtk.detect":
            return [
                "echo '=== Android / bootloader probes ==='",
                "adb devices -l 2>/dev/null || true",
                "fastboot devices 2>/dev/null || true",
                "echo '=== USB IDs ==='",
                "lsusb | grep -Ei 'google|android|samsung|qualcomm|qcom|mediatek|mtk|unisoc|spreadtrum|apple|motorola|xiaomi|oppo|realme|huawei|lg|nokia' || lsusb",
                "echo '=== MTK / EDL tooling ==='",
                "[ -d /opt/mtkclient ] && python3 /opt/mtkclient/mtk printgpt 2>/dev/null || echo 'mtkclient not installed or no BROM device'",
                "[ -d /opt/edl ] && python3 /opt/edl/edl.py printgpt 2>/dev/null || echo 'edl.py not installed or no EDL device'",
            ]

        # ── Vendor ────────────────────────────────────────────────────
        if op.op_id == "vnd.xiaomi":
            return [
                "echo '=== Xiaomi mi-flash-unlock guide ==='",
                "echo '1. en.miui.com/unlock — request unlock + tie account to phone'",
                "echo '2. Wait the imposed cooldown (168h–720h on newer MIUI/HyperOS).'",
                "echo '3. On Linux run miflash_unlock under wine + plug device in fastboot.'",
                f"fastboot {fs} oem device-info 2>&1",
                f"fastboot {fs} oem get_unlock_data 2>&1 || true",
            ]
        if op.op_id == "vnd.oppo":
            return [
                "echo '=== OPPO/Realme dialer codes ==='",
                "echo '*#800#       Engineering mode (older ColorOS)'",
                "echo '*#36446337#  Realme deep test'",
                "echo '*#808#       LCD test'",
                "echo '*#888#       PCB version'",
                "echo 'For unlock: oppo.com unlock portal (region-specific) or use msmDownloadTool.'",
            ]
        if op.op_id == "vnd.huawei":
            return [
                "echo '=== Huawei testpoint guide ==='",
                "echo 'Huawei has revoked official bootloader unlock.'",
                "echo '1. Open back, short testpoint to GND while plugging USB → Kirin enters HiSuite mode.'",
                "echo '2. Use DC-Phoenix or HCU client (Wine) to read/erase.'",
                "echo '3. Flash stock firmware via HiSuite or eRecovery (Vol Up + Power w/ USB).'",
            ]
        if op.op_id == "vnd.samsung_dl":
            return [
                "echo '=== Samsung Download Mode entry ==='",
                "echo 'A) Modern (no Home button): Power off, hold Vol-Up + Vol-Down, plug in USB.'",
                "echo 'B) Older with Home: hold Vol-Down + Home + Power.'",
                "echo 'Use Heimdall or Odin (Wine) to flash .tar.md5.'",
                "which heimdall >/dev/null 2>&1 && heimdall detect || echo 'Install Heimdall: Maintenance tab'",
            ]
        if op.op_id == "vnd.samsung_frp":
            return [
                "echo '=== Samsung FRP / stock restore checklist ==='",
                "echo '1. Confirm ownership and Google account recovery eligibility.'",
                "echo '2. Enter Download Mode and flash matching stock firmware with Heimdall/Odin.'",
                "echo '3. Use Smart Switch emergency recovery if firmware is unknown.'",
                "echo '4. After setup, remove old Google account from Settings before resale.'",
                "which heimdall >/dev/null 2>&1 && heimdall detect || echo 'Install Heimdall: Maintenance tab'",
            ]
        if op.op_id == "vnd.lg":
            return [
                "echo '=== LG flashing guide ==='",
                "echo 'LG Bridge / LGUP run on Windows under Wine.'",
                "echo 'For LG bootloader unlock (where supported): developer.lge.com → request bootloader code.'",
                f"fastboot {fs} oem device-id 2>&1 || true",
            ]
        if op.op_id == "vnd.motorola":
            return [
                "echo '=== Motorola bootloader unlock ==='",
                "echo '1. Enable OEM unlocking, reboot to fastboot.'",
                f"fastboot {fs} oem get_unlock_data 2>&1 || true",
                "echo '2. Remove spaces/newlines and submit at motorola-global-portal.custhelp.com/app/standalone/bootloader/unlock-your-device-b'",
                "echo '3. If approved, run: fastboot oem unlock UNIQUE_KEY (wipes data).'",
            ]
        if op.op_id == "vnd.pixel":
            return [
                "echo '=== Google Pixel factory-image helper ==='",
                f"fastboot {fs} getvar product 2>&1 || true",
                f"fastboot {fs} getvar current-slot 2>&1 || true",
                "echo 'Download matching factory image from developers.google.com/android/images.'",
                "echo 'Extract it, review flash-all.sh, then run from the extracted folder.'",
            ]

        # ── Maintenance ───────────────────────────────────────────────
        if op.op_id == "mnt.udev":
            rules = (
                'SUBSYSTEM=="usb",ATTR{idVendor}=="04e8",MODE="0666",GROUP="plugdev"\\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="18d1",MODE="0666",GROUP="plugdev"\\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="05c6",MODE="0666",GROUP="plugdev"\\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="0e8d",MODE="0666",GROUP="plugdev"\\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="2717",MODE="0666",GROUP="plugdev"\\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="12d1",MODE="0666",GROUP="plugdev"\\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="05ac",MODE="0666",GROUP="plugdev"\\n'
            )
            return [
                f"sudo bash -c 'printf \"{rules}\" > /etc/udev/rules.d/51-phone-liberator.rules'",
                "sudo udevadm control --reload-rules && sudo udevadm trigger",
                f"sudo usermod -aG plugdev {shq(os.getenv('USER',''))} 2>/dev/null || true",
                "echo 'udev rules installed (re-login for plugdev group to take effect)'",
            ]
        if op.op_id == "mnt.adb":
            return ["sudo apt-get update -qq", "sudo apt-get install -y adb fastboot android-tools-adb android-tools-fastboot"]
        if op.op_id == "mnt.platform":
            return [
                "cd /tmp && curl -L -o pt.zip https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
                "sudo rm -rf /opt/platform-tools && sudo unzip -o /tmp/pt.zip -d /opt",
                "sudo ln -sf /opt/platform-tools/adb /usr/local/bin/adb",
                "sudo ln -sf /opt/platform-tools/fastboot /usr/local/bin/fastboot",
                "adb version",
            ]
        if op.op_id == "mnt.scrcpy":
            return ["sudo apt-get install -y scrcpy"]
        if op.op_id == "mnt.mtkclient":
            return [
                "sudo apt-get install -y python3-pip git libusb-1.0-0",
                "sudo rm -rf /opt/mtkclient && sudo git clone https://github.com/bkerler/mtkclient /opt/mtkclient",
                "sudo pip3 install -r /opt/mtkclient/requirements.txt --break-system-packages 2>/dev/null || sudo pip3 install -r /opt/mtkclient/requirements.txt",
            ]
        if op.op_id == "mnt.edl":
            return [
                "sudo apt-get install -y python3-pip git libusb-1.0-0",
                "sudo rm -rf /opt/edl && sudo git clone https://github.com/bkerler/edl /opt/edl",
                "sudo pip3 install pyusb pycryptodome --break-system-packages 2>/dev/null || sudo pip3 install pyusb pycryptodome",
            ]
        if op.op_id == "mnt.libimobile":
            return ["sudo apt-get install -y libimobiledevice6 libimobiledevice-utils ifuse usbmuxd ideviceinstaller libplist-utils"]
        if op.op_id == "mnt.iderestore":
            return [
                "sudo apt-get install -y build-essential autoconf automake libtool pkg-config libusb-1.0-0-dev libcurl4-openssl-dev libssl-dev libzip-dev libplist-dev libimobiledevice-dev libirecovery-dev",
                "cd /tmp && rm -rf idevicerestore && git clone https://github.com/libimobiledevice/idevicerestore",
                "cd /tmp/idevicerestore && ./autogen.sh && make -j$(nproc) && sudo make install",
            ]
        if op.op_id == "mnt.checkra1n":
            return [
                "sudo bash -c 'echo deb https://assets.checkra.in/debian /  > /etc/apt/sources.list.d/checkra1n.list'",
                "sudo apt-key adv --fetch-keys https://assets.checkra.in/debian/archive.key 2>/dev/null || curl -fsSL https://assets.checkra.in/debian/archive.key | sudo tee /etc/apt/trusted.gpg.d/checkra1n.asc",
                "sudo apt-get update && sudo apt-get install -y checkra1n",
            ]
        if op.op_id == "mnt.palera1n":
            return [
                "sudo curl -L https://static.palera.in/scripts/install.sh -o /tmp/palerain.sh",
                "sudo bash /tmp/palerain.sh",
            ]
        if op.op_id == "mnt.sideloadly":
            return [open_browser_cmd("https://sideloadly.io"),
                    "echo 'Download Linux .deb and run: sudo dpkg -i Sideloadly_*.deb'"]
        if op.op_id == "mnt.heimdall":
            return ["sudo apt-get install -y heimdall-flash heimdall-flash-frontend"]
        if op.op_id == "mnt.samloader":
            return ["sudo pip3 install samloader --break-system-packages 2>/dev/null || sudo pip3 install samloader"]
        if op.op_id == "mnt.spflash":
            return [open_browser_cmd("https://spflashtools.com/linux")]
        if op.op_id == "mnt.pyserial":
            return ["sudo pip3 install pyserial --break-system-packages 2>/dev/null || sudo pip3 install pyserial"]
        if op.op_id == "mnt.pyusb":
            return ["sudo pip3 install pyusb --break-system-packages 2>/dev/null || sudo pip3 install pyusb"]
        if op.op_id == "mnt.spreadtrum":
            return [
                "sudo apt-get install -y git python3-pip libusb-1.0-0",
                "sudo pip3 install pyusb pyserial pycryptodome --break-system-packages 2>/dev/null || sudo pip3 install pyusb pyserial pycryptodome",
                "echo 'Spreadtrum/Unisoc devices usually need boot-key service mode plus vendor-specific loaders.'",
                "echo 'Place trusted SPD tools/loaders in the tools directory; avoid random unsigned binaries.'",
            ]
        if op.op_id == "mnt.verify":
            return [
                "echo '=== Core Android ==='",
                "adb version 2>&1 || true",
                "fastboot --version 2>&1 || true",
                "scrcpy --version 2>&1 | head -3 || true",
                "echo '=== iPhone ==='",
                "idevice_id --version 2>&1 || true",
                "idevicerestore --version 2>&1 || true",
                "echo '=== Flashing / service ==='",
                "heimdall version 2>&1 || true",
                "python3 -c 'import serial, usb; print(\"pyserial/pyusb OK\")' 2>&1 || true",
                "[ -d /opt/mtkclient ] && echo 'mtkclient installed' || echo 'mtkclient missing'",
                "[ -d /opt/edl ] && echo 'edl.py installed' || echo 'edl.py missing'",
                "wine --version 2>&1 || true",
            ]
        if op.op_id == "mnt.wine":
            return ["sudo dpkg --add-architecture i386", "sudo apt-get update -qq", "sudo apt-get install -y wine wine32 wine64 winetricks"]
        if op.op_id == "mnt.all":
            steps = [
                "echo '=== Installing every Phone Liberator dependency ==='",
                "sudo apt-get update -qq",
                "sudo apt-get install -y adb fastboot android-tools-adb android-tools-fastboot scrcpy heimdall-flash heimdall-flash-frontend libimobiledevice6 libimobiledevice-utils ifuse usbmuxd ideviceinstaller libplist-utils python3-pip git libusb-1.0-0 socat curl unzip wine",
                "sudo pip3 install samloader pyserial pyusb pycryptodome --break-system-packages 2>/dev/null || sudo pip3 install samloader pyserial pyusb pycryptodome",
                "sudo rm -rf /opt/mtkclient && sudo git clone https://github.com/bkerler/mtkclient /opt/mtkclient",
                "sudo pip3 install -r /opt/mtkclient/requirements.txt --break-system-packages 2>/dev/null || sudo pip3 install -r /opt/mtkclient/requirements.txt",
                "sudo rm -rf /opt/edl && sudo git clone https://github.com/bkerler/edl /opt/edl",
                "echo '=== Done. Re-login for plugdev group changes. ==='",
            ]
            return steps

        self._log(f"[{op.label}] not yet implemented", "warn")
        return []


# ───────────────────────── Entry point ─────────────────────────
def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication([])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)
    win = App()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
