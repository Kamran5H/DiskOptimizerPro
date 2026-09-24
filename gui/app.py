import os
import sys
import threading
import queue
import time
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from PIL import Image

from engine.system_ops import (
    is_admin,
    get_disk_stats,
    get_all_drives_stats,
    run_powershell
)
from engine.cleaner_engine import (
    CleanerEngine,
    is_process_running,
    stop_processes
)
from engine.large_files import scan_large_files_multi
from engine.duplicate_finder import find_duplicate_files
from engine.empty_folder_cleaner import scan_empty_directories, delete_empty_directories

# Ensure UTF-8 output across Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Set CustomTkinter Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
ctk.deactivate_automatic_dpi_awareness()


class DiskOptimizerApp(ctk.CTk):
    """
    Disk Optimizer Pro V2 - Kamran Ashraf
    Executive Dual-Drive (C: & D:) PC Optimization & Cleanup Suite
    """
    def __init__(self):
        super().__init__()

        self.title("Disk Optimizer Pro V2 - Kamran Ashraf")
        
        # Adaptive geometry fitting both 720p laptops and 1080p+ desktops cleanly
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        app_w = min(1180, max(960, screen_w - 60))
        app_h = min(780, max(580, screen_h - 80))
        self.geometry(f"{app_w}x{app_h}")
        self.minsize(min(960, app_w), min(580, app_h))

        self.configure(fg_color="#0b1120")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Set App Icon if available
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base_dir, "assets", "app_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # Execution State
        self.is_running = False
        self.log_queue = queue.Queue()
        self.engine = CleanerEngine(log_cb=self._enqueue_log)
        self.cleaned_bytes_total = 0
        self.initial_free_map = {}

        # Scanner states
        self.is_large_scanning = False
        self.is_duplicate_scanning = False
        self.is_empty_scanning = False
        self.stop_large_scan = False
        self.stop_dupe_scan = False
        self.stop_empty_scan = False

        # Build UI
        self._build_header()
        self._build_tabview()

        # Telemetry & Logger Polling
        self.refresh_all_disk_stats()
        self.after(50, self._process_log_queue)

    # -----------------------------------------------------------------
    # HEADER & DUAL-DRIVE TELEMETRY
    # -----------------------------------------------------------------

    def _build_header(self):
        """Header with App Title, Admin Badge, and Dual-Drive Telemetry (C: & D:)"""
        self.header_frame = ctk.CTkFrame(self, fg_color="#131d31", corner_radius=12)
        self.header_frame.pack(fill="x", padx=16, pady=(12, 6))

        # Title Block
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=16, pady=10)

        app_title = ctk.CTkLabel(
            title_box,
            text="⚡ DISK OPTIMIZER PRO V2",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#38bdf8"
        )
        app_title.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            title_box,
            text="Executive Dual-Drive (C: & D:) PC Optimization Suite • Kamran Ashraf",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        sub_lbl.pack(anchor="w")

        # Admin Badge
        has_admin = is_admin()
        admin_text = "🛡️ Admin: YES" if has_admin else "⚠️ Admin: NO (Click to Elevate)"
        admin_fg = "#064e3b" if has_admin else "#78350f"
        admin_text_color = "#34d399" if has_admin else "#fcd34d"

        self.admin_btn = ctk.CTkButton(
            self.header_frame,
            text=admin_text,
            fg_color=admin_fg,
            hover_color="#047857" if has_admin else "#92400e",
            text_color=admin_text_color,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=8,
            height=30,
            command=self.request_elevation if not has_admin else None
        )
        self.admin_btn.pack(side="left", padx=12, pady=10)

        # Drive Telemetry Right Container
        telemetry_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        telemetry_box.pack(side="right", padx=14, pady=8)

        # Drive C: Card
        self.c_card = ctk.CTkFrame(telemetry_box, fg_color="#1e293b", corner_radius=8)
        self.c_card.pack(side="left", padx=6, pady=2)

        self.c_label = ctk.CTkLabel(
            self.c_card,
            text="Drive C: -- GB Free (0%)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#f8fafc"
        )
        self.c_label.pack(padx=10, pady=(4, 2))

        self.c_progress = ctk.CTkProgressBar(self.c_card, width=150, height=6, corner_radius=3)
        self.c_progress.set(0.1)
        self.c_progress.pack(padx=10, pady=(0, 6))

        # Drive D: Card
        self.d_card = ctk.CTkFrame(telemetry_box, fg_color="#1e293b", corner_radius=8)
        self.d_card.pack(side="left", padx=6, pady=2)

        self.d_label = ctk.CTkLabel(
            self.d_card,
            text="Drive D: -- GB Free (0%)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#f8fafc"
        )
        self.d_label.pack(padx=10, pady=(4, 2))

        self.d_progress = ctk.CTkProgressBar(self.d_card, width=150, height=6, corner_radius=3)
        self.d_progress.set(0.25)
        self.d_progress.pack(padx=10, pady=(0, 6))

        # Refresh Telemetry Button
        self.refresh_btn = ctk.CTkButton(
            telemetry_box,
            text="🔄",
            width=32,
            height=32,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=13),
            command=self.refresh_all_disk_stats
        )
        self.refresh_btn.pack(side="left", padx=(6, 0))

    # -----------------------------------------------------------------
    # TABVIEW CONTAINER
    # -----------------------------------------------------------------

    def _build_tabview(self):
        """Creates the 4 tabs: 1-Click Optimizer, Large Files, Duplicate Finder, Empty Folders"""
        self.tabview = ctk.CTkTabview(
            self,
            fg_color="#0f172a",
            segmented_button_fg_color="#131d31",
            segmented_button_selected_color="#0284c7",
            segmented_button_selected_hover_color="#0369a1",
            text_color="#f8fafc"
        )
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.tab_optimizer = self.tabview.add("🚀 1-Click Optimizer")
        self.tab_large = self.tabview.add("🔍 Large Files Finder")
        self.tab_dupes = self.tabview.add("👥 Duplicate Files Finder")
        self.tab_empty = self.tabview.add("🧹 Empty Folders Cleaner")

        self._build_tab_optimizer()
        self._build_tab_large_files()
        self._build_tab_duplicates()
        self._build_tab_empty_folders()

    # -----------------------------------------------------------------
    # TAB 1: 1-CLICK OPTIMIZER
    # -----------------------------------------------------------------

    def _build_tab_optimizer(self):
        tab = self.tab_optimizer

        # Top Control & Preset Bar
        top_bar = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        top_bar.pack(fill="x", padx=4, pady=(2, 8))

        # 1-Click Clean All Button
        self.clean_btn = ctk.CTkButton(
            top_bar,
            text="🚀 1-CLICK CLEAN ALL",
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=38,
            corner_radius=8,
            command=self.start_cleanup
        )
        self.clean_btn.pack(side="left", padx=(10, 4), pady=8)

        self.clean_stop_btn = ctk.CTkButton(
            top_bar,
            text="⏹️ Stop",
            width=65,
            height=38,
            fg_color="#475569",
            hover_color="#64748b",
            state="disabled",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=8,
            command=self.stop_cleanup_action
        )
        self.clean_stop_btn.pack(side="left", padx=(0, 8), pady=8)

        # Drive Scope Selector
        scope_lbl = ctk.CTkLabel(top_bar, text="Target Scope:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8")
        scope_lbl.pack(side="left", padx=(8, 4))

        self.scope_var = ctk.StringVar(value="All Drives (C: & D:)")
        self.scope_seg = ctk.CTkSegmentedButton(
            top_bar,
            values=["All Drives (C: & D:)", "Drive C: Only", "Drive D: Only"],
            variable=self.scope_var,
            selected_color="#0284c7",
            selected_hover_color="#0369a1",
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.scope_seg.pack(side="left", padx=4)

        # Preset Menu
        preset_lbl = ctk.CTkLabel(top_bar, text="Preset:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8")
        preset_lbl.pack(side="left", padx=(12, 4))

        self.preset_menu = ctk.CTkOptionMenu(
            top_bar,
            values=["Safe Fast Clean", "Deep System Clean", "Drive D: Clean", "Developer Clean", "Select All", "Clear All"],
            command=self.apply_preset,
            fg_color="#1e293b",
            button_color="#334155",
            button_hover_color="#475569",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            height=34,
            corner_radius=8
        )
        self.preset_menu.set("Safe Fast Clean")
        self.preset_menu.pack(side="left", padx=4)

        # Split Container: Checklists Left, Terminal Right
        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=0, pady=0)

        # Left Column: Checklists
        left_col = ctk.CTkFrame(body, fg_color="#131d31", corner_radius=10)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=0)

        self.task_scroll = ctk.CTkScrollableFrame(left_col, fg_color="transparent")
        self.task_scroll.pack(fill="both", expand=True, padx=8, pady=8)

        self.tasks = {}
        self._build_task_categories()

        # Right Column: Terminal & Metrics
        right_col = ctk.CTkFrame(body, fg_color="#131d31", corner_radius=10)
        right_col.pack(side="right", fill="both", expand=True, padx=(6, 0), pady=0)

        log_head = ctk.CTkFrame(right_col, fg_color="transparent")
        log_head.pack(fill="x", padx=12, pady=(10, 4))

        console_title = ctk.CTkLabel(
            log_head,
            text="💻 Execution Terminal & Live Space Tally",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8"
        )
        console_title.pack(side="left")

        clear_btn = ctk.CTkButton(
            log_head,
            text="Clear",
            width=54,
            height=24,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.clear_logs
        )
        clear_btn.pack(side="right")

        self.console = ctk.CTkTextbox(
            right_col,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#090d16",
            text_color="#e2e8f0",
            corner_radius=8,
            wrap="word"
        )
        self.console.pack(fill="both", expand=True, padx=12, pady=4)

        # Console color tags
        self.console.tag_config("info", foreground="#94a3b8")
        self.console.tag_config("step", foreground="#38bdf8")
        self.console.tag_config("success", foreground="#34d399")
        self.console.tag_config("warning", foreground="#fbbf24")
        self.console.tag_config("error", foreground="#f87171")
        self.console.tag_config("bold", foreground="#38bdf8")

        # Bottom Progress Bar
        bottom_box = ctk.CTkFrame(right_col, fg_color="#1e293b", corner_radius=8)
        bottom_box.pack(fill="x", padx=12, pady=(4, 10))

        self.progress_bar = ctk.CTkProgressBar(bottom_box, height=8, corner_radius=4)
        self.progress_bar.set(0)
        self.progress_bar.configure(progress_color="#10b981", fg_color="#334155")
        self.progress_bar.pack(fill="x", padx=12, pady=(8, 4))

        stat_row = ctk.CTkFrame(bottom_box, fg_color="transparent")
        stat_row.pack(fill="x", padx=12, pady=(2, 6))

        self.status_text = ctk.CTkLabel(
            stat_row,
            text="Ready to optimize drives.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        self.status_text.pack(side="left")

        self.recovered_label = ctk.CTkLabel(
            stat_row,
            text="Freed: 0.0 MB",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#34d399"
        )
        self.recovered_label.pack(side="right")

    def _build_task_categories(self):
        def create_category_card(title: str, icon: str):
            card = ctk.CTkFrame(self.task_scroll, fg_color="#1e293b", corner_radius=8)
            card.pack(fill="x", pady=4)
            header = ctk.CTkLabel(
                card,
                text=f"{icon} {title}",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#38bdf8"
            )
            header.pack(anchor="w", padx=10, pady=(6, 3))
            return card

        def add_task(card, key, label, default=True, warning=""):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            var = ctk.BooleanVar(value=default)
            chk = ctk.CTkCheckBox(
                row,
                text=label,
                variable=var,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#f1f5f9",
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=4,
                hover_color="#0284c7"
            )
            chk.pack(side="left", fill="x", expand=True)

            if warning:
                badge = ctk.CTkLabel(
                    row,
                    text=warning,
                    font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                    text_color="#fbbf24",
                    fg_color="#78350f",
                    corner_radius=4,
                    padx=4,
                    pady=1
                )
                badge.pack(side="right", padx=4)

            self.tasks[key] = {"var": var, "label": label, "chk": chk, "default": default}

        # CATEGORY 1: System Temp & Log Caches
        c1 = create_category_card("System Temp & Error Logs", "🧹")
        add_task(c1, "user_temp", "User Temp Folder ($env:TEMP)", True)
        add_task(c1, "win_temp", "Windows Temp Folder (C:\\Windows\\Temp)", True)
        add_task(c1, "wer_reports", "Windows Error Reporting (WER)", True)
        add_task(c1, "thumb_cache", "Explorer Thumbnail Cache", True)
        add_task(c1, "recent_items", "Recent Items Shortcuts", True)
        add_task(c1, "recycle_bin", "Empty Recycle Bin (C: & D:)", True)
        add_task(c1, "crash_dumps", "Crash Dumps & Minidumps", True)
        add_task(c1, "font_d3d_icon", "FontCache, D3DSCache & IconCache", True)

        # CATEGORY 2: Drive D: Dedicated Cleanups
        c2 = create_category_card("Drive D: Dedicated Cleanups", "💾")
        add_task(c2, "drive_d_junk", "Clean D: Root VC++ Leftovers (25 items)", True, "D: Root")
        add_task(c2, "drive_d_pycache", "Sweep D: Python __pycache__ & .pytest_cache", True, "D: Cache")

        # CATEGORY 3: Browser & Developer Caches
        c3 = create_category_card("Browser & Developer Caches", "🌐")
        add_task(c3, "chrome_cache", "Google Chrome Caches (All Profiles)", True)
        add_task(c3, "edge_cache", "Microsoft Edge Caches (All Profiles)", True)
        add_task(c3, "pip_cache", "Python pip Cache ($env:LOCALAPPDATA\\pip\\cache)", True)
        add_task(c3, "dev_superpack", "Developer Super-Pack (NPM, VS Code, Yarn)", True)
        add_task(c3, "chrome_history", "Chrome Bloated History & Favicons (> 10MB)", False, "History >10MB")
        add_task(c3, "old_playwright", "Old Playwright Versions (Keeps latest)", True)
        add_task(c3, "old_opera", "Old Opera Versions (Keeps latest)", True)
        add_task(c3, "mendeley_inst", "Mendeley Updater Installer File", True)

        # CATEGORY 4: Windows Admin & Advanced System
        c4 = create_category_card("Windows Admin & Advanced Optimizers", "🛡️")
        add_task(c4, "win_update", "Windows Update Cache (SoftwareDistribution)", True, "Admin")
        add_task(c4, "shadow_storage", "Shadow Storage & Old Restore Points (C: & D:)", True, "Admin")
        add_task(c4, "cleanmgr", "Windows Cleanmgr with 13 VolumeCaches keys", True, "Admin")
        add_task(c4, "delivery_opt", "Delivery Optimization P2P Update Cache", True, "Admin")
        add_task(c4, "prefetch", "Windows Prefetch Cache (C:\\Windows\\Prefetch)", True, "Admin")
        add_task(c4, "memory_dumps", "System MEMORY.DMP & LiveKernelReports", True, "Admin")
        add_task(c4, "dns_flush", "Flush Windows DNS Resolver Cache", True)
        add_task(c4, "hibernation", "Disable Hibernation (powercfg -h off, saves 4-8GB)", False, "Admin")

        # CATEGORY 5: Deep Compaction & Advanced
        c5 = create_category_card("Deep Storage & Compaction", "📦")
        add_task(c5, "wsl_compact", "WSL Virtual Disk Compaction (diskpart ext4.vhdx)", False, "WSL Shutdown")
        add_task(c5, "compact_os", "CompactOS System Binaries Compression (~5-10m)", False, "5-10 Mins")
        add_task(c5, "bluestacks", "BlueStacks Complete Removal (Processes & Folders)", False, "DESTRUCTIVE")

    # -----------------------------------------------------------------
    # TAB 2: LARGE FILES FINDER
    # -----------------------------------------------------------------

    def _build_tab_large_files(self):
        tab = self.tab_large

        ctrl = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        ctrl.pack(fill="x", padx=4, pady=(2, 6))

        # Drive selector
        dlbl = ctk.CTkLabel(ctrl, text="Drive:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8")
        dlbl.pack(side="left", padx=(12, 4), pady=8)
        self.large_drive_var = ctk.StringVar(value="Both Drives (C: & D:)")
        self.large_drive_menu = ctk.CTkOptionMenu(
            ctrl,
            values=["Both Drives (C: & D:)", "Drive C: Only", "Drive D: Only"],
            variable=self.large_drive_var,
            fg_color="#1e293b",
            button_color="#334155",
            width=160
        )
        self.large_drive_menu.pack(side="left", padx=4)

        # Min size
        slbl = ctk.CTkLabel(ctrl, text="Min Size:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8")
        slbl.pack(side="left", padx=(10, 4))
        self.large_size_var = ctk.StringVar(value=">= 50 MB")
        self.large_size_menu = ctk.CTkOptionMenu(
            ctrl,
            values=[">= 50 MB", ">= 100 MB", ">= 250 MB", ">= 500 MB", ">= 1 GB"],
            variable=self.large_size_var,
            fg_color="#1e293b",
            button_color="#334155",
            width=110
        )
        self.large_size_menu.pack(side="left", padx=4)

        # Max results
        tlbl = ctk.CTkLabel(ctrl, text="Show:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8")
        tlbl.pack(side="left", padx=(10, 4))
        self.large_limit_var = ctk.StringVar(value="Top 50")
        self.large_limit_menu = ctk.CTkOptionMenu(
            ctrl,
            values=["Top 25", "Top 50", "Top 100"],
            variable=self.large_limit_var,
            fg_color="#1e293b",
            button_color="#334155",
            width=90
        )
        self.large_limit_menu.pack(side="left", padx=4)

        # Scan and Stop Buttons
        self.large_scan_btn = ctk.CTkButton(
            ctrl,
            text="🔍 Start Scan",
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.start_large_files_scan
        )
        self.large_scan_btn.pack(side="left", padx=(14, 4))

        self.large_stop_btn = ctk.CTkButton(
            ctrl,
            text="⏹️ Stop",
            width=65,
            fg_color="#475569",
            hover_color="#64748b",
            state="disabled",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.stop_large_files_scan
        )
        self.large_stop_btn.pack(side="left", padx=(0, 8))

        self.large_status_lbl = ctk.CTkLabel(
            ctrl,
            text="Ready to scan for large files.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        self.large_status_lbl.pack(side="left", padx=8)

        # Table Frame
        tree_frame = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._configure_treeview_styles()

        self.large_tree = ttk.Treeview(
            tree_frame,
            columns=("Drive", "Size", "Name", "Path"),
            show="headings",
            selectmode="browse"
        )
        self.large_tree.heading("Drive", text="Drive")
        self.large_tree.heading("Size", text="Size")
        self.large_tree.heading("Name", text="File Name")
        self.large_tree.heading("Path", text="Full Path")

        self.large_tree.column("Drive", width=60, anchor="center")
        self.large_tree.column("Size", width=110, anchor="center")
        self.large_tree.column("Name", width=250, anchor="w")
        self.large_tree.column("Path", width=580, anchor="w")
        self.large_tree.bind("<Double-1>", lambda e: self.open_large_in_explorer(silent_on_empty=True))

        l_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.large_tree.yview, style="Dark.Vertical.TScrollbar")
        self.large_tree.configure(yscrollcommand=l_scroll.set)
        self.large_tree.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        l_scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)

        # Bottom Actions Bar
        act_bar = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        act_bar.pack(fill="x", padx=4, pady=(4, 6))

        open_btn = ctk.CTkButton(
            act_bar,
            text="📂 Open in Explorer",
            fg_color="#334155",
            hover_color="#475569",
            command=self.open_large_in_explorer
        )
        open_btn.pack(side="left", padx=10, pady=6)

        del_btn = ctk.CTkButton(
            act_bar,
            text="🗑️ Delete Selected File",
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=self.delete_large_file
        )
        del_btn.pack(side="left", padx=6, pady=6)

    # -----------------------------------------------------------------
    # TAB 3: DUPLICATE FILES FINDER
    # -----------------------------------------------------------------

    def _build_tab_duplicates(self):
        tab = self.tab_dupes

        ctrl = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        ctrl.pack(fill="x", padx=4, pady=(2, 6))

        dlbl = ctk.CTkLabel(ctrl, text="Target:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8")
        dlbl.pack(side="left", padx=(12, 4), pady=8)

        self.dupe_target_var = ctk.StringVar(value="Drive D: (Recommended)")
        self.dupe_target_menu = ctk.CTkOptionMenu(
            ctrl,
            values=["Drive D: (Recommended)", "Drive C: Users", "Both Drives (C: & D:)"],
            variable=self.dupe_target_var,
            fg_color="#1e293b",
            button_color="#334155",
            width=180
        )
        self.dupe_target_menu.pack(side="left", padx=4)

        slbl = ctk.CTkLabel(ctrl, text="Min Size:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8")
        slbl.pack(side="left", padx=(10, 4))

        self.dupe_size_var = ctk.StringVar(value=">= 5 MB")
        self.dupe_size_menu = ctk.CTkOptionMenu(
            ctrl,
            values=[">= 1 MB", ">= 5 MB", ">= 10 MB", ">= 50 MB"],
            variable=self.dupe_size_var,
            fg_color="#1e293b",
            button_color="#334155",
            width=100
        )
        self.dupe_size_menu.pack(side="left", padx=4)

        self.dupe_scan_btn = ctk.CTkButton(
            ctrl,
            text="👥 Find Duplicates",
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.start_duplicate_scan
        )
        self.dupe_scan_btn.pack(side="left", padx=(14, 4))

        self.dupe_stop_btn = ctk.CTkButton(
            ctrl,
            text="⏹️ Stop",
            width=65,
            fg_color="#475569",
            hover_color="#64748b",
            state="disabled",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.stop_dupe_scan_action
        )
        self.dupe_stop_btn.pack(side="left", padx=(0, 8))

        self.dupe_status_lbl = ctk.CTkLabel(
            ctrl,
            text="Ready to discover duplicate files.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        self.dupe_status_lbl.pack(side="left", padx=8)

        # Duplicates Table
        tree_frame = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.dupe_tree = ttk.Treeview(
            tree_frame,
            columns=("Group", "Size", "Wasted", "Copies", "File"),
            show="headings",
            selectmode="browse"
        )
        self.dupe_tree.heading("Group", text="Hash ID")
        self.dupe_tree.heading("Size", text="File Size")
        self.dupe_tree.heading("Wasted", text="Wasted Space")
        self.dupe_tree.heading("Copies", text="Copies")
        self.dupe_tree.heading("File", text="File Path")

        self.dupe_tree.column("Group", width=100, anchor="center")
        self.dupe_tree.column("Size", width=100, anchor="center")
        self.dupe_tree.column("Wasted", width=110, anchor="center")
        self.dupe_tree.column("Copies", width=70, anchor="center")
        self.dupe_tree.column("File", width=600, anchor="w")
        self.dupe_tree.bind("<Double-1>", lambda e: self.open_dupe_in_explorer(silent_on_empty=True))

        d_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.dupe_tree.yview, style="Dark.Vertical.TScrollbar")
        self.dupe_tree.configure(yscrollcommand=d_scroll.set)
        self.dupe_tree.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        d_scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)

        # Bottom Actions
        act_bar = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        act_bar.pack(fill="x", padx=4, pady=(4, 6))

        open_dupe_btn = ctk.CTkButton(
            act_bar,
            text="📂 Open in Explorer",
            fg_color="#334155",
            hover_color="#475569",
            command=self.open_dupe_in_explorer
        )
        open_dupe_btn.pack(side="left", padx=10, pady=6)

        del_dupe_btn = ctk.CTkButton(
            act_bar,
            text="🗑️ Delete Selected Duplicate Copy",
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=self.delete_dupe_copy
        )
        del_dupe_btn.pack(side="left", padx=6, pady=6)

    # -----------------------------------------------------------------
    # TAB 4: EMPTY FOLDERS CLEANER
    # -----------------------------------------------------------------

    def _build_tab_empty_folders(self):
        tab = self.tab_empty

        ctrl = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        ctrl.pack(fill="x", padx=4, pady=(2, 6))

        dlbl = ctk.CTkLabel(ctrl, text="Target Drive:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8")
        dlbl.pack(side="left", padx=(12, 4), pady=8)

        self.empty_target_var = ctk.StringVar(value="Drive D: (Entire Drive)")
        self.empty_target_menu = ctk.CTkOptionMenu(
            ctrl,
            values=["Drive D: (Entire Drive)", "Drive C: (User Folders)", "Both Drives"],
            variable=self.empty_target_var,
            fg_color="#1e293b",
            button_color="#334155",
            width=180
        )
        self.empty_target_menu.pack(side="left", padx=4)

        self.empty_scan_btn = ctk.CTkButton(
            ctrl,
            text="🧹 Scan Empty Folders",
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.start_empty_folders_scan
        )
        self.empty_scan_btn.pack(side="left", padx=(14, 4))

        self.empty_stop_btn = ctk.CTkButton(
            ctrl,
            text="⏹️ Stop",
            width=65,
            fg_color="#475569",
            hover_color="#64748b",
            state="disabled",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.stop_empty_scan_action
        )
        self.empty_stop_btn.pack(side="left", padx=(0, 8))

        self.empty_status_lbl = ctk.CTkLabel(
            ctrl,
            text="Ready to scan for orphan empty directories.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        self.empty_status_lbl.pack(side="left", padx=8)

        # Empty Folders Table
        tree_frame = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.empty_tree = ttk.Treeview(
            tree_frame,
            columns=("Folder", "Path"),
            show="headings",
            selectmode="browse"
        )
        self.empty_tree.heading("Folder", text="Folder Name")
        self.empty_tree.heading("Path", text="Full Directory Path")

        self.empty_tree.column("Folder", width=220, anchor="w")
        self.empty_tree.column("Path", width=750, anchor="w")
        self.empty_tree.bind("<Double-1>", lambda e: self.open_empty_in_explorer(silent_on_empty=True))

        e_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.empty_tree.yview, style="Dark.Vertical.TScrollbar")
        self.empty_tree.configure(yscrollcommand=e_scroll.set)
        self.empty_tree.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        e_scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)

        # Bottom Actions
        act_bar = ctk.CTkFrame(tab, fg_color="#131d31", corner_radius=10)
        act_bar.pack(fill="x", padx=4, pady=(4, 6))

        open_empty_btn = ctk.CTkButton(
            act_bar,
            text="📂 Open in Explorer",
            fg_color="#334155",
            hover_color="#475569",
            command=self.open_empty_in_explorer
        )
        open_empty_btn.pack(side="left", padx=10, pady=6)

        self.clean_all_empty_btn = ctk.CTkButton(
            act_bar,
            text="🧹 Clean All Listed Empty Folders",
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.clean_all_empty_folders
        )
        self.clean_all_empty_btn.pack(side="left", padx=6, pady=6)

    def _configure_treeview_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#090d16",
            foreground="#f8fafc",
            rowheight=26,
            fieldbackground="#090d16",
            bordercolor="#1e293b",
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#1e293b",
            foreground="#38bdf8",
            font=("Segoe UI", 10, "bold"),
            relief="flat"
        )
        style.map("Treeview", foreground=[("selected", "#ffffff")], background=[("selected", "#0284c7")])
        style.configure(
            "Dark.Vertical.TScrollbar",
            background="#1e293b",
            troughcolor="#090d16",
            bordercolor="#131d31",
            arrowcolor="#38bdf8",
            relief="flat"
        )
        style.map(
            "Dark.Vertical.TScrollbar",
            background=[("active", "#334155"), ("disabled", "#0f172a")]
        )

    # -----------------------------------------------------------------
    # TELEMETRY REFRESH
    # -----------------------------------------------------------------

    def refresh_all_disk_stats(self):
        """Updates C: and D: drive telemetry in header (standard used-capacity meter)"""
        stats_map = get_all_drives_stats(["C:\\", "D:\\"])

        if "C:" in stats_map:
            c = stats_map["C:"]
            self.c_label.configure(text=f"Drive C: {c['free_gb']} GB Free ({c['used_percent']}% Used)")
            used_ratio = max(0.0, min(1.0, c["used_bytes"] / c["total_bytes"])) if c["total_bytes"] > 0 else 0
            self.c_progress.set(used_ratio)
            self.c_progress.configure(progress_color="#ef4444" if c["used_percent"] >= 88 else "#10b981")

        if "D:" in stats_map:
            d = stats_map["D:"]
            self.d_label.configure(text=f"Drive D: {d['free_gb']} GB Free ({d['used_percent']}% Used)")
            used_ratio = max(0.0, min(1.0, d["used_bytes"] / d["total_bytes"])) if d["total_bytes"] > 0 else 0
            self.d_progress.set(used_ratio)
            self.d_progress.configure(progress_color="#ef4444" if d["used_percent"] >= 88 else "#0284c7")

        return stats_map

    # -----------------------------------------------------------------
    # ELEVATION REQUEST
    # -----------------------------------------------------------------

    def request_elevation(self):
        """Relaunches application with UAC Administrator rights"""
        try:
            import ctypes
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            launcher = os.path.join(base_dir, "launcher.pyw")
            
            # Prefer pythonw.exe to prevent flashing console
            py_dir = os.path.dirname(sys.executable)
            pythonw = os.path.join(py_dir, "pythonw.exe")
            python_exe = pythonw if os.path.exists(pythonw) else sys.executable

            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", python_exe, f'"{launcher}"', base_dir, 1)
            # Only exit if elevation was granted (ShellExecuteW returns > 32 on success)
            if ret > 32:
                self.destroy()
            else:
                self._enqueue_log("UAC elevation request was declined.", "warning")
        except Exception as ex:
            messagebox.showerror("Elevation Error", f"Could not request administrator elevation:\n{ex}")

    # -----------------------------------------------------------------
    # PRESET SELECTIONS
    # -----------------------------------------------------------------

    def apply_preset(self, choice: str):
        if choice == "Safe Fast Clean":
            self.scope_var.set("All Drives (C: & D:)")
            safe_keys = {
                "user_temp", "win_temp", "wer_reports", "thumb_cache",
                "recent_items", "recycle_bin", "crash_dumps", "font_d3d_icon",
                "drive_d_junk", "drive_d_pycache", "chrome_cache", "edge_cache",
                "pip_cache", "dev_superpack", "old_playwright", "old_opera",
                "mendeley_inst", "win_update", "shadow_storage", "cleanmgr",
                "delivery_opt", "prefetch", "memory_dumps", "dns_flush"
            }
            for k, item in self.tasks.items():
                item["var"].set(k in safe_keys)

        elif choice == "Deep System Clean":
            self.scope_var.set("All Drives (C: & D:)")
            deep_keys = {
                "user_temp", "win_temp", "wer_reports", "thumb_cache",
                "recent_items", "recycle_bin", "crash_dumps", "font_d3d_icon",
                "drive_d_junk", "drive_d_pycache", "chrome_cache", "edge_cache",
                "pip_cache", "dev_superpack", "old_playwright",
                "old_opera", "mendeley_inst", "win_update", "shadow_storage",
                "cleanmgr", "delivery_opt", "prefetch", "memory_dumps", "dns_flush",
                "hibernation", "wsl_compact", "compact_os"
            }
            for k, item in self.tasks.items():
                item["var"].set(k in deep_keys)

        elif choice == "Drive D: Clean":
            d_keys = {"recycle_bin", "drive_d_junk", "drive_d_pycache", "shadow_storage"}
            for k, item in self.tasks.items():
                item["var"].set(k in d_keys)
            self.scope_var.set("Drive D: Only")

        elif choice == "Developer Clean":
            self.scope_var.set("All Drives (C: & D:)")
            dev_keys = {"pip_cache", "dev_superpack", "drive_d_pycache", "old_playwright"}
            for k, item in self.tasks.items():
                item["var"].set(k in dev_keys)

        elif choice == "Select All":
            self.scope_var.set("All Drives (C: & D:)")
            for item in self.tasks.values():
                item["var"].set(True)

        elif choice == "Clear All":
            for item in self.tasks.values():
                item["var"].set(False)

    # -----------------------------------------------------------------
    # LOGGING & QUEUE
    # -----------------------------------------------------------------

    def _enqueue_log(self, message: str, level: str = "info"):
        self.log_queue.put((message, level))

    def _process_log_queue(self):
        try:
            while not self.log_queue.empty():
                message, level = self.log_queue.get_nowait()
                timestamp = time.strftime("[%H:%M:%S] ")
                self.console.insert("end", timestamp, "info")
                self.console.insert("end", message + "\n", level)
                self.console.see("end")
        except Exception:
            pass
        if not getattr(self, "_is_destroyed", False):
            try:
                self._log_after_id = self.after(50, self._process_log_queue)
            except Exception:
                pass

    def on_close(self):
        if self.is_running or self.is_large_scanning or self.is_duplicate_scanning or self.is_empty_scanning:
            confirm = messagebox.askyesno(
                "Exit Confirmation",
                "An optimization or scanning operation is currently running.\n\nAre you sure you want to stop operations and exit?",
                icon="warning"
            )
            if not confirm:
                return
            self.engine.stop()
            self.stop_large_scan = True
            self.stop_dupe_scan = True
            self.stop_empty_scan = True
        self.destroy()

    def destroy(self):
        self._is_destroyed = True
        if hasattr(self, "_log_after_id"):
            try:
                self.after_cancel(self._log_after_id)
            except Exception:
                pass
        super().destroy()

    def clear_logs(self):
        self.console.delete("1.0", "end")

    # -----------------------------------------------------------------
    # 1-CLICK CLEANUP PIPELINE EXECUTION
    # -----------------------------------------------------------------

    def start_cleanup(self):
        if self.is_running:
            return

        selected_keys = [k for k, item in self.tasks.items() if item["var"].get()]
        if not selected_keys:
            messagebox.showwarning("No Tasks Selected", "Please select at least one cleanup task to run.")
            return

        # Destructive BlueStacks warning
        if "bluestacks" in selected_keys:
            confirm = messagebox.askyesno(
                "Warning: BlueStacks Cleanup",
                "You have selected 'BlueStacks Complete Removal'.\n"
                "This will terminate all BlueStacks processes and permanently delete all BlueStacks data!\n\n"
                "Do you want to proceed with BlueStacks removal?",
                icon="warning"
            )
            if not confirm:
                self.tasks["bluestacks"]["var"].set(False)
                selected_keys.remove("bluestacks")
                if not selected_keys:
                    return

        # Smart Browser Detection Check
        check_browsers = []
        if "chrome_cache" in selected_keys or "chrome_history" in selected_keys:
            check_browsers.append("chrome")
        if "edge_cache" in selected_keys:
            check_browsers.append("msedge")

        if check_browsers:
            running = [b for b in check_browsers if is_process_running([b])]
            if running:
                b_names = " & ".join(["Google Chrome" if b == "chrome" else "Microsoft Edge" for b in running])
                resp = messagebox.askyesnocancel(
                    "Browsers Running",
                    f"{b_names} is currently open.\n\n"
                    f"• Click [Yes] to close {b_names} and clean caches thoroughly.\n"
                    f"• Click [No] to keep browsers open and skip browser caches.\n"
                    f"• Click [Cancel] to abort.",
                    icon="question"
                )
                if resp is None:
                    return
                elif resp is True:
                    stop_processes(running, self._enqueue_log)
                else:
                    for k in ["chrome_cache", "chrome_history", "edge_cache"]:
                        if k in selected_keys:
                            selected_keys.remove(k)
                    self._enqueue_log("Browser caches skipped at user request.", "warning")

        # Set UI running state
        self.is_running = True
        self.engine.reset()
        self.clean_btn.configure(state="disabled", text="⏳ Cleaning...")
        self.clean_stop_btn.configure(state="normal", fg_color="#7f1d1d", hover_color="#991b1b")
        self.status_text.configure(text="Executing optimization tasks...")
        self.progress_bar.set(0.02)
        self.cleaned_bytes_total = 0

        # Snapshot initial free bytes
        self.initial_free_map = get_all_drives_stats(["C:\\", "D:\\"])

        scope = self.scope_var.get()
        self._enqueue_log("==================================================", "bold")
        self._enqueue_log(f"=== DISK OPTIMIZER PRO V2 CLEANUP PIPELINE ({scope}) ===", "step")
        self._enqueue_log("==================================================", "bold")

        threading.Thread(target=self._run_cleanup_thread, args=(selected_keys, scope), daemon=True).start()

    def _run_cleanup_thread(self, selected_keys: list, scope: str):
        total_tasks = len(selected_keys)
        completed_tasks = 0

        # Filter target drives based on scope
        drives = ["C:", "D:"] if "All" in scope else (["C:"] if "C:" in scope else ["D:"])

        task_dispatch = {
            "user_temp": self.engine.clean_user_temp if "C:" in drives else None,
            "win_temp": self.engine.clean_windows_temp if "C:" in drives else None,
            "wer_reports": self.engine.clean_error_reports if "C:" in drives else None,
            "thumb_cache": self.engine.clean_thumbnail_cache if "C:" in drives else None,
            "recent_items": self.engine.clean_recent_items if "C:" in drives else None,
            "recycle_bin": lambda: self.engine.clean_recycle_bin(drives),
            "crash_dumps": self.engine.clean_crash_dumps if "C:" in drives else None,
            "font_d3d_icon": self.engine.clean_font_d3ds_icon_cache if "C:" in drives else None,
            "drive_d_junk": self.engine.clean_drive_d_root_junk if "D:" in drives else None,
            "drive_d_pycache": self.engine.clean_drive_d_python_caches if "D:" in drives else None,
            "chrome_cache": self.engine.clean_chrome_caches if "C:" in drives else None,
            "edge_cache": self.engine.clean_edge_caches if "C:" in drives else None,
            "pip_cache": self.engine.clean_pip_cache if "C:" in drives else None,
            "dev_superpack": (lambda: self.engine.clean_developer_caches(drives)) if any(d in drives for d in ["C:", "D:"]) else None,
            "chrome_history": self.engine.clean_bloated_chrome_history if "C:" in drives else None,
            "old_playwright": self.engine.clean_old_playwright_versions if "C:" in drives else None,
            "old_opera": self.engine.clean_old_opera_versions if "C:" in drives else None,
            "mendeley_inst": self.engine.clean_mendeley_installer if "C:" in drives else None,
            "bluestacks": self.engine.clean_bluestacks if "C:" in drives else None,
            "win_update": self.engine.run_windows_update if "C:" in drives else None,
            "shadow_storage": lambda: self.engine.run_shadow_storage_all() if "All" in scope else self.engine.run_shadow_storage(drives[0]),
            "cleanmgr": self.engine.run_cleanmgr if "C:" in drives else None,
            "delivery_opt": self.engine.run_delivery_optimization if "C:" in drives else None,
            "prefetch": self.engine.run_prefetch if "C:" in drives else None,
            "memory_dumps": self.engine.run_memory_dumps if "C:" in drives else None,
            "dns_flush": self.engine.run_flush_dns,
            "hibernation": self.engine.run_disable_hibernation if "C:" in drives else None,
            "wsl_compact": self.engine.run_wsl_compact,
            "compact_os": self.engine.run_compact_os if "C:" in drives else None,
        }

        for key in selected_keys:
            if self.engine.should_stop:
                self._enqueue_log("Cleanup pipeline cancelled by user.", "warning")
                break
            func = task_dispatch.get(key)
            if func:
                try:
                    freed = func() or 0
                    self.cleaned_bytes_total += freed
                except Exception as ex:
                    self._enqueue_log(f"Error executing {key}: {ex}", "error")
            else:
                task_label = self.tasks.get(key, {}).get("label", key)
                self._enqueue_log(f"[SKIPPED] {task_label} (Target scope: {scope})", "info")

            completed_tasks += 1
            ratio = completed_tasks / float(total_tasks)
            self.after(0, self._update_progress_ui, ratio, completed_tasks, total_tasks)

        self.after(0, self._cleanup_completed)

    def _update_progress_ui(self, ratio: float, completed: int, total: int):
        self.progress_bar.set(ratio)
        self.status_text.configure(text=f"Completed {completed} of {total} tasks...")
        mb = round(self.cleaned_bytes_total / (1024 * 1024), 1)
        if mb >= 1024:
            self.recovered_label.configure(text=f"Freed: {round(mb/1024, 2)} GB")
        else:
            self.recovered_label.configure(text=f"Freed: {mb} MB")

    def stop_cleanup_action(self):
        if self.is_running:
            self.engine.stop()
            self.clean_stop_btn.configure(state="disabled", text="Stopping...")
            self.status_text.configure(text="Cancelling cleanup operations...")
            self._enqueue_log("Cancellation requested. Stopping after current task finishes...", "warning")

    def _cleanup_completed(self):
        self.is_running = False
        self.clean_btn.configure(state="normal", text="🚀 1-CLICK CLEAN ALL")
        self.clean_stop_btn.configure(state="disabled", text="⏹️ Stop", fg_color="#475569", hover_color="#64748b")
        self.progress_bar.set(1.0)

        # Refresh telemetry
        final_stats = self.refresh_all_disk_stats()

        total_diff_gb = 0
        diff_msgs = []
        for d in ["C:", "D:"]:
            if d in final_stats and d in self.initial_free_map:
                diff = final_stats[d]["free_bytes"] - self.initial_free_map[d]["free_bytes"]
                diff_gb = round(diff / (1024 ** 3), 2)
                if diff_gb > 0:
                    total_diff_gb += diff_gb
                    diff_msgs.append(f"{d} (+{diff_gb} GB)")

        self._enqueue_log("==================================================", "bold")
        self._enqueue_log("=== DISK OPTIMIZER V2 RUN COMPLETED SUCCESSFULLY ===", "success")
        if total_diff_gb > 0:
            msg_str = ", ".join(diff_msgs)
            self._enqueue_log(f"Total Disk Space Recovered: +{round(total_diff_gb, 2)} GB across {msg_str}!", "success")
            self.recovered_label.configure(text=f"Freed: +{round(total_diff_gb, 2)} GB")
        else:
            mb = round(self.cleaned_bytes_total / (1024 * 1024), 1)
            self._enqueue_log(f"Total Scoured: {mb} MB cleared.", "info")
            self.recovered_label.configure(text=f"Freed: {mb} MB")
        self._enqueue_log("==================================================", "bold")

        self.status_text.configure(text="Optimization completed successfully!")
        messagebox.showinfo(
            "Optimization Complete",
            f"Optimization finished successfully!\n\n"
            f"Drive C: {final_stats.get('C:', {}).get('free_gb', 0)} GB Free\n"
            f"Drive D: {final_stats.get('D:', {}).get('free_gb', 0)} GB Free\n\n"
            f"Recovered Space: +{round(total_diff_gb, 2)} GB" if total_diff_gb > 0 else "System caches cleared!"
        )

    # -----------------------------------------------------------------
    # TAB 2: LARGE FILES SCANNER ACTIONS
    # -----------------------------------------------------------------

    def start_large_files_scan(self):
        if self.is_large_scanning:
            return
        self.is_large_scanning = True
        self.stop_large_scan = False
        self.large_scan_btn.configure(state="disabled", text="Scanning...")
        self.large_stop_btn.configure(state="normal", fg_color="#7f1d1d", hover_color="#991b1b")
        for row in self.large_tree.get_children():
            self.large_tree.delete(row)

        target = self.large_drive_var.get()
        roots = ["C:\\", "D:\\"] if "Both" in target else (["C:\\"] if "C:" in target else ["D:\\"])

        size_text = self.large_size_var.get()
        min_mb = float(size_text.replace(">=", "").replace("MB", "").replace("GB", "").strip())
        if "GB" in size_text:
            min_mb *= 1024

        top_limit = int(self.large_limit_var.get().replace("Top", "").strip())

        self.large_status_lbl.configure(text=f"Scanning {', '.join(roots)} for files >= {int(min_mb)} MB...")

        threading.Thread(
            target=self._run_large_scan_thread,
            args=(roots, min_mb, top_limit),
            daemon=True
        ).start()

    def stop_large_files_scan(self):
        self.stop_large_scan = True
        self.large_status_lbl.configure(text="Cancelling scan...")
        self.large_stop_btn.configure(state="disabled")

    def _run_large_scan_thread(self, roots, min_mb, top_limit):
        try:
            results = scan_large_files_multi(
                roots,
                min_size_mb=min_mb,
                top_n=top_limit,
                stop_check=lambda: self.stop_large_scan
            )
            self.after(0, self._large_scan_completed, results)
        except Exception as ex:
            self.after(0, self._large_scan_error, str(ex))

    def _large_scan_completed(self, results):
        self.is_large_scanning = False
        self.large_scan_btn.configure(state="normal", text="🔍 Start Scan")
        self.large_stop_btn.configure(state="disabled", fg_color="#475569", hover_color="#64748b")
        self.large_status_lbl.configure(text=f"Found {len(results)} large files.")
        for item in results:
            sz_str = f"{item['size_gb']} GB" if item['size_gb'] >= 1.0 else f"{item['size_mb']} MB"
            self.large_tree.insert("", "end", values=(item["drive"], sz_str, item["name"], item["path"]))

    def _large_scan_error(self, err):
        self.is_large_scanning = False
        self.large_scan_btn.configure(state="normal", text="🔍 Start Scan")
        self.large_stop_btn.configure(state="disabled", fg_color="#475569", hover_color="#64748b")
        self.large_status_lbl.configure(text=f"Error: {err}")

    def open_large_in_explorer(self, silent_on_empty: bool = False):
        selected = self.large_tree.selection()
        if not selected:
            if not silent_on_empty:
                messagebox.showinfo("Select File", "Please select a file first.")
            return
        fp = self.large_tree.item(selected[0])["values"][3]
        if os.path.exists(fp):
            subprocess.Popen(["explorer", f"/select,{fp}"])

    def delete_large_file(self):
        selected = self.large_tree.selection()
        if not selected:
            messagebox.showinfo("Select File", "Please select a file to delete.")
            return
        vals = self.large_tree.item(selected[0])["values"]
        name = vals[2]
        fp = vals[3]
        sz = vals[1]

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete:\n\n{name} ({sz})\n\nPath: {fp}",
            icon="warning"
        )
        if confirm:
            try:
                try:
                    os.chmod(fp, 0o777)
                except Exception:
                    pass
                os.remove(fp)
                self.large_tree.delete(selected[0])
                messagebox.showinfo("Deleted", f"Successfully deleted {name}.")
                self.refresh_all_disk_stats()
            except Exception as ex:
                messagebox.showerror("Delete Error", f"Could not delete file:\n{ex}")

    # -----------------------------------------------------------------
    # TAB 3: DUPLICATE FINDER ACTIONS
    # -----------------------------------------------------------------

    def start_duplicate_scan(self):
        if self.is_duplicate_scanning:
            return
        self.is_duplicate_scanning = True
        self.stop_dupe_scan = False
        self.dupe_scan_btn.configure(state="disabled", text="Scanning...")
        self.dupe_stop_btn.configure(state="normal", fg_color="#7f1d1d", hover_color="#991b1b")
        for row in self.dupe_tree.get_children():
            self.dupe_tree.delete(row)

        target = self.dupe_target_var.get()
        if "D:" in target:
            roots = ["D:\\"]
        elif "C:" in target:
            roots = [os.path.expanduser("~")]
        else:
            roots = ["D:\\", os.path.expanduser("~")]

        size_text = self.dupe_size_var.get()
        min_mb = float(size_text.replace(">=", "").replace("MB", "").strip())
        min_bytes = int(min_mb * 1024 * 1024)

        self.dupe_status_lbl.configure(text=f"Scanning for duplicates in {', '.join(roots)}...")

        threading.Thread(
            target=self._run_dupe_scan_thread,
            args=(roots, min_bytes),
            daemon=True
        ).start()

    def stop_dupe_scan_action(self):
        self.stop_dupe_scan = True
        self.dupe_status_lbl.configure(text="Cancelling scan...")
        self.dupe_stop_btn.configure(state="disabled")

    def _run_dupe_scan_thread(self, roots, min_bytes):
        try:
            results = find_duplicate_files(
                roots,
                min_size_bytes=min_bytes,
                stop_check=lambda: self.stop_dupe_scan
            )
            self.after(0, self._dupe_scan_completed, results)
        except Exception as ex:
            self.after(0, self._dupe_scan_error, str(ex))

    def _dupe_scan_completed(self, results):
        self.is_duplicate_scanning = False
        self.dupe_scan_btn.configure(state="normal", text="👥 Find Duplicates")
        self.dupe_stop_btn.configure(state="disabled", fg_color="#475569", hover_color="#64748b")
        total_wasted = round(sum(r["wasted_mb"] for r in results), 1)
        wasted_str = f"{round(total_wasted/1024, 2)} GB" if total_wasted >= 1024 else f"{total_wasted} MB"
        self.dupe_status_lbl.configure(text=f"Found {len(results)} duplicate sets (~{wasted_str} recoverable).")

        for group in results:
            sz_str = f"{round(group['size_mb']/1024, 2)} GB" if group['size_mb'] >= 1024 else f"{group['size_mb']} MB"
            w_str = f"{group['wasted_gb']} GB" if group['wasted_gb'] >= 1.0 else f"{group['wasted_mb']} MB"
            for p in group["files"]:
                self.dupe_tree.insert("", "end", values=(group["hash"], sz_str, w_str, group["count"], p))

    def _dupe_scan_error(self, err):
        self.is_duplicate_scanning = False
        self.dupe_scan_btn.configure(state="normal", text="👥 Find Duplicates")
        self.dupe_stop_btn.configure(state="disabled", fg_color="#475569", hover_color="#64748b")
        self.dupe_status_lbl.configure(text=f"Error: {err}")

    def open_dupe_in_explorer(self, silent_on_empty: bool = False):
        selected = self.dupe_tree.selection()
        if not selected:
            if not silent_on_empty:
                messagebox.showinfo("Select File", "Please select a duplicate file first.")
            return
        fp = self.dupe_tree.item(selected[0])["values"][4]
        if os.path.exists(fp):
            subprocess.Popen(["explorer", f"/select,{fp}"])

    def delete_dupe_copy(self):
        selected = self.dupe_tree.selection()
        if not selected:
            messagebox.showinfo("Select File", "Please select a duplicate copy to delete.")
            return
        vals = self.dupe_tree.item(selected[0])["values"]
        gid = vals[0]
        fp = vals[4]

        same_hash_items = [item for item in self.dupe_tree.get_children() if self.dupe_tree.item(item)["values"][0] == gid]
        same_hash_count = len(same_hash_items)
        if same_hash_count <= 1:
            confirm = messagebox.askyesno(
                "Last Copy Warning",
                f"This is the ONLY remaining copy shown for this file!\nDeleting it will remove the file entirely.\n\nProceed?",
                icon="warning"
            )
            if not confirm:
                return

        confirm = messagebox.askyesno("Confirm Delete", f"Delete duplicate copy:\n\n{fp}?", icon="question")
        if confirm:
            try:
                try:
                    os.chmod(fp, 0o777)
                except Exception:
                    pass
                os.remove(fp)
                self.dupe_tree.delete(selected[0])

                # Dynamically update remaining copies in the group
                remaining_items = [item for item in self.dupe_tree.get_children() if self.dupe_tree.item(item)["values"][0] == gid]
                new_count = len(remaining_items)
                for item in remaining_items:
                    curr_vals = list(self.dupe_tree.item(item)["values"])
                    curr_vals[3] = new_count
                    if new_count <= 1:
                        curr_vals[2] = "0.0 MB"
                    self.dupe_tree.item(item, values=curr_vals)

                messagebox.showinfo("Deleted", "Duplicate copy removed successfully.")
                self.refresh_all_disk_stats()
            except Exception as ex:
                messagebox.showerror("Error", f"Could not delete duplicate:\n{ex}")

    # -----------------------------------------------------------------
    # TAB 4: EMPTY FOLDERS ACTIONS
    # -----------------------------------------------------------------

    def start_empty_folders_scan(self):
        if self.is_empty_scanning:
            return
        self.is_empty_scanning = True
        self.stop_empty_scan = False
        self.empty_scan_btn.configure(state="disabled", text="Scanning...")
        self.empty_stop_btn.configure(state="normal", fg_color="#7f1d1d", hover_color="#991b1b")
        for row in self.empty_tree.get_children():
            self.empty_tree.delete(row)

        target = self.empty_target_var.get()
        if "D:" in target:
            roots = ["D:\\"]
        elif "C:" in target:
            roots = [os.path.expanduser("~")]
        else:
            roots = ["D:\\", os.path.expanduser("~")]

        self.empty_status_lbl.configure(text=f"Scanning {', '.join(roots)} for empty folders...")

        threading.Thread(target=self._run_empty_scan_thread, args=(roots,), daemon=True).start()

    def stop_empty_scan_action(self):
        self.stop_empty_scan = True
        self.empty_status_lbl.configure(text="Cancelling scan...")
        self.empty_stop_btn.configure(state="disabled")

    def _run_empty_scan_thread(self, roots):
        try:
            results = scan_empty_directories(
                roots,
                stop_check=lambda: self.stop_empty_scan
            )
            self.after(0, self._empty_scan_completed, results)
        except Exception as ex:
            self.after(0, self._empty_scan_error, str(ex))

    def _empty_scan_completed(self, results):
        self.is_empty_scanning = False
        self.empty_scan_btn.configure(state="normal", text="🧹 Scan Empty Folders")
        self.empty_stop_btn.configure(state="disabled", fg_color="#475569", hover_color="#64748b")
        self.empty_status_lbl.configure(text=f"Found {len(results)} empty folders.")
        for p in results:
            self.empty_tree.insert("", "end", values=(os.path.basename(p), p))

    def _empty_scan_error(self, err):
        self.is_empty_scanning = False
        self.empty_scan_btn.configure(state="normal", text="🧹 Scan Empty Folders")
        self.empty_stop_btn.configure(state="disabled", fg_color="#475569", hover_color="#64748b")
        self.empty_status_lbl.configure(text=f"Error: {err}")

    def open_empty_in_explorer(self, silent_on_empty: bool = False):
        selected = self.empty_tree.selection()
        if not selected:
            if not silent_on_empty:
                messagebox.showinfo("Select Folder", "Please select a folder first.")
            return
        p = self.empty_tree.item(selected[0])["values"][1]
        if os.path.exists(p):
            subprocess.Popen(["explorer", p])

    def clean_all_empty_folders(self):
        rows = self.empty_tree.get_children()
        if not rows:
            messagebox.showinfo("No Folders", "No empty folders listed to clean.")
            return

        paths = [self.empty_tree.item(r)["values"][1] for r in rows]
        confirm = messagebox.askyesno(
            "Confirm Cleanup",
            f"Are you sure you want to clean and remove {len(paths)} empty directories?",
            icon="question"
        )
        if confirm:
            self.clean_all_empty_btn.configure(state="disabled", text="Cleaning...")
            self.empty_status_lbl.configure(text=f"Cleaning {len(paths)} empty folders in background...")
            threading.Thread(
                target=self._run_delete_empty_folders_thread,
                args=(paths, rows),
                daemon=True
            ).start()

    def _run_delete_empty_folders_thread(self, paths, rows):
        succ, fail = delete_empty_directories(paths)
        self.after(0, self._delete_empty_folders_completed, succ, fail, rows)

    def _delete_empty_folders_completed(self, succ, fail, rows):
        self.clean_all_empty_btn.configure(state="normal", text="🧹 Clean All Listed Empty Folders")
        for r in rows:
            try:
                self.empty_tree.delete(r)
            except Exception:
                pass
        self.empty_status_lbl.configure(text=f"Cleaned {succ} empty folders ({fail} locked/skipped).")
        messagebox.showinfo("Clean Complete", f"Successfully cleaned {succ} empty folders ({fail} locked/skipped).")


def main():
    app = DiskOptimizerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
