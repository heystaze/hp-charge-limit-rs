# HP Charge Limit — Windows GUI

A zero-dependency Python/Tkinter desktop GUI wrapper for [kralonur/hp-charge-limit-rs](https://github.com/kralonur/hp-charge-limit-rs) on Windows, allowing you to monitor battery status, toggle full-charge bypass, configure charge thresholds, and manage the Windows background service without typing CLI commands.

## Features
- **Live Status Dashboard:** Visual charge progress bar, AC/battery telemetry, firmware charge mode, bypass state, and Windows service status.
- **Bypass & Single-Shot Firmware Control:** Toggle `bypass on` / `bypass off` or apply a single `set` charge mode.
- **Validated Limiter Parameters:** Configure `--stop`, `--start`, `--interval`, `--run-mode`, `--off-mode`, `--off-min`, and `--stop-mode` with threshold validation (`start < stop`) and live flag preview.
- **Windows Service & Foreground Daemon Controls:** Install/reconfigure, uninstall, start, stop, or restart the `hp-charge-limit-rs` service, or run a foreground daemon with active-service conflict detection.
- **Dark / Light Mode & Persistent Settings:** Custom theme toggle switch and manual save (`gui_config.json`) for your executable path and parameters.

## Quick Start

1. Download the latest Windows release (`hp-charge-limit-rs.exe`) from [kralonur/hp-charge-limit-rs/releases](https://github.com/kralonur/hp-charge-limit-rs/releases).
2. Download `HPChargeLimitGUI.exe` from this repository's **Releases** page (or run `python hp_charge_gui.py` with Python 3).
3. Place both `.exe` files in the same folder (or click **Browse...** in the app to select `hp-charge-limit-rs.exe` and click **Save Settings**).
4. Click **Restart as Admin** when installing/reconfiguring the Windows service or reading protected WMI firmware states.

## Build Standalone `.exe` from Source

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --uac-admin --name "HPChargeLimitGUI" hp_charge_gui.py
