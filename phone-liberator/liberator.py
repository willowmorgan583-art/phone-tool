#!/usr/bin/env python3
"""
Phone Liberator v4
ADB / Fastboot / MTK / EDL / iPhone unlocking, Mkopa MDM removal,
Feature phone AT commands, Network unlock.
"""
import os, sys, subprocess, datetime
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QPushButton, QLabel, QTextEdit,
    QComboBox, QCheckBox, QScrollArea, QSizePolicy, QInputDialog,
    QFileDialog, QFrame, QSplitter,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QTextCursor, QPalette, QFont

# ── Worker ─────────────────────────────────────────────────────────────────────
class Worker(QThread):
    log  = pyqtSignal(str, str)
    done = pyqtSignal(int)

    def __init__(self, cmds, label=""):
        super().__init__()
        self.cmds  = cmds
        self.label = label
        self._abort = False
        self._proc  = None

    def abort(self):
        self._abort = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def run(self):
        for cmd in self.cmds:
            if self._abort:
                self.log.emit("[ABORTED]", "#f38ba8")
                self.done.emit(-1)
                return
            self.log.emit(f"$ {cmd}", "#89dceb")
            try:
                self._proc = subprocess.Popen(
                    cmd, shell=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )
                for line in self._proc.stdout:
                    if self._abort:
                        self._proc.terminate()
                        break
                    self.log.emit(line.rstrip(), "#cdd6f4")
                self._proc.wait()
                rc = self._proc.returncode
                if rc != 0 and not self._abort:
                    self.log.emit(f"[exit {rc}]", "#fab387")
            except Exception as e:
                self.log.emit(f"[ERROR] {e}", "#f38ba8")
        self.done.emit(0)

# ── Detector ───────────────────────────────────────────────────────────────────
class Detector(QThread):
    found = pyqtSignal(list)

    def run(self):
        devs = []
        try:
            adb_out = subprocess.check_output(
                "adb devices -l 2>/dev/null", shell=True, text=True)
            for line in adb_out.splitlines()[1:]:
                line = line.strip()
                if not line or "offline" in line:
                    continue
                parts = line.split()
                sn  = parts[0]
                raw = " ".join(parts[2:])
                props = dict(p.split(":", 1) for p in raw.split() if ":" in p)
                brand = props.get("brand", "Android")
                model = props.get("model", sn[:12])
                cpu_cmd = f"adb -s {sn} shell getprop ro.hardware 2>/dev/null"
                cpu = subprocess.check_output(cpu_cmd, shell=True, text=True).strip()
                devs.append({
                    "sn": sn, "brand": brand, "model": model,
                    "cpu": cpu, "method": "adb",
                    "display": f"{brand} {model} [{sn[:8]}]",
                    "android": subprocess.check_output(
                        f"adb -s {sn} shell getprop ro.build.version.release 2>/dev/null",
                        shell=True, text=True).strip(),
                })
        except Exception:
            pass
        try:
            fb = subprocess.check_output(
                "fastboot devices 2>/dev/null", shell=True, text=True)
            for line in fb.splitlines():
                sn = line.split()[0] if line.split() else ""
                if sn:
                    devs.append({
                        "sn": sn, "brand": "Fastboot", "model": "Device",
                        "cpu": "", "method": "fastboot",
                        "display": f"Fastboot [{sn[:12]}]", "android": "?",
                    })
        except Exception:
            pass
        for port in ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0"]:
            if Path(port).exists():
                devs.append({
                    "sn": port, "brand": "Feature", "model": "Phone",
                    "cpu": "", "method": "serial",
                    "display": f"Feature Phone [{port}]", "android": "?",
                })
        if not devs:
            devs.append({
                "sn": "", "brand": "No Device", "model": "",
                "cpu": "", "method": "adb",
                "display": "No device detected", "android": "?",
            })
        self.found.emit(devs)

# ── Stylesheet ─────────────────────────────────────────────────────────────────
QSS = """
QMainWindow, QWidget { background:#1e1e2e; color:#cdd6f4; }
QTabWidget::pane { border:1px solid #313244; }
QTabBar::tab {
    background:#181825; color:#a6adc8;
    padding:6px 14px; margin-right:2px; border-radius:4px 4px 0 0;
}
QTabBar::tab:selected { background:#313244; color:#cdd6f4; }
QPushButton {
    background:#313244; color:#cdd6f4; border:none;
    border-radius:4px; padding:4px 8px;
    min-width:140px;
}
QPushButton:hover   { background:#45475a; }
QPushButton:pressed { background:#585b70; }
QPushButton:disabled{ background:#181825; color:#585b70; }
QPushButton[danger="true"]  { background:#e64553; color:#fff; }
QPushButton[danger="true"]:hover { background:#f38ba8; }
QPushButton[warn="true"]    { background:#e6a335; color:#1e1e2e; }
QPushButton[warn="true"]:hover { background:#fab387; }
QPushButton[safe="true"]    { background:#40a02b; color:#fff; }
QPushButton[safe="true"]:hover { background:#a6e3a1; color:#1e1e2e; }
QTextEdit  { background:#11111b; color:#cdd6f4; border:1px solid #313244;
             font-family:monospace; font-size:11px; }
QComboBox  { background:#313244; color:#cdd6f4; border:1px solid #45475a;
             padding:3px 8px; border-radius:4px; }
QComboBox QAbstractItemView { background:#313244; color:#cdd6f4; }
QCheckBox  { color:#cdd6f4; }
QLabel     { color:#cdd6f4; }
QLabel[desc="true"] { color:#a6adc8; font-size:10px; }
QScrollBar:vertical { background:#181825; width:8px; }
QScrollBar::handle:vertical { background:#45475a; border-radius:4px; }
QFrame[role="sep"] { background:#313244; }
"""

# ── Operations table ── (category, op_id, btn_label, description, style, root)
OPS = [
    # Android ADB
    ("ADB",  "Screen Lock Remove",  "Rm Screen Lock",   "Delete lock DB files (needs root)", "warn",   True),
    ("ADB",  "FRP Bypass",          "FRP Bypass",        "Disable setup wizard via content provider", "warn", False),
    ("ADB",  "Backup /sdcard",      "Backup SD",         "Pull /sdcard to ~/phone-liberator/backup/", "safe", False),
    ("ADB",  "Install APK",         "Install APK",       "Install APK with -r -g flags",     "normal", False),
    ("ADB",  "Sideload ZIP",        "Sideload ZIP",      "ADB sideload OTA/custom zip",       "normal", False),
    ("ADB",  "Reboot → Fastboot",   "→ Fastboot",        "Reboot into fastboot/bootloader",   "normal", False),
    ("ADB",  "Reboot → Recovery",   "→ Recovery",        "Reboot into recovery",               "normal", False),
    ("ADB",  "Screenshot",          "Screenshot",        "Capture screen to ~/Desktop/",       "normal", False),
    ("ADB",  "Shell",               "Open Shell",        "Launch interactive ADB shell",       "normal", False),
    ("ADB",  "Logcat (live)",        "Logcat",            "Stream device logs (Ctrl+C to stop)","normal", False),
    ("ADB",  "Dump Props",          "Dump Props",        "Dump all system properties",         "normal", False),
    ("ADB",  "Sysinfo",             "Sysinfo",           "CPU / RAM / Storage snapshot",       "normal", False),
    # Fastboot
    ("FB",   "OEM Unlock",          "OEM Unlock",        "Unlock bootloader (wipes data!)",    "danger", False),
    ("FB",   "FRP Erase",           "Erase FRP",         "Erase FRP partition in fastboot",    "warn",   False),
    ("FB",   "Factory Reset",       "Factory Reset",     "fastboot -w (wipe data+cache)",      "danger", False),
    ("FB",   "Fastboot Reboot",     "Reboot",            "Reboot device from fastboot",        "normal", False),
    ("FB",   "Lock Bootloader",     "Lock BL",           "Re-lock bootloader (Mkopa restore)", "warn",   False),
    ("FB",   "Flash boot.img",      "Flash boot.img",    "Flash custom/stock boot image",      "warn",   False),
    ("FB",   "Flash firmware .zip", "Flash Firmware",    "Flash all partitions from .zip",     "warn",   False),
    ("FB",   "NUKE ALL (⚠ irreversible)", "NUKE ALL ⚠",  "Wipe every partition — permanent",  "danger", True),
    # Mkopa / PAYG
    ("MKP",  "Mkopa: Remove MDM (ADB)",       "Remove MDM",     "Clear Mkopa device-manager packages",  "warn",   False),
    ("MKP",  "Mkopa: MTK Unlock",             "MTK Unlock",     "mtkclient payload → fastboot unlock",  "warn",   False),
    ("MKP",  "Mkopa: Qualcomm EDL Unlock",    "QC EDL Unlock",  "edl.py erase FRP+protect partitions",  "warn",   False),
    ("MKP",  "Mkopa: Flash Stock Firmware",   "Flash Stock",    "Samsung/MTK/QC stock ROM restore",     "danger", False),
    ("MKP",  "Mkopa: Lock Bootloader",        "Lock BL",        "Lock BL after stock restore",          "warn",   False),
    ("MKP",  "PAYG: Disable Kiosk App",       "Disable Kiosk",  "Disable PAYG kiosk/lock app",          "warn",   False),
    ("MKP",  "Android: Safaricom Carrier Unlock", "Carrier Unlock", "Android handsets locked to Safaricom","normal",False),
    # iPhone
    ("IOS",  "iPhone: Info & UDID",                      "Info / UDID",      "Show device info via libimobiledevice",    "normal", False),
    ("IOS",  "iPhone: Pair / Trust",                     "Pair",             "Pair and trust iPhone",                   "safe",   False),
    ("IOS",  "iPhone: Backup (idevicebackup2)",          "Backup",           "Full iPhone backup to ~/phone-liberator/backup/","safe",False),
    ("IOS",  "iPhone: Enter DFU Mode",                   "DFU Guide",        "Step-by-step DFU instructions",           "normal", False),
    ("IOS",  "iPhone: Passcode Reset (restore)",         "Passcode Reset",   "Enter recovery + restore via iTunes",     "danger", False),
    ("IOS",  "iPhone: Jailbreak Matrix",                 "JB Matrix",        "2025 jailbreak compatibility chart",      "normal", False),
    ("IOS",  "iPhone: checkra1n (A5–A11 / iOS 12–14.8)", "checkra1n",       "Boot checkra1n GUI (A5-A11)",             "warn",   False),
    ("IOS",  "iPhone: palera1n (A9–A17 / iOS 15–17.0)", "palera1n",         "Run palera1n CLI (A9-A17)",               "warn",   False),
    ("IOS",  "iPhone: unc0ver (A12–A14 / iOS 11–14.8)", "unc0ver",          "Sideload unc0ver IPA",                    "warn",   False),
    ("IOS",  "iPhone: Dopamine (A12–A15 / iOS 15–16.6)","Dopamine",         "Rootless jailbreak A12-A15",              "warn",   False),
    ("IOS",  "iPhone: Serotonin (A12+ / iOS 16.0–16.6.1)","Serotonin",     "RootHide rootless A12+",                  "warn",   False),
    ("IOS",  "iPhone: TrollStore (iOS 14–17.0)",         "TrollStore",       "Permanent IPA, no jailbreak needed",      "warn",   False),
    ("IOS",  "iPhone: MacDirtyCow apps (iOS 15–16.1.2)", "MacDirtyCow",     "CVE-2022-46689 tweaks iOS 15-16.1.2",     "warn",   False),
    ("IOS",  "iPhone: SSH (post-jailbreak)",             "SSH",              "SSH into jailbroken iPhone",              "normal", False),
    ("IOS",  "iPhone: Install IPA (Sideloadly)",         "Sideloadly",       "Launch Sideloadly for IPA install",       "normal", False),
    ("IOS",  "iPhone: Activation Lock — Deceased Owner", "Activation Lock",  "Apple official path for deceased owner",  "normal", False),
    # Feature Phone
    ("FTR",  "Feature: AT Info",               "AT Info",       "Read model/IMEI/signal via AT commands", "normal", False),
    ("FTR",  "Feature: Read IMEI (AT)",        "Read IMEI",     "AT+CGSN — read IMEI via serial",         "normal", False),
    ("FTR",  "Feature: Factory Reset (AT)",    "Factory Reset", "AT reset commands (multi-brand)",         "warn",   False),
    ("FTR",  "Feature: AT Network Unlock",     "AT Unlock",     "AT+CLCK NCK unlock via serial",           "warn",   False),
    ("FTR",  "Feature: Nokia Flash (JAF/Phoenix via Wine)", "Nokia Flash", "Launch JAF/Phoenix via Wine", "normal", False),
    ("FTR",  "Feature: MTK Flash (SP Flash Tool)",  "SP Flash Tool","Launch SP Flash Tool Linux",          "normal", False),
    ("FTR",  "Feature: DC-Unlocker (Wine)",    "DC-Unlocker",   "Launch dc-unlocker2client via Wine",      "normal", False),
    # Network Unlock
    ("NET",  "Net: AT+CLCK Carrier Unlock",    "CLCK Unlock",   "Send NCK via AT+CLCK=PN,0 to modem",     "warn",   False),
    ("NET",  "Net: Read Unlock Attempts (AT)", "Unlock Attempts","Read remaining NCK attempts",            "normal", False),
    ("NET",  "Net: NCK Generator (IMEI-based)","NCK Generator", "IMEI-based NCK hint + Luhn check",       "normal", False),
    ("NET",  "Net: Qualcomm NV SIM Unlock",    "QC NV Unlock",  "edl.py NV item 10 SIM unlock",           "warn",   False),
    ("NET",  "Net: MTK Network Unlock",        "MTK Net Unlock","mtkclient payload + fastboot unlock",     "warn",   False),
    ("NET",  "Net: Check IMEI (imei.info)",    "IMEI Check",    "Open imei.info for IMEI lookup",         "normal", False),
    # MTK / EDL
    ("MTK",  "MTK → Fastboot Mode",      "MTK Fastboot",     "mtkclient payload → FASTBOOT metamode",    "warn",  False),
    ("MTK",  "MTK FRP Erase",            "MTK FRP Erase",    "Payload → fastboot erase frp",             "warn",  False),
    ("MTK",  "MTK Read Flash",           "MTK Read Flash",   "Read preloader/boot/system via mtkclient", "safe",  False),
    ("MTK",  "EDL: Read Partition Table","EDL Partitions",   "List partitions via edl.py",               "normal",False),
    ("MTK",  "EDL: Erase FRP/Protect",   "EDL Erase FRP",    "Erase frp+protect_f partitions",           "warn",  False),
    ("MTK",  "EDL: Read Full Flash",     "EDL Read Flash",   "Read full device flash to .bin",           "safe",  False),
    ("MTK",  "EDL: Flash Single Partition","EDL Flash Part", "Flash one partition via edl.py",           "warn",  False),
    # Maintenance
    ("MAINT","Install USB rules (udev)", "USB udev Rules",   "Write /etc/udev/rules.d/51-phone-liberator.rules","safe",False),
    ("MAINT","Install ADB + Fastboot",   "ADB + Fastboot",   "apt-get android-tools-adb/fastboot",       "safe",  False),
    ("MAINT","Install platform-tools",   "Platform Tools",   "Google official platform-tools (latest)",  "safe",  False),
    ("MAINT","Install mtkclient",        "mtkclient",        "git clone bkerler/mtkclient → /opt/",      "safe",  False),
    ("MAINT","Install edl.py",           "edl.py",           "git clone bkerler/edl → /opt/",            "safe",  False),
    ("MAINT","Install libimobiledevice", "libimobiledevice", "apt-get idevice tools + usbmuxd",          "safe",  False),
    ("MAINT","Install idevicerestore",   "idevicerestore",   "Build idevicerestore from source",         "safe",  False),
    ("MAINT","Install checkra1n",        "checkra1n",        "Add checkra1n apt repo + install",         "safe",  False),
    ("MAINT","Install palera1n",         "palera1n",         "Download palera1n binary → /usr/local/bin","safe",  False),
    ("MAINT","Install Sideloadly",       "Sideloadly",       "Open sideloadly.io + dpkg install",        "safe",  False),
    ("MAINT","Install Heimdall",         "Heimdall",         "apt-get heimdall-flash (Samsung)",         "safe",  False),
    ("MAINT","Install samloader",        "samloader",        "pip3 install samloader (Samsung DL)",       "safe",  False),
    ("MAINT","Install SP Flash Tool",    "SP Flash Tool",    "Open spflashtools.com/linux",               "safe",  False),
    ("MAINT","Install pyserial",         "pyserial",         "pip3 install pyserial (AT serial)",        "safe",  False),
    ("MAINT","Install pyusb",            "pyusb",            "pip3 install pyusb",                       "safe",  False),
    ("MAINT","Install Wine",             "Wine",             "apt-get wine wine32 wine64",               "safe",  False),
    ("MAINT","Install All Tools",        "Install ALL ⚡",    "Install every dependency in one shot",     "safe",  False),
]

# ── App ────────────────────────────────────────────────────────────────────────
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phone Liberator v4")
        self.resize(1100, 780)
        self.setStyleSheet(QSS)
        self._devs   = []
        self._worker = None

        cw = QWidget(); self.setCentralWidget(cw)
        root = QVBoxLayout(cw); root.setContentsMargins(8,8,8,8); root.setSpacing(6)

        # ── Top bar ──────────────────────────────────────────────────────────
        top = QHBoxLayout()
        self.dev_combo = QComboBox(); self.dev_combo.setMinimumWidth(340)
        self.dev_combo.addItem("Click Scan to detect devices")
        btn_scan = QPushButton("⟳ Scan"); btn_scan.setFixedWidth(80)
        btn_scan.setProperty("safe","true"); btn_scan.style().unpolish(btn_scan)
        btn_scan.style().polish(btn_scan)
        btn_scan.clicked.connect(self._scan)
        self.chk_rb = QCheckBox("Reboot after")
        self.btn_abort = QPushButton("■ ABORT")
        self.btn_abort.setProperty("danger","true")
        self.btn_abort.style().unpolish(self.btn_abort)
        self.btn_abort.style().polish(self.btn_abort)
        self.btn_abort.setEnabled(False)
        self.btn_abort.clicked.connect(self._abort)
        top.addWidget(QLabel("Device:")); top.addWidget(self.dev_combo)
        top.addWidget(btn_scan); top.addSpacing(12)
        top.addWidget(self.chk_rb); top.addStretch()
        top.addWidget(self.btn_abort)
        root.addLayout(top)

        # ── Status bar ───────────────────────────────────────────────────────
        self.lbl_status = QLabel("Idle")
        self.lbl_status.setAlignment(Qt.AlignLeft)
        root.addWidget(self.lbl_status)

        # ── Splitter: tabs + log ─────────────────────────────────────────────
        split = QSplitter(Qt.Vertical)
        root.addWidget(split, 1)

        self.tabs = QTabWidget()
        split.addWidget(self.tabs)

        self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(160)
        split.addWidget(self.log_box)
        split.setSizes([480, 260])

        # ── Build tabs ───────────────────────────────────────────────────────
        TAB_DEF = [
            ("ADB",   "Android ADB"),
            ("FB",    "Fastboot"),
            ("MKP",   "Mkopa / PAYG"),
            ("IOS",   "iPhone"),
            ("FTR",   "Feature Phone"),
            ("NET",   "Network Unlock"),
            ("MTK",   "MTK / EDL"),
            ("MAINT", "Maintenance"),
        ]
        for cat, title in TAB_DEF:
            self._make_tab(cat, title)

        self._log("Phone Liberator v4 ready — click Scan to detect devices", "#a6e3a1")

    def _make_tab(self, cat, title):
        outer = QWidget()
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setWidget(outer); scroll.setFrameShape(QFrame.NoFrame)
        inner_w = QWidget(); scroll.setWidget(inner_w)
        grid = QGridLayout(inner_w)
        grid.setContentsMargins(10,10,10,10); grid.setSpacing(6)
        grid.setColumnStretch(2,1)

        row = 0
        for (c, op_id, btn_lbl, desc, style, needs_root) in OPS:
            if c != cat:
                continue
            btn = QPushButton(btn_lbl)
            btn.setFixedHeight(30)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.setMinimumWidth(140)
            if style in ("danger","warn","safe","normal"):
                if style != "normal":
                    btn.setProperty(style, "true")
                    btn.style().unpolish(btn); btn.style().polish(btn)
            root_lbl = QLabel("(root)" if needs_root else "")
            root_lbl.setStyleSheet("color:#fab387; font-size:10px;")
            root_lbl.setFixedWidth(42)
            desc_lbl = QLabel(desc); desc_lbl.setProperty("desc","true")
            btn.clicked.connect(lambda _, o=op_id: self._run(o))
            grid.addWidget(btn,      row, 0)
            grid.addWidget(root_lbl, row, 1)
            grid.addWidget(desc_lbl, row, 2)
            row += 1

        grid.setRowStretch(row, 1)
        scroll.setWidget(inner_w)
        container = QWidget(); vl = QVBoxLayout(container)
        vl.setContentsMargins(0,0,0,0); vl.addWidget(scroll)
        self.tabs.addTab(container, title)

    # ── Scan ─────────────────────────────────────────────────────────────────
    def _scan(self):
        self._log("Scanning for devices…", "#89dceb")
        self.dev_combo.clear(); self.dev_combo.addItem("Scanning…")
        d = Detector(); d.found.connect(self._on_found); d.start()
        self._det = d

    def _on_found(self, devs):
        self._devs = devs
        self.dev_combo.clear()
        for d in devs:
            self.dev_combo.addItem(d["display"])
        self._log(f"Found {len(devs)} device(s)", "#a6e3a1")

    def _cur_dev(self):
        idx = self.dev_combo.currentIndex()
        if 0 <= idx < len(self._devs):
            return self._devs[idx]
        return {"sn":"","brand":"","model":"","cpu":"","method":"adb","android":"?"}

    # ── Run operation ────────────────────────────────────────────────────────
    def _run(self, op):
        d   = self._cur_dev()
        sn  = d.get("sn","")
        typ = d.get("method","adb")
        meth = d.get("method","adb")
        adb = f"adb -s {sn}" if sn not in ("—","?","") else "adb"
        cmds = self._build(op, adb, meth, sn, d, typ)
        if cmds is None: return
        if not cmds:
            self._log(f"[{op}] — no commands generated", "#fab387"); return
        self._log(f"\n=== {op} ===", "#cba6f7")
        if self._worker and self._worker.isRunning():
            self._worker.abort()
        self._worker = Worker(cmds, op)
        self._worker.log.connect(self._log)
        self._worker.done.connect(self._done)
        self._worker.start()
        self._set_running(True, op)

    def _set_running(self, running, label=""):
        self.btn_abort.setEnabled(running)
        self.lbl_status.setText(f"Running: {label}…" if running else "Idle")

    def _done(self, rc):
        self._set_running(False)
        color = "#a6e3a1" if rc == 0 else ("#f38ba8" if rc == -1 else "#fab387")
        self._log("=== Done ===" if rc == 0 else ("=== Aborted ===" if rc == -1
                  else f"=== Finished (exit {rc}) ==="), color)

    def _abort(self):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._log("[User abort requested]", "#f38ba8")

    def _log(self, msg, color="#cdd6f4"):
        self.log_box.setTextColor(QColor(color))
        self.log_box.append(msg)
        self.log_box.moveCursor(QTextCursor.End)

    # ── Command builder ───────────────────────────────────────────────────────
    def _build(self, op, adb, meth, sn, dev, typ):
        rb    = "&& fastboot reboot" if self.chk_rb.isChecked() else ""
        arb   = f"; {adb} reboot"   if self.chk_rb.isChecked() else ""
        fs    = f"-s {sn}" if sn and sn not in ("—","?","") else ""
        ser   = sn if "/dev/tty" in sn else "/dev/ttyUSB0"
        brand = dev.get("brand","").lower()
        model = dev.get("model","")
        cpu   = dev.get("cpu","").lower()

        # ── Android ADB ──────────────────────────────────────────────────────
        if op=="Screen Lock Remove":
            return [f"{adb} shell su -c 'rm -f "
                    "/data/system/locksettings.db /data/system/locksettings.db-shm "
                    "/data/system/locksettings.db-wal /data/system/gesture.key "
                    f"/data/system/password.key /data/system/pin.key' {arb}"]
        if op=="FRP Bypass":
            return [
                f"{adb} shell content insert --uri content://settings/secure "
                "--bind name:s:user_setup_complete --bind value:s:1",
                f"{adb} shell content insert --uri content://settings/global "
                "--bind name:s:device_provisioned --bind value:s:1",
                f"{adb} shell settings put global setup_wizard_has_run 1 2>/dev/null || true",
                f"{adb} shell pm disable com.google.android.setupwizard 2>/dev/null || true",
            ]
        if op=="Backup /sdcard":
            dst = os.path.expanduser(f"~/phone-liberator/backup/{sn or 'device'}")
            os.makedirs(dst, exist_ok=True)
            return [f"{adb} pull /sdcard '{dst}'", f"echo 'Saved to {dst}'"]
        if op=="Install APK":
            apk,_ = QFileDialog.getOpenFileName(self,"Select APK","","APK (*.apk)")
            return None if not apk else [f"{adb} install -r -g '{apk}'"]
        if op=="Sideload ZIP":
            zf,_ = QFileDialog.getOpenFileName(self,"Select ZIP","","ZIP (*.zip)")
            return None if not zf else [f"{adb} sideload '{zf}'"]
        if op=="Reboot → Fastboot": return [f"{adb} reboot bootloader"]
        if op=="Reboot → Recovery":  return [f"{adb} reboot recovery"]
        if op=="Screenshot":
            dst = os.path.expanduser(
                f"~/Desktop/screen_{datetime.now():%Y%m%d_%H%M%S}.png")
            return [f"{adb} shell screencap -p /sdcard/__sc.png",
                    f"{adb} pull /sdcard/__sc.png '{dst}'",
                    f"{adb} shell rm /sdcard/__sc.png", f"echo 'Saved: {dst}'"]
        if op=="Shell":
            subprocess.Popen(
                f"x-terminal-emulator -e '{adb} shell' 2>/dev/null "
                f"|| xterm -e '{adb} shell' 2>/dev/null "
                f"|| gnome-terminal -- {adb} shell", shell=True)
            return []
        if op=="Logcat (live)": return [f"{adb} logcat -v threadtime"]
        if op=="Dump Props":    return [f"{adb} shell getprop"]
        if op=="Sysinfo":
            return [f"{adb} shell uname -a",
                    f"{adb} shell cat /proc/cpuinfo | head -20",
                    f"{adb} shell cat /proc/meminfo | head -6",
                    f"{adb} shell df -h /data /sdcard"]

        # ── Android Fastboot ─────────────────────────────────────────────────
        if op=="OEM Unlock":      return [f"fastboot {fs} oem unlock {rb}"]
        if op=="FRP Erase":       return [f"fastboot {fs} erase frp {rb}"]
        if op=="Factory Reset":   return [f"fastboot {fs} -w {rb}"]
        if op=="Fastboot Reboot": return [f"fastboot {fs} reboot"]
        if op=="Lock Bootloader": return [f"fastboot {fs} oem lock {rb}"]
        if op=="Flash boot.img":
            img,_ = QFileDialog.getOpenFileName(self,"Select boot.img","","IMG (*.img)")
            return None if not img else [f"fastboot {fs} flash boot '{img}' {rb}"]
        if op=="Flash firmware .zip":
            zf,_ = QFileDialog.getOpenFileName(self,"Select firmware","","ZIP (*.zip)")
            if not zf: return None
            return ["rm -rf /tmp/_lfw && mkdir -p /tmp/_lfw",
                    f"unzip -o '{zf}' -d /tmp/_lfw",
                    f"cd /tmp/_lfw && for p in preloader lk boot recovery system "
                    f"system_ext vendor vendor_dlkm product dtbo vbmeta "
                    f"vbmeta_system vbmeta_vendor; do "
                    f"[ -f $p.img ] && fastboot {fs} flash $p $p.img && echo flashed $p "
                    f"|| true; done", f"fastboot {fs} reboot"]
        if op=="NUKE ALL (⚠ irreversible)":
            if meth=="fastboot":
                return [f"for p in system system_ext vendor product userdata cache "
                        f"boot dtbo vbmeta vbmeta_system vbmeta_vendor; do "
                        f"fastboot {fs} erase $p 2>/dev/null && echo wiped $p || true; done",
                        f"fastboot {fs} reboot-bootloader"]
            return [f"{adb} shell su -c '"
                    "for blk in userdata frp; do "
                    "b=$(readlink -f /dev/block/by-name/$blk 2>/dev/null); "
                    "[ -n \"$b\" ] && dd if=/dev/zero of=$b bs=4096 count=2048 || true; "
                    "done; reboot'"]

        # ── Mkopa / PAYG ─────────────────────────────────────────────────────
        if op=="Mkopa: Remove MDM (ADB)":
            return [
                f"{adb} shell pm list packages | grep -iE 'mkopa|mdm|devicepolicy' || true",
                f"{adb} shell pm clear com.mkopa.devicesecurity 2>/dev/null || true",
                f"{adb} shell pm clear com.mkopa.devicemanager  2>/dev/null || true",
                f"{adb} shell dpm remove-active-admin "
                "$(adb shell dumpsys device_policy 2>/dev/null | "
                "grep -oE '[a-z]+\\.mkopa\\.[a-z]+/[A-Za-z.]+' | head -1) 2>/dev/null || true",
                "echo 'MDM removal attempted'", f"{adb} reboot"]
        if op=="Mkopa: MTK Unlock":
            self._need("mtkclient")
            return ["python3 /opt/mtkclient/mtk payload --metamode FASTBOOT","sleep 4",
                    "fastboot oem unlock","fastboot erase frp","fastboot erase userdata",
                    "fastboot reboot"]
        if op=="Mkopa: Qualcomm EDL Unlock":
            self._need("edl")
            return ["python3 /opt/edl/edl.py partition 2>/dev/null | head -20 || true",
                    "python3 /opt/edl/edl.py e frp 2>/dev/null || true",
                    "python3 /opt/edl/edl.py e protect_f 2>/dev/null || true",
                    "python3 /opt/edl/edl.py reset"]
        if op=="Mkopa: Flash Stock Firmware":
            fw = os.path.expanduser("~/phone-liberator/firmware")
            os.makedirs(fw, exist_ok=True)
            if "samsung" in brand:
                return [
                    f"echo '=== Samsung stock flash: {model} ==='",
                    f"which samloader && samloader -m {model} -r DBT -O '{fw}' "
                    "|| echo 'Install samloader: Maintenance tab'",
                    f"ls '{fw}'/*.zip 2>/dev/null | head -1 | "
                    "xargs -I{{}} unzip -o {{}} -d '{fw}/' 2>/dev/null || true",
                    "echo 'Put device in Download Mode (Vol Down + Home + Power)'",
                    f"ls '{fw}'/*.tar.md5 2>/dev/null | head -3 "
                    f"|| echo 'No .tar.md5 files in {fw}/ yet'",
                    "which heimdall || echo 'Install Heimdall: Maintenance tab'",
                    "echo 'After flash: Mkopa/PAYG → Lock Bootloader'"]
            elif "mediatek" in cpu or typ=="mtk":
                return [
                    f"echo '=== MTK stock flash: {model} ==='",
                    f"echo 'Place firmware .zip in {fw}/'",
                    f"ls '{fw}'/*.zip 2>/dev/null | head -1 | "
                    "xargs -I{{}} unzip -o {{}} -d '{fw}/extracted/' 2>/dev/null || true",
                    "echo 'Open SP Flash Tool: Feature tab → SP Flash Tool'",
                    "echo 'Load scatter file → Download Only → Download'",
                    "echo 'After flash: Mkopa/PAYG → Lock Bootloader'"]
            else:
                return [
                    f"echo '=== QC/Generic stock flash: {model} ==='",
                    f"echo 'Place firmware .zip in {fw}/'",
                    f"ls '{fw}'/*.zip 2>/dev/null | head -1 | "
                    "xargs -I{{}} bash -c 'mkdir -p /tmp/_fw && unzip -o {{}} -d /tmp/_fw'",
                    f"cd /tmp/_fw && ls *.img 2>/dev/null | "
                    f"xargs -I{{}} fastboot {fs} flash $(basename {{}} .img) {{}} 2>/dev/null || true",
                    f"fastboot {fs} -w", f"fastboot {fs} reboot",
                    "echo 'After flash: Mkopa/PAYG → Lock Bootloader'"]
        if op=="Mkopa: Lock Bootloader":
            return [
                "echo '=== Locking bootloader — device must be in fastboot mode ==='",
                f"fastboot {fs} oem lock 2>/dev/null || fastboot {fs} flashing lock",
                "echo 'Bootloader locked. Device resets to factory state on first boot.'",
                "echo 'Complete Android setup — Mkopa software will NOT reinstall.'",
                f"fastboot {fs} reboot"]
        if op=="PAYG: Disable Kiosk App":
            return [
                f"{adb} shell pm list packages | grep -iE 'lock|kiosk|payg|mkopa|safaricom' || true",
                f"{adb} shell settings put global policy_control immersive.full=* 2>/dev/null || true",
                "echo 'Run: adb shell pm disable <package> for permanent fix'"]
        if op=="Android: Safaricom Carrier Unlock":
            return [
                "echo '=== Android Safaricom Carrier Unlock ==='",
                "echo 'For Android handsets manufactured SIM-locked to Safaricom'",
                f"{adb} shell service call iphonesubinfo 1 2>/dev/null | "
                "grep -oP \"'[0-9.]+'\"|tr -d \"'. \" || echo 'Dial *#06# for IMEI'",
                "echo 'Call Safaricom 100 or visit My Safaricom App → Device Unlock'",
                "echo 'Bring IMEI + National ID + proof of purchase to any Safaricom shop'"]

        # ── iPhone ───────────────────────────────────────────────────────────
        if op=="iPhone: Info & UDID":
            uf = f"-u {sn}" if sn not in ("—","?","","QC-EDL","MTK-USB") else ""
            return [f"ideviceinfo {uf} | grep -E "
                    "'DeviceName|ProductType|ProductVersion|CPUArchitecture|"
                    "ActivationState|UniqueDeviceID|IMEI'", "idevice_id -l"]
        if op=="iPhone: Pair / Trust":
            return ["idevicepair pair",
                    "echo 'Tap Trust on iPhone when prompted, then run again'"]
        if op=="iPhone: Backup (idevicebackup2)":
            uf = f"-u {sn}" if sn not in ("—","?","","QC-EDL","MTK-USB") else ""
            dst = os.path.expanduser(
                f"~/phone-liberator/backup/iphone_{sn[:8] if len(sn)>4 else 'dev'}")
            os.makedirs(dst, exist_ok=True)
            return [f"idevicebackup2 backup --full '{dst}'", f"echo 'Saved to {dst}'"]
        if op=="iPhone: Enter DFU Mode":
            if any(x in model for x in ("iPhone8","iPhone9","iPhone10")):
                g = "7/8/X: Side+VolDown 10s → release Side → keep VolDown 5s"
            elif any(x in model for x in ("iPhone11","iPhone12","iPhone13",
                                           "iPhone14","iPhone15","iPhone16")):
                g = "XS/11-16: VolUp tap → VolDown tap → hold Side 10s → release → keep 5s"
            else:
                g = "Older (6 and below): hold Home+Power 10s → release Power → keep Home 5s"
            return [f"echo 'DFU Guide: {g}'", "idevice_id -l"]
        if op=="iPhone: Passcode Reset (restore)":
            uf = f"-u {sn}" if sn not in ("—","?","","QC-EDL","MTK-USB") else ""
            return ["echo 'WARNING: full device erase — all data lost'",
                    f"ideviceenterrecovery {sn if uf else ''} 2>/dev/null || true",
                    "echo 'Connect to iTunes/Finder and click Restore'",
                    "echo 'Linux: idevicerestore -e <firmware.ipsw>'"]
        if op=="iPhone: Jailbreak Matrix":
            ios = dev.get("android","?")
            return [
                "echo '=== iPhone Jailbreak Matrix (2025) ==='",
                f"echo 'Device: {model}  iOS: {ios}'",
                "echo 'checkra1n  A5-A11  iOS 12-14.8.1  5s/6/6s/SE1/7/8/X'",
                "echo 'palera1n   A9-A17  iOS 15-17.0    6s-15 Pro Max (tethered A9-A11)'",
                "echo 'unc0ver    A12-A14 iOS 11-14.8    XS/11/12  via Sideloadly'",
                "echo 'Dopamine   A12-A15 iOS 15-16.6.1  XS-13 rootless'",
                "echo 'Serotonin  A12+    iOS 16.0-16.6.1 RootHide rootless'",
                "echo 'TrollStore A9+     iOS 14-17.0    no jailbreak needed'",
                "echo 'MacDirtyCow A9+    iOS 15-16.1.2  CVE-2022-46689'",
                "echo 'iPhone 16 Pro A18: NO public jailbreak as of 2025'"]
        if op=="iPhone: checkra1n (A5–A11 / iOS 12–14.8)":
            if not Path("/usr/local/bin/checkra1n").exists():
                return ["echo 'Not installed → Maintenance → checkra1n'"]
            return ["echo 'Put device in DFU mode first'","checkra1n -G &"]
        if op=="iPhone: palera1n (A9–A17 / iOS 15–17.0)":
            if not Path("/usr/local/bin/palera1n").exists():
                return ["echo 'Not installed → Maintenance → palera1n'"]
            uf = f"-u {sn}" if sn not in ("—","?","","QC-EDL","MTK-USB") else ""
            return [f"palera1n {uf} 2>&1", "echo 'Tip: palera1n -l for tethered A9-A11'"]
        if op=="iPhone: unc0ver (A12–A14 / iOS 11–14.8)":
            dst = os.path.expanduser("~/phone-liberator/tools/uncover.ipa")
            return ["echo 'unc0ver: A12-A14, iOS 11-14.8 via Sideloadly'",
                    f"[ -f '{dst}' ] && echo 'IPA ready' || echo 'Get from unc0ver.dev'",
                    "which sideloadly && sideloadly & || echo 'Install Sideloadly → Maintenance'"]
        if op=="iPhone: Dopamine (A12–A15 / iOS 15–16.6)":
            return ["echo 'Dopamine: A12-A15, iOS 15-16.6.1, rootless'",
                    "echo 'Get from ellekit.space/dopamine'",
                    "which sideloadly && sideloadly & || echo 'Install Sideloadly → Maintenance'"]
        if op=="iPhone: Serotonin (A12+ / iOS 16.0–16.6.1)":
            return ["echo 'Serotonin: A12+, iOS 16.0-16.6.1, rootless'",
                    "echo 'Get from github.com/RootHide/Serotonin/releases'",
                    "which sideloadly && sideloadly & || echo 'Install Sideloadly → Maintenance'"]
        if op=="iPhone: TrollStore (iOS 14–17.0)":
            uf = f"-u {sn}" if sn not in ("—","?","","QC-EDL","MTK-USB") else ""
            return ["echo 'TrollStore: permanent IPA, no jailbreak, iOS 14-17, A9+'",
                    "echo 'METHOD A: TrollInstallerX → github.com/opa334/TrollInstallerX'",
                    f"echo 'METHOD B (iOS 14-15.4 A9-A12): ideviceinstaller {uf} -i TrollHelper.ipa'",
                    "which sideloadly && sideloadly & || echo 'Install Sideloadly → Maintenance'"]
        if op=="iPhone: MacDirtyCow apps (iOS 15–16.1.2)":
            return ["echo 'MacDirtyCow: CVE-2022-46689, iOS 15-16.1.2'",
                    "echo 'Cowabunga: github.com/leminlimez/Cowabunga/releases'",
                    "which sideloadly && sideloadly & || echo 'Install Sideloadly → Maintenance'"]
        if op=="iPhone: SSH (post-jailbreak)":
            return ["ssh -o StrictHostKeyChecking=no -p 2222 root@localhost"]
        if op=="iPhone: Install IPA (Sideloadly)":
            return ["which sideloadly && sideloadly & || echo 'Install Sideloadly → Maintenance'"]
        if op=="iPhone: Activation Lock — Deceased Owner":
            uf = f"-u {sn}" if sn not in ("—","?","","QC-EDL","MTK-USB") else ""
            return [
                "echo '=== Activation Lock: Deceased Owner (Apple official path) ==='",
                "echo 'iPhone 16 Pro A18: NO software bypass exists in 2025'",
                "echo 'Required: death certificate + ownership proof + your national ID'",
                f"ideviceinfo {uf} -k SerialNumber 2>/dev/null || echo 'Check original box for serial number'",
                "echo 'Contact: apple.com/support | Kenya: +254-800-724-985'",
                "echo 'OR: icloud.com/find → Erase Device → Remove from Account (needs Apple ID password)'"]

        # ── Feature Phone ────────────────────────────────────────────────────
        if op=="Feature: AT Info":
            return [f"python3 -c \""
                    f"import serial,time; s=serial.Serial('{ser}',9600,timeout=2); "
                    f"[s.write((c+'\\r\\n').encode()) or time.sleep(0.6) or "
                    f"print(c,'->',s.read(300).decode(errors='replace')) "
                    f"for c in ['ATI','AT+CGMM','AT+CIMI','AT+CGSN','AT+CREG?','AT+CSQ']]\""]
        if op=="Feature: Read IMEI (AT)":
            return [f"python3 -c \""
                    f"import serial,time; s=serial.Serial('{ser}',9600,timeout=2); "
                    f"s.write(b'AT+CGSN\\r\\n'); time.sleep(1); "
                    f"print('IMEI:',s.read(300).decode(errors='replace'))\""]
        if op=="Feature: Factory Reset (AT)":
            return [f"python3 -c \""
                    f"import serial,time; s=serial.Serial('{ser}',9600,timeout=2); "
                    f"[s.write((c+'\\r\\n').encode()) or time.sleep(1) or "
                    f"print(c,'->',s.read(300).decode(errors='replace')) "
                    f"for c in ['AT*RSTDFLT','AT+RSTDFLT','AT+CRST=1']]\""]
        if op=="Feature: AT Network Unlock":
            code,ok = QInputDialog.getText(self,"NCK Code","Enter Network Control Key:")
            if not ok or not code: return None
            return [f"python3 -c \""
                    f"import serial,time; s=serial.Serial('{ser}',9600,timeout=2); "
                    f"cmds=['AT+CLCK=\\\"PN\\\",0,\\\"{code}\\\"','AT+CPIN={code}']; "
                    f"[s.write((c+'\\r\\n').encode()) or time.sleep(1) or "
                    f"print(c,'->',s.read(300).decode(errors='replace')) for c in cmds]\""]
        if op=="Feature: Nokia Flash (JAF/Phoenix via Wine)":
            return ["which wine || sudo apt-get install -y wine wine32",
                    "ls ~/phone-liberator/tools/*.exe 2>/dev/null | head -1 | "
                    "xargs -I{} wine {} 2>/dev/null & "
                    "|| echo 'Copy JAF.exe or PhoenixService.exe to ~/phone-liberator/tools/'"]
        if op=="Feature: MTK Flash (SP Flash Tool)":
            return ["ls ~/phone-liberator/tools/SP_Flash_Tool*.tar.gz 2>/dev/null | "
                    "head -1 | xargs -I{} tar xf {} -C ~/phone-liberator/tools/ 2>/dev/null || true",
                    "ls ~/phone-liberator/tools/SP_Flash_Tool*/flash_tool 2>/dev/null | "
                    "head -1 | xargs -I{} bash -c 'chmod +x {}; {} &' 2>/dev/null "
                    "|| echo 'Download SP Flash Tool from spflashtools.com/linux to ~/phone-liberator/tools/'"]
        if op=="Feature: DC-Unlocker (Wine)":
            return ["which wine || sudo apt-get install -y wine wine32",
                    "ls ~/phone-liberator/tools/dc-unlocker*.exe 2>/dev/null | head -1 | "
                    "xargs -I{} wine {} 2>/dev/null & "
                    "|| echo 'Copy dc-unlocker2client.exe to ~/phone-liberator/tools/'"]

        # ── Network Unlock ───────────────────────────────────────────────────
        if op=="Net: AT+CLCK Carrier Unlock":
            code,ok = QInputDialog.getText(self,"NCK","Enter NCK code:")
            if not ok or not code: return None
            return [f"python3 -c \""
                    f"import serial,time; s=serial.Serial('{ser}',9600,timeout=2); "
                    f"s.write(('AT+CLCK=\\\"PN\\\",0,\\\"{code}\\\"\\r\\n').encode()); "
                    f"time.sleep(1); print(s.read(500).decode(errors='replace'))\""]
        if op=="Net: Read Unlock Attempts (AT)":
            return [f"python3 -c \""
                    f"import serial,time; s=serial.Serial('{ser}',9600,timeout=2); "
                    f"s.write(b'AT+CLCK=\\\"PN\\\",2\\r\\n'); time.sleep(1); "
                    f"print(s.read(500).decode(errors='replace'))\""]
        if op=="Net: NCK Generator (IMEI-based)":
            imei,ok = QInputDialog.getText(self,"IMEI","Enter 15-digit IMEI:")
            if not ok or not imei: return None
            return [f"echo 'IMEI: {imei}'",
                    f"python3 -c \""
                    f"imei='{imei}'; "
                    f"print('Last 8:',imei[-8:]); print('Last 6:',imei[-6:]); "
                    f"d=[int(x) for x in imei[:14]]; "
                    f"s=sum(d[i]*2 if i%2 else d[i] for i in range(14)); "
                    f"print('Luhn:',str(s%100000000).zfill(8)); "
                    f"print('Samsung/Nokia: imeidr.com or carrier portal')\""]
        if op=="Net: Qualcomm NV SIM Unlock":
            self._need("edl")
            return ["python3 /opt/edl/edl.py nvread 10 2>/dev/null "
                    "|| echo 'Connect device in EDL mode first'"]
        if op=="Net: MTK Network Unlock":
            self._need("mtkclient")
            return ["python3 /opt/mtkclient/mtk payload --metamode FASTBOOT","sleep 3",
                    "fastboot oem network-unlock 2>/dev/null "
                    "|| echo 'Try: fastboot oem cdma_get_simlock_tickets'"]
        if op=="Net: Check IMEI (imei.info)":
            imei,ok = QInputDialog.getText(self,"IMEI","Enter IMEI:")
            if not ok: return None
            return [f"xdg-open 'https://www.imei.info/?imei={imei}' 2>/dev/null "
                    f"|| echo 'Visit: https://www.imei.info/?imei={imei}'"]

        # ── MTK / EDL ────────────────────────────────────────────────────────
        if op=="MTK → Fastboot Mode":
            self._need("mtkclient")
            return ["python3 /opt/mtkclient/mtk payload --metamode FASTBOOT"]
        if op=="MTK FRP Erase":
            self._need("mtkclient")
            return ["python3 /opt/mtkclient/mtk payload --metamode FASTBOOT",
                    "sleep 3","fastboot erase frp","fastboot reboot"]
        if op=="MTK Read Flash":
            self._need("mtkclient")
            dst = os.path.expanduser(f"~/phone-liberator/backup/mtk_{datetime.now():%Y%m%d_%H%M%S}")
            os.makedirs(dst, exist_ok=True)
            return [f"python3 /opt/mtkclient/mtk r preloader,boot,system,userdata '{dst}'"]
        if op=="EDL: Read Partition Table":
            self._need("edl")
            return ["python3 /opt/edl/edl.py partition"]
        if op=="EDL: Erase FRP/Protect":
            self._need("edl")
            return ["python3 /opt/edl/edl.py e frp 2>/dev/null || true",
                    "python3 /opt/edl/edl.py e protect_f 2>/dev/null || true",
                    "python3 /opt/edl/edl.py reset"]
        if op=="EDL: Read Full Flash":
            self._need("edl")
            dst = os.path.expanduser(f"~/phone-liberator/backup/edl_{datetime.now():%Y%m%d_%H%M%S}")
            os.makedirs(dst, exist_ok=True)
            return [f"python3 /opt/edl/edl.py rf '{dst}/full_flash.bin'"]
        if op=="EDL: Flash Single Partition":
            self._need("edl")
            part,ok1 = QInputDialog.getText(self,"Partition","e.g. boot, recovery, frp:")
            if not ok1 or not part: return None
            img,_ = QFileDialog.getOpenFileName(self,"Select image","","IMG (*.img)")
            if not img: return None
            return [f"python3 /opt/edl/edl.py w {part} '{img}'"]

        # ── Maintenance ──────────────────────────────────────────────────────
        if op=="Install USB rules (udev)":
            return [
                "sudo tee /etc/udev/rules.d/51-phone-liberator.rules > /dev/null << 'EOF'\n"
                'SUBSYSTEM=="usb",ATTR{idVendor}=="04e8",MODE="0666",GROUP="plugdev"\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="18d1",MODE="0666",GROUP="plugdev"\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="05c6",MODE="0666",GROUP="plugdev"\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="0e8d",MODE="0666",GROUP="plugdev"\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="2717",MODE="0666",GROUP="plugdev"\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="12d1",MODE="0666",GROUP="plugdev"\n'
                'SUBSYSTEM=="usb",ATTR{idVendor}=="05ac",MODE="0666",GROUP="plugdev"\n'
                "EOF",
                "sudo udevadm control --reload-rules && sudo udevadm trigger",
                "sudo usermod -aG plugdev $USER 2>/dev/null || true",
                "echo 'USB rules installed — reconnect device'"]
        if op=="Install ADB + Fastboot":
            return ["sudo apt-get update -qq",
                    "sudo apt-get install -y android-tools-adb android-tools-fastboot",
                    "adb start-server","adb version"]
        if op=="Install platform-tools":
            return ["curl -Lo /tmp/pt.zip "
                    "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
                    "sudo unzip -o /tmp/pt.zip -d /opt/",
                    "sudo ln -sf /opt/platform-tools/adb /usr/local/bin/adb",
                    "sudo ln -sf /opt/platform-tools/fastboot /usr/local/bin/fastboot",
                    "adb version && fastboot --version"]
        if op=="Install mtkclient":
            return ["sudo apt-get install -y python3-pip git",
                    "[ -d /opt/mtkclient ] || sudo git clone "
                    "https://github.com/bkerler/mtkclient /opt/mtkclient",
                    "sudo pip3 install -r /opt/mtkclient/requirements.txt",
                    "echo 'mtkclient ready'"]
        if op=="Install edl.py":
            return ["sudo apt-get install -y python3-pip git libusb-1.0-0-dev",
                    "[ -d /opt/edl ] || sudo git clone https://github.com/bkerler/edl /opt/edl",
                    "sudo pip3 install -r /opt/edl/requirements.txt","echo 'edl.py ready'"]
        if op=="Install libimobiledevice":
            return ["sudo apt-get update -qq",
                    "sudo apt-get install -y libimobiledevice-utils ifuse ideviceinstaller usbmuxd",
                    "sudo systemctl enable --now usbmuxd 2>/dev/null || true",
                    "echo 'libimobiledevice installed'"]
        if op=="Install idevicerestore":
            return ["sudo apt-get install -y libimobiledevice-dev libirecovery-dev "
                    "libcurl4-openssl-dev libzip-dev libplist-dev cmake git autoconf automake libtool",
                    "[ -d /tmp/idevicerestore ] || git clone "
                    "https://github.com/libimobiledevice/idevicerestore /tmp/idevicerestore",
                    "cd /tmp/idevicerestore && ./autogen.sh && make -j$(nproc) && sudo make install",
                    "echo 'idevicerestore installed'"]
        if op=="Install checkra1n":
            return ["curl -fsSL https://assets.checkra.in/debian/public.key | "
                    "sudo gpg --dearmor -o /usr/share/keyrings/checkra1n.gpg",
                    "echo 'deb [signed-by=/usr/share/keyrings/checkra1n.gpg] "
                    "https://assets.checkra.in/debian /' | "
                    "sudo tee /etc/apt/sources.list.d/checkra1n.list",
                    "sudo apt-get update -qq && sudo apt-get install -y checkra1n",
                    "echo 'checkra1n installed'"]
        if op=="Install palera1n":
            return ["ARCH=$(uname -m); "
                    "[ \"$ARCH\" = 'x86_64' ] && BIN='palera1n-linux-x86_64' "
                    "|| BIN='palera1n-linux-arm64'",
                    "curl -Lo /tmp/palera1n "
                    "https://github.com/palera1n/palera1n/releases/latest/download/$BIN",
                    "sudo install -m 755 /tmp/palera1n /usr/local/bin/palera1n",
                    "palera1n --version"]
        if op=="Install Sideloadly":
            return ["xdg-open 'https://sideloadly.io/#download' 2>/dev/null & true",
                    "echo 'Download .deb from sideloadly.io then:'",
                    "ls ~/Downloads/sideloadly*.deb 2>/dev/null | "
                    "head -1 | xargs -I{} sudo dpkg -i {} "
                    "|| echo 'sudo dpkg -i ~/Downloads/sideloadly*.deb'"]
        if op=="Install Heimdall":
            return ["sudo apt-get update -qq",
                    "sudo apt-get install -y heimdall-flash",
                    "heimdall version"]
        if op=="Install samloader":
            return ["sudo pip3 install samloader",
                    "samloader --help 2>/dev/null | head -3 || echo 'samloader installed'"]
        if op=="Install SP Flash Tool":
            return ["xdg-open 'https://spflashtools.com/linux' 2>/dev/null & true",
                    "echo 'Save .tar.gz to ~/phone-liberator/tools/ then Feature → SP Flash Tool'"]
        if op=="Install pyserial":
            return ["sudo pip3 install pyserial",
                    "python3 -c 'import serial; print(\"pyserial\",serial.__version__)'"]
        if op=="Install pyusb":
            return ["sudo pip3 install pyusb",
                    "python3 -c 'import usb; print(\"pyusb ok\")'"]
        if op=="Install Wine":
            return ["sudo dpkg --add-architecture i386","sudo apt-get update -qq",
                    "sudo apt-get install -y wine wine32 wine64","wine --version"]
        if op=="Install All Tools":
            return [
                "echo '=== Installing all Phone Liberator dependencies ==='",
                "sudo apt-get update -qq",
                "sudo apt-get install -y android-tools-adb android-tools-fastboot "
                "libimobiledevice-utils ifuse ideviceinstaller usbmuxd heimdall-flash "
                "python3-pip git libusb-1.0-0-dev wine wine32 curl unzip",
                "sudo pip3 install pyserial pyusb samloader",
                "[ -d /opt/mtkclient ] || sudo git clone "
                "https://github.com/bkerler/mtkclient /opt/mtkclient",
                "sudo pip3 install -r /opt/mtkclient/requirements.txt 2>/dev/null || true",
                "[ -d /opt/edl ] || sudo git clone https://github.com/bkerler/edl /opt/edl",
                "sudo pip3 install -r /opt/edl/requirements.txt 2>/dev/null || true",
                "sudo systemctl enable --now usbmuxd 2>/dev/null || true",
                "echo '=== Done. Still manual: checkra1n, palera1n, Sideloadly ==='"]
        return []

    def _need(self, tool):
        paths = {"mtkclient": "/opt/mtkclient/mtk", "edl": "/opt/edl/edl.py",
                 "palera1n": "/usr/local/bin/palera1n", "checkra1n": "/usr/local/bin/checkra1n"}
        if not Path(paths.get(tool,"")).exists():
            self._log(f"[!] {tool} not installed — go to Maintenance → Install {tool}","#fab387")

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    for d in ["tools","backup","firmware"]:
        os.makedirs(os.path.expanduser(f"~/phone-liberator/{d}"), exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.Window,          QColor("#1e1e2e"))
    pal.setColor(QPalette.WindowText,      QColor("#cdd6f4"))
    pal.setColor(QPalette.Base,            QColor("#11111b"))
    pal.setColor(QPalette.Text,            QColor("#cdd6f4"))
    pal.setColor(QPalette.Button,          QColor("#313244"))
    pal.setColor(QPalette.ButtonText,      QColor("#cdd6f4"))
    pal.setColor(QPalette.Highlight,       QColor("#89b4fa"))
    pal.setColor(QPalette.HighlightedText, QColor("#1e1e2e"))
    app.setPalette(pal)
    w = App(); w.show()
    sys.exit(app.exec_())
