---
name: testing-phone-liberator
description: Test the phone-liberator PyQt5 desktop app end-to-end. Use when verifying UI changes, op-builder logic, shell-injection hardening, or any change to liberator.py.
---

# Testing phone-liberator

Single-file PyQt5 GUI at `phone-liberator/liberator.py`. The org environment
config already installs `python3-pyqt5`, `xvfb`, `adb`, `fastboot`, so you do
not need to install anything for a typical session.

## How to run

```bash
# Live (visible) GUI on display :0 — for screenshots and recordings:
DISPLAY=:0 /usr/bin/python3 phone-liberator/liberator.py &

# Headless smoke-test under Xvfb — for compile/run sanity checks:
xvfb-run -a /usr/bin/python3 phone-liberator/liberator.py

# Compile-check only:
/usr/bin/python3 -m py_compile phone-liberator/liberator.py
```

Use system Python (`/usr/bin/python3`) — pyenv Pythons usually do not have
PyQt5 bound to system libs.

To maximise the live window for a recording on Linux:
```bash
DISPLAY=:0 wmctrl -ir $(DISPLAY=:0 xdotool search --name 'Phone Liberator' | tail -1) -b add,maximized_vert,maximized_horz
```

## Architecture quirks that bite

- **`Worker.run()` runs each item in `self.cmds` in its own `/bin/bash`
  subprocess.** Anything that depends on shell state from a previous item
  (variables, `case`/`esac` blocks, here-docs, multi-line `if`/`fi`) MUST
  live inside a single list item — joined with `;` or `\n`. Splitting a
  shell-variable capture from its consumer across two list items is the
  classic phone-liberator regression (see PR #2 → #3 history).
- **Op handlers return `list[str] | None`.** A `None` return means the
  user cancelled or input was rejected; the harness must check for it.
- **`shlex.quote()` is aliased as `shq` at the top of liberator.py.** All
  user inputs that reach a shell must go through `shq`.
- **Detector thread accesses raw C++ Qt objects.** A `RuntimeError: wrapped
  C/C++ object … has been deleted` from `_det.isRunning()` means the previous
  detector finished — catch it and start a fresh one.

## How to test ops without real hardware

Driver pattern: import `liberator`, build the app, call `App._build(op, dev)`,
run the resulting bash items through `/bin/bash -c` with stub functions for
`adb`, `ideviceinfo`, `socat`, etc.

```python
import os, sys, subprocess
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, 'phone-liberator')
import liberator as L
from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
w = L.App(); w.show()
OP = {o.op_id: o for o in L.OPS}

dev = L.Device(method='adb', sn='SN-A', model='X', brand='Y',
               android='14', cpu='qualcomm')
cmds = w._build(OP['mkp.remove_mdm'], dev)

sandbox = (
    'adb() { '
    '  if [[ "$*" == *"dumpsys device_policy"* ]]; then '
    '    echo "    com.mkopa.devicesecurity/.AdminReceiver"; '
    '  elif [[ "$*" == *"remove-active-admin"* ]]; then '
    '    echo "REMOVED:$*" > /tmp/proof; '
    '  fi; '
    '}; export -f adb; '
    + cmds[3]
)
subprocess.run(['/bin/bash', '-c', sandbox], check=True)
```

For shell-injection tests, point the stub at `touch /tmp/PWN-<TAG>` and assert
the marker file is **NOT** created when the op is fed a malicious payload
(quote-breaking string for NCK / IMEI / package name / etc.).

## Device dataclass

```python
@dataclass
class Device:
    sn: str = ''
    brand: str = ''
    model: str = ''
    cpu: str = ''
    method: str = 'adb'  # adb|fastboot|serial|ios|none
    android: str = '?'
    display: str = 'No device detected'
```

Note there is **no** `serial` field — pass the serial as `sn`. The android
field stores the iOS *version* string for `method='ios'` (e.g. `'17.1'`).

## GUI assertions worth running

- 13 categories in sidebar: Device, Android ADB, Wi-Fi ADB, App Manager,
  Fastboot, Root (Magisk/KSU), Mkopa / PAYG, iPhone, Feature Phone, Network
  Unlock, MTK / EDL, Vendor, Maintenance.
- `Ctrl+F` opens search (focus the search box first if shortcut doesn't fire);
  search counter reads `<filtered>/<total> match`.
- `Ctrl+T` toggles between Catppuccin Mocha (`#1e1e2e`) and Latte (`#eff1f5`).
  If the round-trip doesn't fire, the active widget likely doesn't propagate
  the QShortcut — click the search box or sidebar to give it focus, then retry.
- `Ctrl+,` opens settings, `Ctrl+R` rescans devices, `Esc` aborts the running op.

## Devin Secrets Needed

None — testing is purely local on the VM and does not need any secrets,
logins, or API keys.

## Things to avoid

- Do not test using `gh` CLI in GHES environments.
- Do not start a recording before maximizing the GUI window.
- Do not run the app under pyenv Python — only `/usr/bin/python3` has the
  required PyQt5 bindings.
- Do not split shell state across `cmds` list items (see Worker.run() note).
