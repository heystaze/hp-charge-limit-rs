# HP Charge Limit — Windows GUI

A zero-dependency Python/Tkinter desktop GUI wrapper for [kralonur/hp-charge-limit-rs](https://github.com/kralonur/hp-charge-limit-rs) on Windows. It provides a visual dashboard and one-click controls for all `hp-charge-limit-rs.exe` CLI commands—monitoring battery telemetry, toggling temporary full-charge bypass, configuring charge thresholds, and managing the Windows background service without typing terminal commands manually.

## Features
- **Live Status Dashboard:** Visual battery charge progress bar alongside real-time AC adapter state, battery capacity/voltage, cycle count & health, bypass status, firmware charge mode (`inhibit`, `hold`, `auto`), Windows service status, and last off-state summary (`status` & `diagnose`).
- **Bypass & Single-Shot Firmware Control:** Enable or disable temporary full-charge bypass (`bypass on` / `bypass off`) or apply a one-time firmware mode (`set <MODE>`).
- **Validated Limiter Parameters:** Configure `--stop`, `--start`, `--interval`, `--run-mode`, `--off-mode`, `--off-min`, and `--stop-mode` with built-in threshold validation (`start < stop`), live CLI flag preview, and one-click service reconfiguration.
- **Windows Service & Foreground Daemon Management:** Install/reconfigure (`service install`), uninstall (`service uninstall`), start, stop, or restart the `hp-charge-limit-rs` Windows service, or run a foreground `daemon` with automatic conflict detection if the background service is already active.
- **Dark / Light Mode & Persistent Settings:** Custom pill-shaped theme toggle switch (with native Windows dark title bar support) and manual configuration saving (`gui_config.json`) for your executable path, theme preference, and limiter parameters.
- **Live Embedded Console:** Displays the exact CLI commands executed in the background along with real-time `stdout`/`stderr` output.

## Prerequisites
1. Download the official Windows CLI binary (`hp-charge-limit-rs.exe`) from [kralonur/hp-charge-limit-rs/releases](https://github.com/kralonur/hp-charge-limit-rs/releases).
2. The GUI automatically checks the current folder and `C:\Program Files\hp-charge-limit-rs\hp-charge-limit-rs.exe` on startup, or you can point to any location via **Browse...** and click **Save Settings**.

## Option 1: Run Directly from Source (Recommended)
You can inspect `hp_charge_gui.py` directly and run it with standard Python 3—no external `pip` packages are required:

```powershell
python hp_charge_gui.py
```

*(If launched without Administrator privileges, click **Restart as Admin** in the top bar before running `service` or `set` commands.)*

## Option 2: Build Your Own Standalone `.exe`
If you prefer a standalone executable without relying on pre-built binaries, compile `hp_charge_gui.py` yourself using PyInstaller:

```powershell
pip install pyinstaller
python -m PyInstaller --onefile --windowed --uac-admin --name "HPChargeLimitGUI" hp_charge_gui.py
```

Once complete, run `dist\HPChargeLimitGUI.exe` from any location, select your `hp-charge-limit-rs.exe` path via **Browse...** if needed, and click **Save Settings**.

## Credits & License
- Core HP WMI battery charge limiter CLI by [kralonur/hp-charge-limit-rs](https://github.com/kralonur/hp-charge-limit-rs).
- Licensed under either of [Apache License, Version 2.0](LICENSE-APACHE) or [MIT License](LICENSE-MIT).
