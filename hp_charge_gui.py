import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

CONFIG_FILE = "gui_config.json"
DEFAULT_EXE_PATHS = [
    r".\hp-charge-limit-rs.exe",
    r"C:\Program Files\hp-charge-limit-rs\hp-charge-limit-rs.exe",
]


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    if getattr(sys, "frozen", False):
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, "", None, 1)
    else:
        script = os.path.abspath(sys.argv[0])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}"', None, 1
        )
    sys.exit(0)


def set_windows_dark_titlebar(window: tk.Tk, enabled: bool):
    if os.name != "nt":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if enabled else 0)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
            )
    except Exception:
        pass


class ThemeToggleSwitch(tk.Canvas):
    """Custom pill-shaped Dark/Light mode switch."""

    def __init__(self, parent, variable: tk.BooleanVar, command=None):
        super().__init__(
            parent,
            width=86,
            height=24,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.variable = variable
        self.command = command
        self.bind("<Button-1>", self._toggle)
        self.redraw()

    def _toggle(self, _event=None):
        self.variable.set(not self.variable.get())
        self.redraw()
        if self.command:
            self.command()

    def redraw(self, panel_bg: str = "#26282c", text_fg: str = "#e6e8ec"):
        self.configure(bg=panel_bg)
        self.delete("all")
        is_dark = self.variable.get()

        track_color = "#0067c0" if is_dark else "#b8c0cc"
        knob_color = "#ffffff"
        # Pill track on the left (42x20)
        x0, y0, x1, y1 = 2, 2, 42, 22
        r = 10
        self.create_oval(x0, y0, x0 + 2 * r, y1, fill=track_color, outline=track_color)
        self.create_oval(x1 - 2 * r, y0, x1, y1, fill=track_color, outline=track_color)
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=track_color, outline=track_color)

        # Sliding circle knob
        kx = 24 if is_dark else 4
        self.create_oval(kx, 4, kx + 16, 20, fill=knob_color, outline="")

        # Label next to switch
        self.create_text(
            48,
            12,
            text="Dark" if is_dark else "Light",
            anchor="w",
            fill=text_fg,
            font=("Segoe UI", 9, "bold"),
        )


class HPChargeLimitGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HP Charge Limit — CLI GUI Wrapper")
        self.geometry("920x840")
        self.minsize(820, 720)

        self.exe_path = tk.StringVar(value=self._find_default_exe())
        self.auto_refresh = tk.BooleanVar(value=False)
        self.dark_mode = tk.BooleanVar(value=True)
        self.daemon_proc = None
        self.service_is_active = False

        # Structured flag variables (shared between Service & Daemon tabs)
        self.flag_stop = tk.IntVar(value=80)
        self.flag_start = tk.IntVar(value=75)
        self.flag_interval = tk.IntVar(value=30)
        self.flag_off_min = tk.IntVar(value=40)
        self.flag_run_mode = tk.StringVar(value="inhibit")
        self.flag_off_mode = tk.StringVar(value="hold")
        self.flag_stop_mode = tk.StringVar(value="auto")
        self.flags_preview_var = tk.StringVar(value="")

        self._load_config()
        self._bind_flag_traces()
        self._build_ui()
        self._apply_theme()
        self._update_flags_preview()
        self.run_cli(["status"], silent_log=False)

    def _get_palette(self) -> dict:
        if self.dark_mode.get():
            return {
                "bg": "#1e1f22",
                "panel": "#26282c",
                "input_bg": "#2f3238",
                "fg": "#e6e8ec",
                "muted": "#9aa0a6",
                "border": "#3c4047",
                "btn_bg": "#32353c",
                "btn_active": "#3e424b",
                "tab_bg": "#2c2f36",
                "tab_fg": "#b8bec8",
                "tab_active": "#383c45",
                "accent": "#0067c0",
                "accent_fg": "#ffffff",
                "preview_fg": "#64b5f6",
                "ok_fg": "#66bb6a",
                "warn_fg": "#ffb74d",
                "err_fg": "#ef5350",
                "term_bg": "#111214",
                "term_fg": "#e6e6e6",
            }
        return {
            "bg": "#f0f2f5",
            "panel": "#f5f6f8",
            "input_bg": "#ffffff",
            "fg": "#1f2328",
            "muted": "#57606a",
            "border": "#c8cdd5",
            "btn_bg": "#e4e7ec",
            "btn_active": "#d5dae2",
            "tab_bg": "#cfd6e0",
            "tab_fg": "#222222",
            "tab_active": "#b8c4d4",
            "accent": "#0067c0",
            "accent_fg": "#ffffff",
            "preview_fg": "#005a9e",
            "ok_fg": "#1b7e32",
            "warn_fg": "#b26a00",
            "err_fg": "#b3261e",
            "term_bg": "#121212",
            "term_fg": "#e6e6e6",
        }

    def _apply_theme(self):
        p = self._get_palette()
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.configure(bg=p["bg"])
        set_windows_dark_titlebar(self, self.dark_mode.get())

        style.configure(".", background=p["panel"], foreground=p["fg"], bordercolor=p["border"])
        style.configure("TFrame", background=p["panel"])
        style.configure("TLabelframe", background=p["panel"], bordercolor=p["border"])
        style.configure(
            "TLabelframe.Label",
            background=p["panel"],
            foreground=p["fg"],
            font=("Segoe UI", 9, "bold"),
        )
        style.configure("TLabel", background=p["panel"], foreground=p["fg"])
        style.configure("TCheckbutton", background=p["panel"], foreground=p["fg"])
        style.map(
            "TCheckbutton",
            background=[("active", p["panel"])],
            foreground=[("active", p["fg"])],
        )

        style.configure(
            "TButton",
            background=p["btn_bg"],
            foreground=p["fg"],
            bordercolor=p["border"],
            padding=[8, 3],
        )
        style.map(
            "TButton",
            background=[("active", p["btn_active"]), ("disabled", p["panel"])],
            foreground=[("disabled", p["muted"])],
        )

        style.configure(
            "TEntry",
            fieldbackground=p["input_bg"],
            foreground=p["fg"],
            insertcolor=p["fg"],
            bordercolor=p["border"],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=p["input_bg"],
            foreground=p["fg"],
            background=p["btn_bg"],
            arrowcolor=p["fg"],
            bordercolor=p["border"],
        )
        style.configure(
            "TCombobox",
            fieldbackground=p["input_bg"],
            foreground=p["fg"],
            background=p["btn_bg"],
            arrowcolor=p["fg"],
            bordercolor=p["border"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", p["input_bg"])],
            foreground=[("readonly", p["fg"])],
            selectbackground=[("readonly", p["accent"])],
            selectforeground=[("readonly", p["accent_fg"])],
        )

        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=p["input_bg"],
            background=p["accent"],
            bordercolor=p["border"],
        )
        style.configure("TPanedwindow", background=p["bg"])
        style.configure("Sash", sashthickness=5, background=p["border"])

        # Selected tab is slightly taller than unselected tabs
        style.configure("TNotebook", background=p["bg"], tabmargins=[2, 3, 2, 0])
        style.configure(
            "TNotebook.Tab",
            background=p["tab_bg"],
            foreground=p["tab_fg"],
            padding=[14, 4],
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", p["accent"]), ("active", p["tab_active"])],
            foreground=[("selected", p["accent_fg"]), ("active", p["fg"])],
            padding=[("selected", [14, 6])],
            expand=[("selected", [0, 2, 0, 0])],
        )

        if hasattr(self, "theme_switch"):
            self.theme_switch.redraw(panel_bg=p["panel"], text_fg=p["fg"])
        if hasattr(self, "admin_lbl"):
            admin_state = is_admin()
            self.admin_lbl.configure(
                foreground=p["ok_fg"] if admin_state else p["err_fg"]
            )
        if hasattr(self, "preview_lbl"):
            self.preview_lbl.configure(foreground=p["preview_fg"])
        if hasattr(self, "terminal"):
            self.terminal.configure(
                bg=p["term_bg"],
                fg=p["term_fg"],
                insertbackground=p["term_fg"],
            )

        self._recolor_status_labels()

    def _recolor_status_labels(self):
        if not hasattr(self, "status_labels"):
            return
        p = self._get_palette()
        fw = self.status_vars["firmware"].get()
        if fw != "—":
            is_limited = "inhibit" in fw.lower() or "hold" in fw.lower()
            self.status_labels["firmware"].configure(
                foreground=p["ok_fg"] if is_limited else p["warn_fg"]
            )
        bp = self.status_vars["bypass"].get()
        if bp != "—":
            is_disabled = "disabled" in bp.lower()
            self.status_labels["bypass"].configure(
                foreground=p["ok_fg"] if is_disabled else p["err_fg"]
            )
        sv = self.status_vars["service"].get()
        if sv != "—":
            self.status_labels["service"].configure(
                foreground=p["ok_fg"] if self.service_is_active else p["muted"]
            )

    def _find_default_exe(self) -> str:
        for p in DEFAULT_EXE_PATHS:
            if os.path.isfile(p):
                return os.path.abspath(p)
        return DEFAULT_EXE_PATHS[0]

    def _bind_flag_traces(self):
        for var in (
            self.flag_stop,
            self.flag_start,
            self.flag_interval,
            self.flag_off_min,
            self.flag_run_mode,
            self.flag_off_mode,
            self.flag_stop_mode,
        ):
            var.trace_add("write", lambda *_: self._update_flags_preview())

    def _update_flags_preview(self):
        try:
            preview = (
                f"--stop {self.flag_stop.get()} --start {self.flag_start.get()} "
                f"--interval {self.flag_interval.get()} --run-mode {self.flag_run_mode.get()} "
                f"--off-mode {self.flag_off_mode.get()} --off-min {self.flag_off_min.get()} "
                f"--stop-mode {self.flag_stop_mode.get()}"
            )
            self.flags_preview_var.set(preview)
        except Exception:
            pass

    def _load_config(self):
        if not os.path.isfile(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "exe_path" in data:
                self.exe_path.set(data["exe_path"])
            if "auto_refresh" in data:
                self.auto_refresh.set(bool(data["auto_refresh"]))
            if "dark_mode" in data:
                self.dark_mode.set(bool(data["dark_mode"]))
            if "stop" in data:
                self.flag_stop.set(int(data["stop"]))
            if "start" in data:
                self.flag_start.set(int(data["start"]))
            if "interval" in data:
                self.flag_interval.set(int(data["interval"]))
            if "off_min" in data:
                self.flag_off_min.set(int(data["off_min"]))
            if "run_mode" in data:
                self.flag_run_mode.set(data["run_mode"])
            if "off_mode" in data:
                self.flag_off_mode.set(data["off_mode"])
            if "stop_mode" in data:
                self.flag_stop_mode.set(data["stop_mode"])
        except Exception:
            pass

    def _save_config(self):
        data = {
            "exe_path": self.exe_path.get().strip(),
            "auto_refresh": self.auto_refresh.get(),
            "dark_mode": self.dark_mode.get(),
            "stop": self.flag_stop.get(),
            "start": self.flag_start.get(),
            "interval": self.flag_interval.get(),
            "off_min": self.flag_off_min.get(),
            "run_mode": self.flag_run_mode.get(),
            "off_mode": self.flag_off_mode.get(),
            "stop_mode": self.flag_stop_mode.get(),
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._log(f"[Saved settings to {os.path.abspath(CONFIG_FILE)}]\n", "ok")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save settings:\n{e}")

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # --- Top Bar: Executable Path, Save, Pill Theme Switch & Admin Status ---
        top_frame = ttk.Frame(self, relief="groove", borderwidth=1)
        top_frame.pack(fill="x", **pad)

        ttk.Label(top_frame, text="CLI Path:").pack(side="left", padx=(8, 4), pady=5)
        ttk.Entry(top_frame, textvariable=self.exe_path).pack(
            side="left", fill="x", expand=True, padx=4, pady=5
        )
        ttk.Button(top_frame, text="Browse...", command=self._browse_exe).pack(
            side="left", padx=3, pady=5
        )
        ttk.Button(top_frame, text="Save Settings", command=self._save_config).pack(
            side="left", padx=3, pady=5
        )

        self.theme_switch = ThemeToggleSwitch(
            top_frame, variable=self.dark_mode, command=self._apply_theme
        )
        self.theme_switch.pack(side="left", padx=8, pady=5)

        admin_state = is_admin()
        self.admin_lbl = ttk.Label(
            top_frame,
            text="Admin: YES" if admin_state else "Admin: NO",
            font=("Segoe UI", 9, "bold"),
        )
        self.admin_lbl.pack(side="left", padx=6)

        if not admin_state:
            ttk.Button(
                top_frame, text="Restart as Admin", command=relaunch_as_admin
            ).pack(side="left", padx=(0, 8), pady=5)

        # --- PanedWindow so Controls & Large Terminal can be resized freely ---
        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        upper_container = ttk.Frame(paned)
        paned.add(upper_container, weight=0)

        # --- Live Status Dashboard ---
        status_frame = ttk.LabelFrame(upper_container, text="Live Status (status)")
        status_frame.pack(fill="x", pady=(0, 5))

        bar_row = ttk.Frame(status_frame)
        bar_row.pack(fill="x", padx=8, pady=(4, 2))
        ttk.Label(bar_row, text="CHARGE:", font=("Segoe UI", 9, "bold"), width=10).pack(
            side="left"
        )
        self.battery_pct = tk.DoubleVar(value=0.0)
        self.battery_bar = ttk.Progressbar(
            bar_row, variable=self.battery_pct, maximum=100, length=260
        )
        self.battery_bar.pack(side="left", padx=(0, 10))
        self.battery_pct_label = ttk.Label(
            bar_row, text="—%", font=("Segoe UI", 9, "bold")
        )
        self.battery_pct_label.pack(side="left")

        self.status_vars = {
            "AC": tk.StringVar(value="—"),
            "battery": tk.StringVar(value="—"),
            "health": tk.StringVar(value="—"),
            "bypass": tk.StringVar(value="—"),
            "firmware": tk.StringVar(value="—"),
            "service": tk.StringVar(value="—"),
            "last off": tk.StringVar(value="—"),
        }
        self.status_labels = {}

        grid = ttk.Frame(status_frame)
        grid.pack(fill="x", padx=8, pady=2)

        items = list(self.status_vars.items())
        for idx, (key, var) in enumerate(items):
            r, c = divmod(idx, 2)
            ttk.Label(
                grid, text=f"{key.upper()}:", font=("Segoe UI", 9, "bold"), width=10
            ).grid(row=r, column=c * 2, sticky="w", pady=1)
            lbl = ttk.Label(grid, textvariable=var, width=40, font=("Segoe UI", 9))
            lbl.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 10), pady=1)
            self.status_labels[key] = lbl

        btn_row = ttk.Frame(status_frame)
        btn_row.pack(fill="x", padx=8, pady=(3, 5))
        ttk.Button(
            btn_row,
            text="Refresh Status",
            command=lambda: self.run_cli(["status"]),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            btn_row,
            text="Run Diagnose",
            command=lambda: self.run_cli(["diagnose"]),
        ).pack(side="left", padx=6)
        ttk.Button(
            btn_row,
            text="CLI Help (--help)",
            command=lambda: self.run_cli(["--help"]),
        ).pack(side="left", padx=6)
        ttk.Checkbutton(
            btn_row,
            text="Auto-refresh status (10s)",
            variable=self.auto_refresh,
            command=self._schedule_refresh,
        ).pack(side="right")

        # --- Notebook Tabs for CLI Subcommands ---
        tabs = ttk.Notebook(upper_container)
        tabs.pack(fill="x", pady=(0, 2))

        # Tab 1: Bypass & Set Mode Side-by-Side
        tab_ctrl = ttk.Frame(tabs, padding=8)
        tabs.add(tab_ctrl, text="Bypass & Firmware Set")

        side_by_side = ttk.Frame(tab_ctrl)
        side_by_side.pack(fill="x")

        bypass_box = ttk.LabelFrame(
            side_by_side, text="Bypass (Pause/Resume until reboot)"
        )
        bypass_box.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ttk.Button(
            bypass_box,
            text="Bypass ON (Pause Limiting)",
            command=lambda: self._run_and_refresh(["bypass", "on"]),
        ).pack(side="left", padx=8, pady=6)
        ttk.Button(
            bypass_box,
            text="Bypass OFF (Resume Limiting)",
            command=lambda: self._run_and_refresh(["bypass", "off"]),
        ).pack(side="left", padx=8, pady=6)

        set_box = ttk.LabelFrame(
            side_by_side, text="Set Firmware Charge Mode Once (set <MODE>)"
        )
        set_box.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ttk.Label(set_box, text="Mode:").pack(side="left", padx=(8, 4), pady=6)
        self.set_mode_var = tk.StringVar(value="inhibit")
        ttk.Combobox(
            set_box,
            textvariable=self.set_mode_var,
            values=["inhibit", "hold", "normal", "auto"],
            width=12,
        ).pack(side="left", padx=4, pady=6)
        ttk.Button(
            set_box,
            text="Execute 'set'",
            command=self._execute_set_mode,
        ).pack(side="left", padx=6, pady=6)
        ttk.Button(
            set_box,
            text="set --help",
            command=lambda: self.run_cli(["set", "--help"]),
        ).pack(side="right", padx=8, pady=6)

        # Tab 2: Structured Limiter Flags (Shared by Service & Daemon)
        tab_flags = ttk.Frame(tabs, padding=8)
        tabs.add(tab_flags, text="Limiter Parameters (Flags)")

        f_grid = ttk.Frame(tab_flags)
        f_grid.pack(fill="x")

        ttk.Label(f_grid, text="Stop Charge (%):").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Spinbox(f_grid, from_=20, to=100, textvariable=self.flag_stop, width=8).grid(
            row=0, column=1, sticky="w", padx=(6, 18), pady=3
        )

        ttk.Label(f_grid, text="Start Charge (%):").grid(row=0, column=2, sticky="w", pady=3)
        ttk.Spinbox(f_grid, from_=10, to=99, textvariable=self.flag_start, width=8).grid(
            row=0, column=3, sticky="w", padx=(6, 18), pady=3
        )

        ttk.Label(f_grid, text="Poll Interval (sec):").grid(row=0, column=4, sticky="w", pady=3)
        ttk.Spinbox(f_grid, from_=5, to=3600, textvariable=self.flag_interval, width=8).grid(
            row=0, column=5, sticky="w", padx=(6, 0), pady=3
        )

        ttk.Label(f_grid, text="Run Mode:").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(
            f_grid,
            textvariable=self.flag_run_mode,
            values=["inhibit", "hold", "normal", "auto"],
            width=10,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", padx=(6, 18), pady=3)

        ttk.Label(f_grid, text="Off Mode:").grid(row=1, column=2, sticky="w", pady=3)
        ttk.Combobox(
            f_grid,
            textvariable=self.flag_off_mode,
            values=["hold", "inhibit", "normal", "auto"],
            width=10,
            state="readonly",
        ).grid(row=1, column=3, sticky="w", padx=(6, 18), pady=3)

        ttk.Label(f_grid, text="Stop Mode:").grid(row=1, column=4, sticky="w", pady=3)
        ttk.Combobox(
            f_grid,
            textvariable=self.flag_stop_mode,
            values=["auto", "inhibit", "hold", "normal"],
            width=10,
            state="readonly",
        ).grid(row=1, column=5, sticky="w", padx=(6, 0), pady=3)

        ttk.Label(f_grid, text="Off-Min (%):").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Spinbox(f_grid, from_=5, to=95, textvariable=self.flag_off_min, width=8).grid(
            row=2, column=1, sticky="w", padx=(6, 18), pady=3
        )

        flag_btns = ttk.Frame(f_grid)
        flag_btns.grid(row=2, column=2, columnspan=4, sticky="e", pady=3)
        ttk.Button(
            flag_btns, text="Save Parameters", command=self._save_config
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            flag_btns,
            text="Apply to Service (service install)",
            command=self._apply_params_to_service,
        ).pack(side="left")

        preview_row = ttk.Frame(tab_flags)
        preview_row.pack(fill="x", pady=(4, 0))
        ttk.Label(preview_row, text="Generated Flags:", font=("Segoe UI", 8, "bold")).pack(
            side="left", padx=(0, 6)
        )
        self.preview_lbl = ttk.Label(
            preview_row,
            textvariable=self.flags_preview_var,
            font=("Consolas", 8),
        )
        self.preview_lbl.pack(side="left")

        # Tab 3: Windows Service
        tab_srv = ttk.Frame(tabs, padding=8)
        tabs.add(tab_srv, text="Windows Service")

        srv_row1 = ttk.Frame(tab_srv)
        srv_row1.pack(fill="x", pady=(0, 6))
        ttk.Button(
            srv_row1,
            text="Start Service",
            command=self._start_windows_service,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            srv_row1,
            text="Stop Service",
            command=self._stop_windows_service,
        ).pack(side="left", padx=6)
        ttk.Button(
            srv_row1,
            text="Restart Service",
            command=self._restart_windows_service,
        ).pack(side="left", padx=6)

        srv_row2 = ttk.Frame(tab_srv)
        srv_row2.pack(fill="x")
        ttk.Button(
            srv_row2,
            text="Install / Reconfigure Service (Uses Limiter Parameters)",
            command=self._install_service,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            srv_row2,
            text="Uninstall Service",
            command=self._uninstall_service,
        ).pack(side="left", padx=6)
        ttk.Button(
            srv_row2,
            text="service --help",
            command=lambda: self.run_cli(["service", "--help"]),
        ).pack(side="right", padx=6)

        # Tab 4: Manual Daemon & Completions
        tab_daemon = ttk.Frame(tabs, padding=8)
        tabs.add(tab_daemon, text="Manual Daemon & Completions")

        d_row = ttk.Frame(tab_daemon)
        d_row.pack(fill="x", pady=(0, 6))
        self.btn_start_daemon = ttk.Button(
            d_row,
            text="Start Foreground Daemon (Uses Limiter Parameters)",
            command=self._start_daemon,
        )
        self.btn_start_daemon.pack(side="left", padx=(0, 8))
        self.btn_stop_daemon = ttk.Button(
            d_row,
            text="Stop Foreground Daemon",
            command=self._stop_daemon,
            state="disabled",
        )
        self.btn_stop_daemon.pack(side="left", padx=8)

        c_row = ttk.Frame(tab_daemon)
        c_row.pack(fill="x")
        ttk.Label(c_row, text="Shell Completions:").pack(side="left", padx=(0, 6))
        self.shell_var = tk.StringVar(value="powershell")
        ttk.Combobox(
            c_row,
            textvariable=self.shell_var,
            values=["powershell", "bash", "zsh", "fish", "elvish"],
            width=14,
            state="readonly",
        ).pack(side="left", padx=4)
        ttk.Button(
            c_row,
            text="Generate Completions",
            command=lambda: self.run_cli(["completions", self.shell_var.get()]),
        ).pack(side="left", padx=8)

        # --- Compact Terminal Output Pane (Header + Clear button on same line) ---
        term_frame = ttk.Frame(paned, relief="groove", borderwidth=1)
        paned.add(term_frame, weight=1)

        term_header = ttk.Frame(term_frame)
        term_header.pack(fill="x", padx=6, pady=(3, 2))
        ttk.Label(
            term_header,
            text="Terminal Output",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        ttk.Button(term_header, text="Clear Terminal", command=self._clear_log).pack(
            side="right"
        )

        self.terminal = scrolledtext.ScrolledText(
            term_frame,
            bg="#111214",
            fg="#e6e6e6",
            insertbackground="#ffffff",
            font=("Consolas", 10),
            height=22,
            wrap="word",
            state="disabled",
        )
        self.terminal.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.terminal.tag_config("cmd", foreground="#4fc3f7", font=("Consolas", 10, "bold"))
        self.terminal.tag_config("err", foreground="#ff6b6b")
        self.terminal.tag_config("ok", foreground="#81c784")

    def _build_validated_flags(self) -> list[str] | None:
        stop_v = self.flag_stop.get()
        start_v = self.flag_start.get()
        if start_v >= stop_v:
            messagebox.showerror(
                "Invalid Thresholds",
                f"Start Charge ({start_v}%) must be strictly lower than Stop Charge ({stop_v}%).",
            )
            return None
        return [
            "--stop", str(stop_v),
            "--start", str(start_v),
            "--interval", str(self.flag_interval.get()),
            "--run-mode", self.flag_run_mode.get(),
            "--off-mode", self.flag_off_mode.get(),
            "--off-min", str(self.flag_off_min.get()),
            "--stop-mode", self.flag_stop_mode.get(),
        ]

    def _check_admin_preflight(self, action_name: str) -> bool:
        if is_admin():
            return True
        if messagebox.askyesno(
            "Administrator Privileges Required",
            f"'{action_name}' requires Administrator privileges on Windows.\n\n"
            "Would you like to restart the app as Administrator now?",
        ):
            relaunch_as_admin()
        return False

    def _browse_exe(self):
        path = filedialog.askopenfilename(
            title="Select hp-charge-limit-rs.exe",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")],
        )
        if path:
            self.exe_path.set(path)

    def _log(self, text: str, tag: str = None):
        self.terminal.configure(state="normal")
        if tag:
            self.terminal.insert("end", text, tag)
        else:
            self.terminal.insert("end", text)
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    def _clear_log(self):
        self.terminal.configure(state="normal")
        self.terminal.delete("1.0", "end")
        self.terminal.configure(state="disabled")

    def _parse_status_output(self, output: str):
        p = self._get_palette()
        for line in output.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key in self.status_vars:
                    self.status_vars[key].set(val)

                    if key == "battery":
                        match = re.search(r"(\d+(?:\.\d+)?)%", val)
                        if match:
                            pct = float(match.group(1))
                            self.battery_pct.set(pct)
                            self.battery_pct_label.configure(text=f"{pct:.0f}%")

                    elif key == "firmware":
                        is_limited = "inhibit" in val.lower() or "hold" in val.lower()
                        self.status_labels[key].configure(
                            foreground=p["ok_fg"] if is_limited else p["warn_fg"],
                            font=("Segoe UI", 9, "bold"),
                        )

                    elif key == "bypass":
                        is_disabled = "disabled" in val.lower()
                        self.status_labels[key].configure(
                            foreground=p["ok_fg"] if is_disabled else p["err_fg"],
                            font=("Segoe UI", 9, "bold"),
                        )

                    elif key == "service":
                        self.service_is_active = (
                            "active" in val.lower() and "inactive" not in val.lower()
                        )
                        self.status_labels[key].configure(
                            foreground=p["ok_fg"] if self.service_is_active else p["muted"],
                            font=("Segoe UI", 9, "bold"),
                        )

    def _run_and_refresh(self, args: list[str]):
        self.run_cli(args, follow_up_status=True)

    def _run_sc_command(self, sc_args_list: list[list[str]], description: str):
        def worker():
            for sc_args in sc_args_list:
                cmd = ["sc.exe"] + sc_args
                self.after(0, self._log, f"\n> {' '.join(cmd)}\n", "cmd")
                try:
                    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                    proc = subprocess.run(
                        cmd, capture_output=True, text=True, creationflags=creationflags
                    )
                    if proc.stdout:
                        self.after(0, self._log, proc.stdout)
                    if proc.stderr:
                        self.after(0, self._log, proc.stderr, "err")
                except Exception as e:
                    self.after(0, self._log, f"sc.exe error: {e}\n", "err")
            self.after(400, lambda: self.run_cli(["status"], silent_log=True))

        threading.Thread(target=worker, daemon=True).start()

    def run_cli(
        self, args: list[str], silent_log: bool = False, follow_up_status: bool = False
    ):
        exe = self.exe_path.get().strip()
        if not exe:
            messagebox.showerror("Missing Executable", "Please specify hp-charge-limit-rs.exe path.")
            return

        cmd = [exe] + args

        def worker():
            if not silent_log:
                self.after(0, self._log, f"\n> {' '.join(cmd)}\n", "cmd")
            try:
                creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    creationflags=creationflags,
                )
                stdout = proc.stdout or ""
                stderr = proc.stderr or ""

                if stdout:
                    if not silent_log:
                        self.after(0, self._log, stdout)
                    if args and args[0] == "status":
                        self.after(0, self._parse_status_output, stdout)

                if stderr:
                    self.after(0, self._log, stderr, "err")

                if proc.returncode != 0 and not stderr:
                    self.after(
                        0,
                        self._log,
                        f"[Exited with code {proc.returncode}]\n",
                        "err",
                    )

                if follow_up_status:
                    self.after(300, lambda: self.run_cli(["status"], silent_log=True))

            except FileNotFoundError:
                self.after(
                    0,
                    self._log,
                    f"Error: Executable not found at '{exe}'\n",
                    "err",
                )
            except Exception as e:
                self.after(0, self._log, f"Execution error: {e}\n", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _execute_set_mode(self):
        if not self._check_admin_preflight("set"):
            return
        mode = self.set_mode_var.get().strip()
        if not mode:
            return
        if messagebox.askyesno(
            "Confirm Firmware Mode Change",
            f"Set firmware charge mode once to '{mode}'?\n\n"
            f"Command: hp-charge-limit-rs.exe set {mode}",
        ):
            self._run_and_refresh(["set", mode])

    def _start_windows_service(self):
        if not self._check_admin_preflight("Start Service"):
            return
        if messagebox.askyesno(
            "Confirm Start Service",
            "Start the 'hp-charge-limit-rs' Windows service now?",
        ):
            self._run_sc_command([["start", "hp-charge-limit-rs"]], "Start Service")

    def _stop_windows_service(self):
        if not self._check_admin_preflight("Stop Service"):
            return
        if messagebox.askyesno(
            "Confirm Stop Service",
            "Stop the 'hp-charge-limit-rs' Windows service?\n\n"
            "Background charge limiting will pause while the service is stopped.",
        ):
            self._run_sc_command([["stop", "hp-charge-limit-rs"]], "Stop Service")

    def _restart_windows_service(self):
        if not self._check_admin_preflight("Restart Service"):
            return
        if messagebox.askyesno(
            "Confirm Restart Service",
            "Restart the 'hp-charge-limit-rs' Windows service?\n\n"
            "This will run:\n"
            "1. sc.exe stop hp-charge-limit-rs\n"
            "2. sc.exe start hp-charge-limit-rs",
        ):
            self._run_sc_command(
                [["stop", "hp-charge-limit-rs"], ["start", "hp-charge-limit-rs"]],
                "Restart Service",
            )

    def _apply_params_to_service(self):
        self._save_config()
        self._install_service()

    def _install_service(self):
        if not self._check_admin_preflight("service install"):
            return
        flags = self._build_validated_flags()
        if flags is None:
            return
        if messagebox.askyesno(
            "Confirm Service Install / Reconfigure",
            "Install or reconfigure the 'hp-charge-limit-rs' Windows service with these parameters?\n\n"
            "Note: This copies the exe to C:\\Program Files\\hp-charge-limit-rs\\ and updates the service configuration.\n\n"
            + " ".join(flags),
        ):
            self._run_and_refresh(["service", "install"] + flags)

    def _uninstall_service(self):
        if not self._check_admin_preflight("service uninstall"):
            return
        if messagebox.askyesno(
            "Confirm Service Uninstall",
            "Are you sure you want to uninstall the 'hp-charge-limit-rs' Windows service?\n\n"
            "This stops the service (setting firmware to auto) and removes it from Program Files.",
        ):
            self._run_and_refresh(["service", "uninstall"])

    def _start_daemon(self):
        if self.daemon_proc is not None:
            return
        flags = self._build_validated_flags()
        if flags is None:
            return

        if self.service_is_active:
            choice = messagebox.askyesnocancel(
                "Windows Service Is Active",
                "The 'hp-charge-limit-rs' Windows service is currently active.\n"
                "Two loops would fight over the charge mode.\n\n"
                "• Click YES to stop the service first (sc.exe stop hp-charge-limit-rs) and start the foreground daemon.\n"
                "• Click NO to start the foreground daemon anyway.\n"
                "• Click CANCEL to abort.",
            )
            if choice is None:
                return
            if choice is True:
                if not self._check_admin_preflight("Stop Windows Service"):
                    return
                self._run_sc_command([["stop", "hp-charge-limit-rs"]], "Stop Service")
                self.after(900, lambda: self._launch_daemon_process(flags))
                return

        if not messagebox.askyesno(
            "Confirm Start Foreground Daemon",
            "Start the foreground limiter daemon with these parameters?\n\n"
            + " ".join(flags),
        ):
            return

        self._launch_daemon_process(flags)

    def _launch_daemon_process(self, flags: list[str]):
        exe = self.exe_path.get().strip()
        cmd = [exe, "daemon"] + flags
        self._log(f"\n> {' '.join(cmd)}\n", "cmd")

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.daemon_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags,
            )
            self.btn_start_daemon.configure(state="disabled")
            self.btn_stop_daemon.configure(state="normal")

            def stream_reader():
                for line in self.daemon_proc.stdout:
                    self.after(0, self._log, line)
                self.after(0, self._on_daemon_exit)

            threading.Thread(target=stream_reader, daemon=True).start()
        except Exception as e:
            self.daemon_proc = None
            self._log(f"Failed to start daemon: {e}\n", "err")

    def _stop_daemon(self):
        if not self.daemon_proc:
            return
        if messagebox.askyesno(
            "Confirm Stop Foreground Daemon",
            "Are you sure you want to stop the running foreground daemon?",
        ):
            self.daemon_proc.terminate()
            self._log("[Foreground daemon terminated]\n", "ok")

    def _on_daemon_exit(self):
        self.daemon_proc = None
        self.btn_start_daemon.configure(state="normal")
        self.btn_stop_daemon.configure(state="disabled")

    def _schedule_refresh(self):
        if self.auto_refresh.get():
            self.run_cli(["status"], silent_log=True)
            self.after(10000, self._schedule_refresh)


if __name__ == "__main__":
    app = HPChargeLimitGUI()
    app.mainloop()