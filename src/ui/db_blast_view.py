import asyncio
import os
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Set

import customtkinter as ctk

from theme import COLORS
from icons import get_icon
from db_executor import (
    export_connections_to_file,
    import_connections_from_file,
    run_db_query,
)
from ui.bulk_db_dialog import BulkDbDialog
from ui.db_dialog import DBConnectionDialog

DEFAULT_SQL = """-- DO.MBA DB Blast - SQL Query Editor
-- Tulis query SQL di sini (contoh: SELECT, SHOW, UPDATE, etc.)
-- Gunakan tombol '⚡ Run Blast' untuk mengeksekusi ke seluruh database yang dipilih.

SELECT VERSION();
"""


class DBBlastView(ctk.CTkFrame):
    """Tampilan DB Blast dengan antarmuka bergaya Navicat:
    - Sisi Kiri: Panel Koneksi Database Navicat (Treeview berkecepatan tinggi <10ms, Pencarian instan, Filter Grup, Check All, Tambah, Import/Export, Aksi Cepat)
    - Sisi Kanan: SQL Query Editor & Tab Hasil (Log Eksekusi & Tabel Hasil Query)
    - Dioptimalkan penuh sehingga muat secara instan (<80ms) bahkan untuk ratusan koneksi.
    """

    def __init__(self, parent: ctk.CTk, db_manager: Any, on_data_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.parent = parent
        self.db = db_manager
        self._on_data_changed = on_data_changed

        self.selected_db_ids: Set[int] = set()
        self.query_results_cache: Dict[str, Dict[str, Any]] = {}
        self.is_running_blast = False
        self.search_debounce_id = None
        self._all_connections: List[Dict[str, Any]] = []
        self._current_filtered_conns: List[Dict[str, Any]] = []
        self._needs_refresh = False
        self._is_loaded = False

        # Auto-seed dari connections.ncx / db_connections.js jika database lokal masih kosong
        self._check_initial_seed()

        self._setup_ui()
        self._refresh_connections()

    def mark_needs_refresh(self):
        """Tandai bahwa data telah berubah; langsung refresh jika view sedang aktif terlihat."""
        if self.winfo_ismapped():
            self._refresh_connections()
        else:
            self._needs_refresh = True

    def _check_initial_seed(self):
        """Jika db_connections belum ada data, muat otomatis dari connections.ncx / db_connections.js."""
        try:
            existing = self.db.get_all_db_connections(decrypt_passwords=False)
            if not existing:
                from pathlib import Path
                search_dirs = [
                    Path.cwd(),
                    Path(__file__).resolve().parent.parent,
                    Path(__file__).resolve().parent.parent.parent
                ]
                candidates = ["connections.ncx", "db_connections.js", "db_connections.json"]
                for base in search_dirs:
                    for fname in candidates:
                        target = base / fname
                        if target.exists():
                            conns = import_connections_from_file(str(target))
                            if conns:
                                self.db.bulk_import_db_connections(conns)
                                return
        except Exception as e:
            print(f"Initial seed notice: {e}")

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=4, minsize=420)
        self.grid_columnconfigure(1, weight=5, minsize=480)
        self.grid_rowconfigure(0, weight=1)

        # =========================================================================
        # PANEL KIRI: DAFTAR KONEKSI DATABASE (NAVICAT CONNECTION EXPLORER)
        # =========================================================================
        self.left_panel = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=12, border_width=1, border_color=COLORS["line"])
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=0)
        self.left_panel.grid_rowconfigure(2, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)

        # 1. Header Panel Kiri
        left_header = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        left_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 10))
        left_header.grid_columnconfigure(0, weight=1)

        self.lbl_db_title = ctk.CTkLabel(
            left_header,
            text="Databases",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.lbl_db_title.grid(row=0, column=0, sticky="w")

        btn_header_group = ctk.CTkFrame(left_header, fg_color="transparent")
        btn_header_group.grid(row=0, column=1, sticky="e")

        btn_new = ctk.CTkButton(
            btn_header_group,
            text=" New",
            image=get_icon("plus", (14, 14), "#FFFFFF"),
            compound="left",
            width=68, height=30, corner_radius=7,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_new_db_dialog
        )
        btn_new.pack(side="left", padx=(0, 5))

        btn_import = ctk.CTkButton(
            btn_header_group,
            text=" Import",
            image=get_icon("download", (13, 13), COLORS["text"]),
            compound="left",
            width=78, height=30, corner_radius=7,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=12),
            command=self._import_db_connections
        )
        btn_import.pack(side="left", padx=(0, 5))

        btn_export = ctk.CTkButton(
            btn_header_group,
            text=" Export",
            image=get_icon("upload", (13, 13), COLORS["text"]),
            compound="left",
            width=78, height=30, corner_radius=7,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=12),
            command=self._export_db_connections
        )
        btn_export.pack(side="left", padx=(0, 5))

        btn_refresh = ctk.CTkButton(
            btn_header_group,
            text="",
            image=get_icon("refresh-cw", (14, 14), COLORS["text"]),
            width=34, height=30, corner_radius=7,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            border_width=1, border_color=COLORS["line"],
            command=self._refresh_connections
        )
        btn_refresh.pack(side="left")

        # 2. Filter & Search Bar
        filter_bar = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        filter_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        filter_bar.grid_columnconfigure(0, weight=1)

        # Search Box
        search_box = ctk.CTkFrame(filter_bar, fg_color=COLORS["input_bg"], corner_radius=8, border_width=1, border_color=COLORS["line"])
        search_box.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        search_box.grid_columnconfigure(1, weight=1)

        lbl_icon = ctk.CTkLabel(search_box, text="", image=get_icon("search", (15, 15), COLORS["muted"]))
        lbl_icon.grid(row=0, column=0, padx=(8, 4))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        self.ent_search = ctk.CTkEntry(
            search_box,
            placeholder_text="Cari database / host...",
            textvariable=self.search_var,
            height=32, corner_radius=8, border_width=0,
            fg_color="transparent", text_color=COLORS["text"], placeholder_text_color=COLORS["muted"]
        )
        self.ent_search.grid(row=0, column=1, sticky="ew")

        # Row 2: Group Filter
        ctrl_row = ctk.CTkFrame(filter_bar, fg_color="transparent")
        ctrl_row.grid(row=1, column=0, sticky="ew")
        ctrl_row.grid_columnconfigure(0, weight=1)

        lbl_grp = ctk.CTkLabel(ctrl_row, text="Group Filter:", text_color=COLORS["muted"], font=ctk.CTkFont(size=12))
        lbl_grp.pack(side="left")

        self.opt_group = ctk.CTkOptionMenu(
            ctrl_row,
            values=["All Groups"],
            width=140, height=28,
            corner_radius=6,
            fg_color=COLORS["surface"],
            text_color=COLORS["text"],
            button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"],
            command=lambda _: self._apply_filter()
        )
        self.opt_group.pack(side="right")

        # 3. Navicat Style High-Performance Connection Table Explorer (<10ms load)
        table_container = tk.Frame(self.left_panel, bg=COLORS["input_bg"], highlightthickness=1, highlightbackground=COLORS["line"])
        table_container.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Navicat.Treeview",
            background=COLORS["input_bg"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["input_bg"],
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0
        )
        style.configure(
            "Navicat.Treeview.Heading",
            background=COLORS["surface"],
            foreground=COLORS["muted"],
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            borderwidth=0
        )
        style.map(
            "Navicat.Treeview",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", "#FFFFFF")]
        )

        self.tree = ttk.Treeview(
            table_container,
            columns=("chk", "name", "type", "host", "ssh", "status"),
            show="headings",
            style="Navicat.Treeview",
            selectmode="browse"
        )
        self.tree.heading("chk", text="[✓]", anchor="center", command=self._toggle_check_all)
        self.tree.heading("name", text="Database Name", anchor="w")
        self.tree.heading("type", text="Type", anchor="center")
        self.tree.heading("host", text="Target Host", anchor="w")
        self.tree.heading("ssh", text="SSH Tunnel", anchor="w")
        self.tree.heading("status", text="Status", anchor="center")

        self.tree.column("chk", width=36, anchor="center", stretch=False)
        self.tree.column("name", width=160, anchor="w")
        self.tree.column("type", width=65, anchor="center", stretch=False)
        self.tree.column("host", width=130, anchor="w")
        self.tree.column("ssh", width=120, anchor="w")
        self.tree.column("status", width=85, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Bindings
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)
        self.tree.bind("<space>", self._on_tree_space)
        self.tree.bind("<Button-3>", self._show_tree_context_menu)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select_change)

        # Context Menu
        self._create_tree_context_menu()

        # 4. Bottom Action Toolbar for Selected Connection
        action_bar = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        action_bar.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 10))
        action_bar.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.btn_action_run = ctk.CTkButton(
            action_bar,
            text=" Run Single",
            image=get_icon("play", (13, 13), "#FFFFFF"),
            compound="left",
            height=28, corner_radius=6,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._run_query_on_selected_row
        )
        self.btn_action_run.grid(row=0, column=0, padx=2, sticky="ew")

        self.btn_action_test = ctk.CTkButton(
            action_bar,
            text=" Test",
            image=get_icon("activity", (13, 13), COLORS["accent_text"]),
            compound="left",
            height=28, corner_radius=6,
            fg_color=COLORS["accent_subtle"], hover_color="#263750",
            text_color=COLORS["accent_text"], border_width=1, border_color=COLORS["accent_border"],
            font=ctk.CTkFont(size=11),
            command=self._test_selected_row
        )
        self.btn_action_test.grid(row=0, column=1, padx=2, sticky="ew")

        self.btn_action_edit = ctk.CTkButton(
            action_bar,
            text=" Edit",
            image=get_icon("pencil", (13, 13), COLORS["text_secondary"]),
            compound="left",
            height=28, corner_radius=6,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._edit_selected_row
        )
        self.btn_action_edit.grid(row=0, column=2, padx=2, sticky="ew")

        self.btn_action_del = ctk.CTkButton(
            action_bar,
            text=" Delete",
            image=get_icon("trash", (13, 13), COLORS["danger_text"]),
            compound="left",
            height=28, corner_radius=6,
            fg_color=COLORS["danger_subtle"], border_width=1, border_color=COLORS["danger_border"],
            text_color=COLORS["danger_text"], hover_color=COLORS["danger_hover"],
            font=ctk.CTkFont(size=11),
            command=self._delete_selected_row
        )
        self.btn_action_del.grid(row=0, column=3, padx=2, sticky="ew")

        # Disable action buttons initially
        self._on_tree_select_change()

        # =========================================================================
        # PANEL KANAN: WORKSPACE SQL (EDITOR & HASIL NAVICAT)
        # =========================================================================
        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.right_panel.grid_rowconfigure(1, weight=3)  # Query Editor
        self.right_panel.grid_rowconfigure(2, weight=4)  # Results Tabview
        self.right_panel.grid_columnconfigure(0, weight=1)

        # 1. Query Action Toolbar (2 Baris agar layout stabil & tidak terpotong saat select server)
        toolbar = ctk.CTkFrame(self.right_panel, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.grid_columnconfigure(0, weight=1)

        # Baris 1: Blast Execution Button & Status Target
        row1 = ctk.CTkFrame(toolbar, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 6))

        self.btn_run_blast = ctk.CTkButton(
            row1,
            text=" Run Blast",
            image=get_icon("zap", (14, 14), "#FFFFFF"),
            compound="left",
            width=140,
            height=34,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._run_blast
        )
        self.btn_run_blast.pack(side="left")

        self.lbl_blast_status = ctk.CTkLabel(
            row1,
            text="All databases will run",
            text_color=COLORS["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_blast_status.pack(side="right", padx=4)

        # Divider pemisah antar baris
        divider = ctk.CTkFrame(toolbar, fg_color=COLORS["line"], height=1)
        divider.pack(fill="x", padx=12, pady=3)

        # Baris 2: Editor Title & Utility Buttons (Open, Save, Clear)
        row2 = ctk.CTkFrame(toolbar, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 10))

        lbl_editor_title = ctk.CTkLabel(
            row2,
            text=" Query Editor (SQL)",
            image=get_icon("file-code", (14, 14), COLORS["text"]),
            compound="left",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text"]
        )
        lbl_editor_title.pack(side="left")

        btn_clear_sql = ctk.CTkButton(
            row2,
            text=" Clear",
            image=get_icon("trash", (12, 12), COLORS["muted"]),
            compound="left",
            width=76,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["line"],
            text_color=COLORS["muted"],
            hover_color=COLORS["surface_hover"],
            font=ctk.CTkFont(size=11),
            command=self._clear_sql_editor
        )
        btn_clear_sql.pack(side="right", padx=(6, 0))

        btn_export_sql = ctk.CTkButton(
            row2,
            text=" Save SQL",
            image=get_icon("file-code", (12, 12), COLORS["text_secondary"]),
            compound="left",
            width=92,
            height=28,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._export_sql_file
        )
        btn_export_sql.pack(side="right", padx=(6, 0))

        btn_import_sql = ctk.CTkButton(
            row2,
            text=" Open SQL",
            image=get_icon("folder", (12, 12), COLORS["text_secondary"]),
            compound="left",
            width=92,
            height=28,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._import_sql_file
        )
        btn_import_sql.pack(side="right")

        # 2. SQL Editor Frame
        editor_frame = ctk.CTkFrame(self.right_panel, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        editor_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        editor_frame.grid_rowconfigure(0, weight=1)
        editor_frame.grid_columnconfigure(0, weight=1)

        self.txt_sql = ctk.CTkTextbox(
            editor_frame,
            font=("Consolas", 13),
            wrap="none",
            corner_radius=8,
            border_width=0,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            undo=True
        )
        self.txt_sql.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.txt_sql.insert("1.0", DEFAULT_SQL)

        # 3. Navicat Style Bottom Tab Panel with Lucide Icons (Execution Log & Query Results)
        # 3. Navicat Style Bottom Tab Panel with Lucide Icons (Execution Log & Query Results)
        self.bottom_panel = ctk.CTkFrame(
            self.right_panel,
            corner_radius=10,
            border_width=1,
            border_color=COLORS["line"],
            fg_color=COLORS["surface"]
        )
        self.bottom_panel.grid(row=2, column=0, sticky="nsew", pady=0)
        self.bottom_panel.grid_columnconfigure(0, weight=1)
        self.bottom_panel.grid_rowconfigure(2, weight=1)  # row 2 = content textbox

        # -------------------------------------------------------------
        # BARIS 1: Tab Header Bar (Pill Switcher)
        # -------------------------------------------------------------
        self.tab_header = ctk.CTkFrame(self.bottom_panel, fg_color="transparent")
        self.tab_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        pill_container = ctk.CTkFrame(
            self.tab_header,
            fg_color=COLORS["window"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"],
            height=34
        )
        pill_container.pack(side="left")

        self.btn_tab_log = ctk.CTkButton(
            pill_container,
            text=" Execution Log",
            image=get_icon("file-text", (13, 13), "#FFFFFF"),
            compound="left",
            width=128,
            height=28,
            corner_radius=6,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._set_active_tab("log")
        )
        self.btn_tab_log.pack(side="left", padx=3, pady=3)

        self.btn_tab_result = ctk.CTkButton(
            pill_container,
            text=" Query Results",
            image=get_icon("table", (13, 13), COLORS["text_secondary"]),
            compound="left",
            width=128,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._set_active_tab("results")
        )
        self.btn_tab_result.pack(side="left", padx=(0, 3), pady=3)

        # -------------------------------------------------------------
        # BARIS 2: Dedicated Sub-Toolbar Bar (Tinggi konsisten di kedua tab)
        # -------------------------------------------------------------
        self.sub_toolbar = ctk.CTkFrame(self.bottom_panel, fg_color="transparent", height=32)
        self.sub_toolbar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

        # Sub-toolbar Tab 1: Execution Log
        self.bar_log = ctk.CTkFrame(self.sub_toolbar, fg_color="transparent")
        lbl_log_title = ctk.CTkLabel(
            self.bar_log,
            text="Streaming Console Output",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11)
        )
        lbl_log_title.pack(side="left", padx=(2, 0))

        btn_clear_log = ctk.CTkButton(
            self.bar_log,
            text=" Clear Log",
            image=get_icon("trash", (12, 12), COLORS["muted"]),
            compound="left",
            width=84, height=26, corner_radius=6,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["muted"],
            border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._clear_execution_log
        )
        btn_clear_log.pack(side="right")

        # Sub-toolbar Tab 2: Query Results
        self.bar_result = ctk.CTkFrame(self.sub_toolbar, fg_color="transparent")

        lbl_pick = ctk.CTkLabel(self.bar_result, text="Pilih Database:", text_color=COLORS["text"], font=ctk.CTkFont(size=12))
        lbl_pick.pack(side="left", padx=(0, 8))

        self.opt_result_db = ctk.CTkOptionMenu(
            self.bar_result,
            values=["(No Results Yet)"],
            width=280, height=28,
            corner_radius=6,
            fg_color=COLORS["surface"],
            text_color=COLORS["text"],
            button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"],
            command=self._on_result_db_selected
        )
        self.opt_result_db.pack(side="left")

        btn_copy_res = ctk.CTkButton(
            self.bar_result,
            text=" Copy Result",
            image=get_icon("copy", (12, 12), COLORS["text_secondary"]),
            compound="left",
            width=100, height=28,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._copy_query_result
        )
        btn_copy_res.pack(side="left", padx=(8, 0))

        # -------------------------------------------------------------
        # BARIS 3: Textbox Content (row=2)
        # -------------------------------------------------------------
        self.txt_log = ctk.CTkTextbox(
            self.bottom_panel,
            font=("Consolas", 12),
            wrap="none",
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"],
            fg_color=COLORS["console_bg"],
            text_color=COLORS["console_text"]
        )

        self.txt_result = ctk.CTkTextbox(
            self.bottom_panel,
            font=("Consolas", 12),
            wrap="none",
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"],
            fg_color=COLORS["console_bg"],
            text_color=COLORS["accent_text"]
        )

        # -------------------------------------------------------------
        # BARIS 4: Status Bar Footer (row=3 di bawah Textbox)
        # -------------------------------------------------------------
        self.footer_bar = ctk.CTkFrame(self.bottom_panel, fg_color="transparent", height=20)
        self.footer_bar.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 8))

        self.lbl_result_meta = ctk.CTkLabel(
            self.footer_bar,
            text="",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11, weight="bold")
        )

        # Compatibility wrapper for any self.tabview.set calls
        self.tabview = type("TabviewCompat", (), {"set": lambda _, t: self._set_active_tab(t)})()

        # Set default active tab
        self._set_active_tab("log")

    def _set_active_tab(self, tab_name: str):
        """Beralih antara tab Execution Log dan Query Results secara seamless tanpa pergeseran layout."""
        is_log = tab_name in ("log", "📋 Execution Log", "Execution Log")
        if is_log:
            self.bar_result.pack_forget()
            self.bar_log.pack(fill="x", expand=True)
            self.lbl_result_meta.pack_forget()

            self.txt_result.grid_remove()
            self.txt_log.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 6))

            self.btn_tab_log.configure(
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                text_color="#FFFFFF",
                image=get_icon("file-text", (13, 13), "#FFFFFF")
            )
            self.btn_tab_result.configure(
                fg_color="transparent",
                hover_color=COLORS["surface_hover"],
                text_color=COLORS["text_secondary"],
                image=get_icon("table", (13, 13), COLORS["text_secondary"])
            )
        else:
            self.bar_log.pack_forget()
            self.bar_result.pack(fill="x", expand=True)
            self.lbl_result_meta.pack(side="left")

            self.txt_log.grid_remove()
            self.txt_result.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 6))

            self.btn_tab_result.configure(
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                text_color="#FFFFFF",
                image=get_icon("table", (13, 13), "#FFFFFF")
            )
            self.btn_tab_log.configure(
                fg_color="transparent",
                hover_color=COLORS["surface_hover"],
                text_color=COLORS["text_secondary"],
                image=get_icon("file-text", (13, 13), COLORS["text_secondary"])
            )

    # =========================================================================
    # CONTEXT MENU & SELECTION HANDLING
    # =========================================================================
    def _create_tree_context_menu(self):
        self.context_menu = tk.Menu(
            self,
            tearoff=0,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            activebackground=COLORS["accent"],
            activeforeground="#FFFFFF",
            bd=1
        )

    def _show_tree_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return

        # Jika item yang diklik belum terpilih, pilih item tersebut
        if not self.tree.selection() or item not in self.tree.selection():
            self.tree.selection_set(item)
            self._on_tree_select_change()

        clicked_id = int(item)
        if clicked_id in self.selected_db_ids and len(self.selected_db_ids) > 1:
            target_ids = list(self.selected_db_ids)
            label_suffix = f" ({len(target_ids)} checked)"
        else:
            target_ids = [clicked_id]
            label_suffix = ""

        # Rebuild context menu dinamis
        self.context_menu.delete(0, "end")
        self.context_menu.add_command(label="⚡ Run Query on This DB", command=self._run_query_on_selected_row)
        self.context_menu.add_command(label="🧪 Test Connection", command=self._test_selected_row)
        self.context_menu.add_separator()

        # Submenu: Move to Group
        group_menu = tk.Menu(
            self.context_menu,
            tearoff=0,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            activebackground=COLORS["accent"],
            activeforeground="#FFFFFF",
            bd=1
        )
        groups = self.db.get_groups()
        for g in groups:
            group_menu.add_command(
                label=f"📁  {g['name']}",
                command=lambda gid=g["id"]: self._move_target_dbs_to_group(target_ids, gid)
            )
        if groups:
            group_menu.add_separator()
        group_menu.add_command(
            label="🚫  (None / Default)",
            command=lambda: self._move_target_dbs_to_group(target_ids, None)
        )
        group_menu.add_command(
            label="➕  Create New Group...",
            command=lambda: self._prompt_new_group_and_move(target_ids)
        )

        self.context_menu.add_cascade(label=f"📁 Move to Group{label_suffix}", menu=group_menu)
        self.context_menu.add_separator()
        if len(target_ids) > 1:
            self.context_menu.add_command(
                label=f"✏️ Bulk Edit ({len(target_ids)} DBs)...",
                command=lambda: self._open_bulk_edit_dialog(target_ids)
            )
        else:
            self.context_menu.add_command(label="✏️ Edit Connection", command=self._edit_selected_row)
        self.context_menu.add_command(label="🗑️ Delete Connection", command=self._delete_selected_row)

        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _move_target_dbs_to_group(self, target_ids: List[int], group_id: Optional[int]):
        """Pindahkan database terpilih ke group tertentu."""
        self.db.move_hosts_to_group(target_ids, group_id)
        self._refresh_connections()
        self._notify_data_changed()

    def _prompt_new_group_and_move(self, target_ids: List[int]):
        """Minta nama group baru, buat group, lalu pindahkan koneksi database terpilih."""
        dialog = ctk.CTkInputDialog(text="Enter new group name:", title="New Group")
        group_name = dialog.get_input()
        if group_name and group_name.strip():
            new_group_id = self.db.add_group(group_name.strip())
            self._move_target_dbs_to_group(target_ids, new_group_id)

    def _on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        col = self.tree.identify_column(event.x)
        # Jika klik pada kolom checkbox (#1)
        if col == "#1":
            self._toggle_row_check(item_id)
        self._on_tree_select_change()

    def _on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self._run_query_on_single_conn(int(item_id))

    def _on_tree_space(self, event):
        sel = self.tree.selection()
        if sel:
            for item_id in sel:
                self._toggle_row_check(item_id)

    def _toggle_row_check(self, item_id: str):
        conn_id = int(item_id)
        if conn_id in self.selected_db_ids:
            self.selected_db_ids.remove(conn_id)
            chk_str = "[ ]"
        else:
            self.selected_db_ids.add(conn_id)
            chk_str = "[✓]"
        curr_vals = list(self.tree.item(item_id, "values"))
        if curr_vals:
            curr_vals[0] = chk_str
            self.tree.item(item_id, values=curr_vals)
        self._sync_check_all_state()
        self._update_blast_button_label()

    def _on_tree_select_change(self, event=None):
        sel = self.tree.selection()
        has_sel = bool(sel)

        if has_sel:
            self.btn_action_run.configure(
                state="normal",
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                text_color="#FFFFFF",
                border_width=0,
                image=get_icon("play", (13, 13), "#FFFFFF")
            )
            self.btn_action_test.configure(
                state="normal",
                fg_color=COLORS["surface"],
                hover_color=COLORS["surface_hover"],
                text_color=COLORS["text"],
                border_width=1,
                border_color=COLORS["line"],
                image=get_icon("activity", (13, 13), COLORS["accent_text"])
            )
            edit_text = f" Bulk Edit ({len(self.selected_db_ids)})" if len(self.selected_db_ids) > 1 else " Edit"
            self.btn_action_edit.configure(
                text=edit_text,
                state="normal",
                fg_color=COLORS["surface"],
                hover_color=COLORS["surface_hover"],
                text_color=COLORS["text_secondary"],
                border_width=1,
                border_color=COLORS["line"],
                image=get_icon("pencil", (13, 13), COLORS["text_secondary"])
            )
            self.btn_action_del.configure(
                state="normal",
                fg_color=COLORS["danger_subtle"],
                hover_color=COLORS["danger_hover"],
                text_color=COLORS["danger_text"],
                border_width=1,
                border_color=COLORS["danger_border"],
                image=get_icon("trash", (13, 13), COLORS["danger_text"])
            )
        else:
            self.btn_action_run.configure(
                state="disabled",
                fg_color=COLORS["surface"],
                border_width=1,
                border_color=COLORS["line"],
                text_color_disabled=COLORS["subtle"],
                image=get_icon("play", (13, 13), COLORS["subtle"])
            )
            self.btn_action_test.configure(
                state="disabled",
                fg_color=COLORS["surface"],
                border_width=1,
                border_color=COLORS["line"],
                text_color_disabled=COLORS["subtle"],
                image=get_icon("activity", (13, 13), COLORS["subtle"])
            )
            self.btn_action_edit.configure(
                state="disabled",
                fg_color=COLORS["surface"],
                border_width=1,
                border_color=COLORS["line"],
                text_color_disabled=COLORS["subtle"],
                image=get_icon("pencil", (13, 13), COLORS["subtle"])
            )
            self.btn_action_del.configure(
                state="disabled",
                fg_color=COLORS["surface"],
                border_width=1,
                border_color=COLORS["line"],
                text_color_disabled=COLORS["subtle"],
                image=get_icon("trash", (13, 13), COLORS["subtle"])
            )

    def _run_query_on_selected_row(self):
        sel = self.tree.selection()
        if sel:
            self._run_query_on_single_conn(int(sel[0]))

    def _test_selected_row(self):
        sel = self.tree.selection()
        if sel:
            self._test_single_conn(int(sel[0]))

    def _edit_selected_row(self):
        checked_ids = list(self.selected_db_ids)
        if len(checked_ids) > 1:
            self._open_bulk_edit_dialog(checked_ids)
            return
        sel = self.tree.selection()
        if sel:
            self._open_edit_db_dialog(int(sel[0]))

    def _open_bulk_edit_dialog(self, conn_ids: List[int]):
        """Buka dialog bulk edit untuk daftar koneksi database yang dipilih."""
        if not conn_ids:
            return
        BulkDbDialog(
            parent=self.parent,
            db_manager=self.db,
            conn_ids=conn_ids,
            on_save_callback=self._refresh_and_notify
        )

    def _delete_selected_row(self):
        sel = self.tree.selection()
        if sel:
            c_id = int(sel[0])
            conn = next((c for c in self._all_connections if c["id"] == c_id), None)
            name = conn.get("name") if conn else f"DB-{c_id}"
            self._delete_conn(c_id, name)

    # =========================================================================
    # LOGGING HELPERS
    # =========================================================================
    def _log_message(self, text: str):
        self.txt_log.insert("end", text)
        self.txt_log.see("end")

    def _clear_execution_log(self):
        self.txt_log.delete("1.0", "end")

    def _clear_sql_editor(self):
        self.txt_sql.delete("1.0", "end")

    # =========================================================================
    # OPTIMIZED CONNECTIONS MANAGEMENT (NAVICAT TREEVIEW - SUB-10MS)
    # =========================================================================
    def _refresh_connections(self):
        """Ambil koneksi dari database SQLite, perbarui dropdown & judul, lalu terapkan filter ke Treeview."""
        self._needs_refresh = False

        # 1. Ambil seluruh koneksi tanpa dekripsi password (<2ms!)
        self._all_connections = self.db.get_all_db_connections(decrypt_passwords=False)

        # Update title count
        self.lbl_db_title.configure(text=f"Databases ({len(self._all_connections)})")

        # Update group dropdown
        groups = sorted(list({c.get("group_name") or "Default" for c in self._all_connections}))
        group_opts = ["All Groups"] + groups
        curr = self.opt_group.get()
        self.opt_group.configure(values=group_opts)
        if curr in group_opts:
            self.opt_group.set(curr)
        else:
            self.opt_group.set("All Groups")

        # 2. Terapkan filter & render Treeview
        self._apply_filter()
        self._is_loaded = True

    def _on_search_changed(self, *_):
        """Debounce pencarian 20ms agar pengetikan instan dan responsif."""
        if self.search_debounce_id:
            self.after_cancel(self.search_debounce_id)
        self.search_debounce_id = self.after(20, self._apply_filter)

    def _apply_filter(self):
        """Menyaring koneksi di memori, lalu populate Treeview secara instan (<2ms)."""
        query = self.search_var.get().strip().lower()
        selected_grp = self.opt_group.get()

        matching = []
        for c in self._all_connections:
            if selected_grp != "All Groups" and (c.get("group_name") or "Default") != selected_grp:
                continue
            if query:
                name = (c.get("name") or "").lower()
                host = (c.get("host") or "").lower()
                ssh_host = (c.get("ssh_host") or "").lower()
                if query not in name and query not in host and query not in ssh_host:
                    continue
            matching.append(c)

        self._current_filtered_conns = matching

        # Clear treeview items (<1ms)
        self.tree.delete(*self.tree.get_children())

        # Populate treeview items (<2ms)
        for c in matching:
            c_id = c["id"]
            chk_str = "[✓]" if c_id in self.selected_db_ids else "[ ]"
            ssh_txt = f"{c.get('ssh_username', 'root')}@{c.get('ssh_host', '')}" if c.get("use_ssh") and c.get("ssh_host") else "-"
            host_txt = f"{c.get('host', 'localhost')}:{c.get('port', 3306)}"
            self.tree.insert(
                "", "end",
                iid=str(c_id),
                values=(
                    chk_str,
                    c.get("name") or "Unnamed",
                    c.get("db_type") or "MYSQL",
                    host_txt,
                    ssh_txt,
                    "Ready"
                )
            )

        self._sync_check_all_state()
        self._update_blast_button_label()
        self._on_tree_select_change()

    def _sync_check_all_state(self):
        filtered = getattr(self, "_current_filtered_conns", [])
        if filtered:
            all_chk = all(c["id"] in self.selected_db_ids for c in filtered)
            chk_icon = "[✓]" if all_chk else "[ ]"
        else:
            chk_icon = "[ ]"
        self.tree.heading("chk", text=chk_icon)

    def _toggle_check_all(self):
        filtered = getattr(self, "_current_filtered_conns", [])
        if not filtered:
            return
        all_chk = all(c["id"] in self.selected_db_ids for c in filtered)
        should_check = not all_chk

        for c in filtered:
            c_id = c["id"]
            str_id = str(c_id)
            if should_check:
                self.selected_db_ids.add(c_id)
                chk_str = "[✓]"
            else:
                self.selected_db_ids.discard(c_id)
                chk_str = "[ ]"
            if self.tree.exists(str_id):
                vals = list(self.tree.item(str_id, "values"))
                vals[0] = chk_str
                self.tree.item(str_id, values=vals)

        self._sync_check_all_state()
        self._update_blast_button_label()

    def _update_blast_button_label(self):
        filtered = getattr(self, "_current_filtered_conns", [])
        total_visible = len(filtered)
        selected_visible = len([c["id"] for c in filtered if c["id"] in self.selected_db_ids])

        if selected_visible > 0:
            self.btn_run_blast.configure(text=f" Run Blast ({selected_visible})", image=get_icon("zap", (14, 14), "#FFFFFF"))
            self.lbl_blast_status.configure(text=f"{selected_visible} of {total_visible} selected")
        else:
            self.btn_run_blast.configure(text=" Run Blast (All)", image=get_icon("zap", (14, 14), "#FFFFFF"))
            self.lbl_blast_status.configure(text=f"All {total_visible} will run")

    def _update_tree_status(self, conn_id: int, text: str):
        str_id = str(conn_id)
        if self.tree.exists(str_id):
            self.tree.set(str_id, "status", text)

    # =========================================================================
    # DIALOGS & CRUD
    # =========================================================================
    def _notify_data_changed(self):
        """Beritahu view lain (Pull Blast) bahwa data host berubah, karena satu tabel dipakai bersama."""
        if self._on_data_changed:
            self._on_data_changed()

    def _refresh_and_notify(self):
        self._refresh_connections()
        self._notify_data_changed()

    def _open_new_db_dialog(self):
        DBConnectionDialog(
            parent=self.parent,
            db_manager=self.db,
            on_save_callback=self._refresh_and_notify
        )

    def _open_edit_db_dialog(self, conn_id: int):
        conn = self.db.get_db_connection_by_id(conn_id)
        if not conn:
            return
        DBConnectionDialog(
            parent=self.parent,
            db_manager=self.db,
            connection_data=conn,
            on_save_callback=self._refresh_and_notify
        )

    def _delete_conn(self, conn_id: int, name: str):
        if messagebox.askyesno("Hapus Database", f"Yakin ingin menghapus koneksi '{name}'? Host SSH terkait di Pull Blast akan ikut terhapus."):
            self.db.delete_db_connection(conn_id)
            self.selected_db_ids.discard(conn_id)
            str_id = str(conn_id)
            if self.tree.exists(str_id):
                self.tree.delete(str_id)
            if hasattr(self, "_all_connections"):
                self._all_connections = [c for c in self._all_connections if c["id"] != conn_id]
            if hasattr(self, "_current_filtered_conns"):
                self._current_filtered_conns = [c for c in self._current_filtered_conns if c["id"] != conn_id]
            self._sync_check_all_state()
            self._update_blast_button_label()
            self.lbl_db_title.configure(text=f"Databases ({len(self._all_connections)})")
            self._on_tree_select_change()
            self._notify_data_changed()

    # =========================================================================
    # IMPORT & EXPORT CONNECTIONS (JS / JSON / NCX)
    # =========================================================================
    def _import_db_connections(self):
        file_path = filedialog.askopenfilename(
            title="Import Database Connections",
            filetypes=[
                ("All Supported (*.js, *.json, *.ncx)", "*.js;*.json;*.ncx"),
                ("JavaScript Files (*.js)", "*.js"),
                ("JSON Files (*.json)", "*.json"),
                ("Navicat NCX Export (*.ncx)", "*.ncx"),
                ("All Files (*.*)", "*.*")
            ]
        )
        if not file_path:
            return

        try:
            conns = import_connections_from_file(file_path)
            if not conns:
                messagebox.showwarning("Import Empty", "Tidak ditemukan data koneksi yang valid di file ini.")
                return

            count = self.db.bulk_import_db_connections(conns)
            self._refresh_and_notify()
            messagebox.showinfo(
                "Import Berhasil",
                f"Berhasil mengimpor {count} koneksi database dari:\n{os.path.basename(file_path)}"
            )
            self._log_message(f"[{datetime.now().strftime('%H:%M:%S')}] ⬇ Berhasil mengimpor {count} database dari {file_path}\n")
        except Exception as e:
            messagebox.showerror("Import Error", f"Gagal mengimpor file: {e}")

    def _export_db_connections(self):
        # Saat export, decrypt passwords agar file export lengkap
        conns = self.db.get_all_db_connections(decrypt_passwords=True)
        if not conns:
            messagebox.showwarning("Export Kosong", "Belum ada koneksi database yang tersimpan untuk diekspor.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Export Database Connections",
            defaultextension=".js",
            filetypes=[
                ("JavaScript File (*.js)", "*.js"),
                ("JSON File (*.json)", "*.json"),
                ("All Files (*.*)", "*.*")
            ]
        )
        if not file_path:
            return

        try:
            as_js = file_path.lower().endswith(".js")
            export_connections_to_file(conns, file_path, as_js=as_js)
            messagebox.showinfo(
                "Export Berhasil",
                f"Berhasil mengekspor {len(conns)} koneksi database ke:\n{file_path}"
            )
            self._log_message(f"[{datetime.now().strftime('%H:%M:%S')}] ⬆ Berhasil mengekspor {len(conns)} database ke {file_path}\n")
        except Exception as e:
            messagebox.showerror("Export Error", f"Gagal mengekspor file: {e}")

    # =========================================================================
    # IMPORT & EXPORT QUERY (.sql)
    # =========================================================================
    def _import_sql_file(self):
        file_path = filedialog.askopenfilename(
            title="Open SQL Query File",
            filetypes=[
                ("SQL Files (*.sql)", "*.sql"),
                ("Text Files (*.txt)", "*.txt"),
                ("All Files (*.*)", "*.*")
            ]
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self.txt_sql.delete("1.0", "end")
            self.txt_sql.insert("1.0", content)
            self._log_message(f"[{datetime.now().strftime('%H:%M:%S')}] 📂 Query berhasil dimuat dari: {os.path.basename(file_path)}\n")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membaca file SQL: {e}")

    def _export_sql_file(self):
        query = self.txt_sql.get("1.0", "end").strip()
        if not query:
            messagebox.showwarning("Warning", "Editor SQL masih kosong.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save SQL Query",
            defaultextension=".sql",
            filetypes=[
                ("SQL Files (*.sql)", "*.sql"),
                ("Text Files (*.txt)", "*.txt"),
                ("All Files (*.*)", "*.*")
            ]
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(query)
            messagebox.showinfo("Saved", f"Query SQL berhasil disimpan ke:\n{file_path}")
            self._log_message(f"[{datetime.now().strftime('%H:%M:%S')}] 💾 Query disimpan ke: {file_path}\n")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan file SQL: {e}")

    # =========================================================================
    # TEST CONNECTION
    # =========================================================================
    def _test_single_conn(self, conn_id: int):
        self._update_tree_status(conn_id, "Testing...")

        # Ambil data lengkap dengan password terdekripsi
        conn = self.db.get_db_connection_by_id(conn_id)
        if not conn:
            return

        name = conn.get("name") or f"DB-{conn_id}"
        self._log_message(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ Testing connection to '{name}' ({conn.get('host')})...\n")

        def worker():
            res = run_db_query(conn, "SELECT VERSION();", timeout=10)

            def update():
                if res["success"]:
                    self._update_tree_status(conn_id, f"✓ OK ({res['elapsed_ms']}ms)")
                    self._log_message(f"✓ [{name}] Connection SUCCESS ({res['elapsed_ms']}ms): {res['output'].strip()}\n")
                    messagebox.showinfo(
                        "Test Connection",
                        f"Koneksi ke '{name}' BERHASIL!\n\nResponse time: {res['elapsed_ms']} ms\nOutput:\n{res['output'].strip()}"
                    )
                else:
                    self._update_tree_status(conn_id, "✗ Error")
                    self._log_message(f"✗ [{name}] Connection FAILED ({res['elapsed_ms']}ms): {res['error']}\n")
                    messagebox.showerror(
                        "Test Connection",
                        f"Koneksi ke '{name}' GAGAL!\n\nError:\n{res['error']}"
                    )

            self.after(0, update)

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # SINGLE QUERY EXECUTION
    # =========================================================================
    def _run_query_on_single_conn(self, conn_id: int):
        query = self.txt_sql.get("1.0", "end").strip()
        if not query:
            messagebox.showwarning("Warning", "Silakan masukkan query SQL di editor terlebih dahulu.")
            return

        self._update_tree_status(conn_id, "Running...")

        conn = self.db.get_db_connection_by_id(conn_id)
        if not conn:
            return

        name = conn.get("name") or f"DB-{conn_id}"
        self._set_active_tab("log")
        self._log_message(f"\n[{datetime.now().strftime('%H:%M:%S')}] === Running Query on [{name}] ===\n")
        self._log_message(f"Query: {query[:120]}...\n")

        def worker():
            res = run_db_query(conn, query, timeout=20)

            def update():
                if res["success"]:
                    self._update_tree_status(conn_id, f"✓ OK ({res['elapsed_ms']}ms)")
                    self._log_message(f"✓ Output:\n{res['output']}\nElapsed: {res['elapsed_ms']} ms\n")
                    self._cache_result(name, res)
                else:
                    self._update_tree_status(conn_id, "✗ Error")
                    self._log_message(f"✗ Error:\n{res['error']}\nElapsed: {res['elapsed_ms']} ms\n")
                    self._cache_result(name, res)

                self._log_message("-" * 50 + "\n")

            self.after(0, update)

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # BLAST ALL / SELECTED EXECUTION
    # =========================================================================
    def _run_blast(self):
        """Menjalankan query SQL ke semua database yang dipilih secara bersamaan/terkendali tanpa membuat freeze UI."""
        if self.is_running_blast:
            return

        query = self.txt_sql.get("1.0", "end").strip()
        if not query:
            messagebox.showwarning("Empty Query", "Tuliskan query SQL di editor sebelum menjalankan Blast.")
            return

        # Ambil daftar target id yang terlihat dan/atau dicentang
        filtered = getattr(self, "_current_filtered_conns", [])
        checked_ids = [c["id"] for c in filtered if c["id"] in self.selected_db_ids]

        if checked_ids:
            target_ids = checked_ids
        else:
            # Jika tidak ada yang dicentang khusus, jalankan ke seluruh database yang sedang difilter
            target_ids = [c["id"] for c in filtered]

        if not target_ids:
            messagebox.showwarning("No Target", "Tidak ada database target yang dipilih.")
            return

        # Ambil koneksi lengkap dengan password terdekripsi hanya untuk target yang dieksekusi
        targets = self.db.get_db_connections_by_ids(target_ids)
        if not targets:
            messagebox.showwarning("No Target", "Data database target tidak ditemukan.")
            return

        self.is_running_blast = True
        self.query_results_cache.clear()
        self.btn_run_blast.configure(state="disabled", text="⏳ Blasting...")
        self._set_active_tab("log")

        self._log_message("\n" + "=" * 60 + "\n")
        self._log_message(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ STARTING DB BLAST ON {len(targets)} DATABASE(S)\n")
        self._log_message(f"Query: {query}\n")
        self._log_message("=" * 60 + "\n\n")

        for t in targets:
            self._update_tree_status(t["id"], "Pending...")

        def worker():
            success_count = 0
            failed_count = 0
            total_elapsed = 0

            # Concurrency limit (maksimal 6 koneksi bersamaan agar tidak membebani network)
            max_workers = min(6, len(targets))
            sem = asyncio.Semaphore(max_workers)

            async def execute_target(target: Dict[str, Any]):
                nonlocal success_count, failed_count, total_elapsed
                c_id = target["id"]
                name = target.get("name") or f"DB-{c_id}"

                async with sem:
                    # Update label to running
                    self.after(0, lambda: self._update_tree_status(c_id, "Running..."))
                    self.after(0, lambda: self._log_message(f"[{datetime.now().strftime('%H:%M:%S')}] >> Blasting '{name}' ({target.get('host')})...\n"))

                    # Eksekusi di thread terpisah agar async loop tidak terblokir
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(None, run_db_query, target, query, 20)

                    elapsed = res.get("elapsed_ms", 0)
                    total_elapsed += elapsed

                    if res.get("success"):
                        success_count += 1
                        self.after(0, lambda: self._update_tree_status(c_id, f"✓ OK ({elapsed}ms)"))
                        self.after(0, lambda: self._log_message(f"✓ [{name}] SUCCESS ({elapsed}ms):\n{res.get('output', '')}\n\n"))
                    else:
                        failed_count += 1
                        self.after(0, lambda: self._update_tree_status(c_id, "✗ Error"))
                        self.after(0, lambda: self._log_message(f"✗ [{name}] FAILED ({elapsed}ms):\n{res.get('error', '')}\n\n"))

                    self.after(0, lambda: self._cache_result(name, res))

            async def run_all_async():
                tasks = [asyncio.create_task(execute_target(t)) for t in targets]
                await asyncio.gather(*tasks, return_exceptions=True)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_all_async())
            finally:
                loop.close()

            # Selesai Blast
            def blast_finished():
                self.is_running_blast = False
                self._update_blast_button_label()
                self.btn_run_blast.configure(state="normal")

                self._log_message("=" * 60 + "\n")
                self._log_message(f"[{datetime.now().strftime('%H:%M:%S')}] 🏁 DB BLAST FINISHED!\n")
                self._log_message(f"Total: {len(targets)} | Berhasil: {success_count} | Gagal: {failed_count}\n")
                self._log_message("=" * 60 + "\n")

                # Default ke All Databases view
                if len(targets) > 1:
                    self.opt_result_db.set("All Databases (Combined)")
                    self._on_result_db_selected("All Databases (Combined)")
                elif targets:
                    first_name = targets[0].get("name") or f"DB-{targets[0]['id']}"
                    self.opt_result_db.set(first_name)
                    self._on_result_db_selected(first_name)

                messagebox.showinfo(
                    "DB Blast Finished",
                    f"DB Blast selesai dieksekusi!\n\n"
                    f"Total Database: {len(targets)}\n"
                    f"✓ Berhasil: {success_count}\n"
                    f"✗ Gagal: {failed_count}\n\n"
                    f"Lihat tab 'Query Results' atau 'Execution Log' untuk detail output."
                )

            self.after(0, blast_finished)

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # QUERY RESULTS TAB HANDLING
    # =========================================================================
    def _copy_query_result(self):
        text = self.txt_result.get("1.0", "end-1c")
        if text.strip():
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copied", "Hasil query berhasil disalin ke clipboard.")

    def _cache_result(self, db_name: str, result: Dict[str, Any]):
        self.query_results_cache[db_name] = result

        # Perbarui dropdown daftar hasil dengan opsi All Databases di awal
        db_keys = list(self.query_results_cache.keys())
        if db_keys:
            options = ["All Databases (Combined)"] + db_keys if len(db_keys) > 1 else db_keys
            self.opt_result_db.configure(values=options)
            current = self.opt_result_db.get()
            if current not in options or current == "(No Results Yet)":
                default_choice = "All Databases (Combined)" if len(db_keys) > 1 else db_keys[0]
                self.opt_result_db.set(default_choice)
                self._on_result_db_selected(default_choice)
            else:
                self._on_result_db_selected(current)

    def _on_result_db_selected(self, selected_name: str):
        self.txt_result.delete("1.0", "end")

        if not self.query_results_cache:
            self.txt_result.insert("1.0", "Belum ada hasil query.")
            self.lbl_result_meta.configure(text="")
            return

        if selected_name == "All Databases (Combined)" or (selected_name not in self.query_results_cache and len(self.query_results_cache) > 1):
            total = len(self.query_results_cache)
            success_count = sum(1 for r in self.query_results_cache.values() if r.get("success"))
            failed_count = total - success_count
            total_elapsed = sum(r.get("elapsed_ms", 0) for r in self.query_results_cache.values())

            lines = []
            lines.append("=" * 80)
            lines.append(f"ALL DATABASES QUERY RESULTS ({total} Databases)")
            lines.append(f"✓ Success: {success_count}  |  ✗ Failed: {failed_count}  |  ⏱ Total Time: {total_elapsed} ms")
            lines.append("=" * 80)
            lines.append("")

            for name, res in self.query_results_cache.items():
                is_ok = res.get("success", False)
                elapsed = res.get("elapsed_ms", 0)
                status_icon = "✓" if is_ok else "✗"
                status_label = "SUCCESS" if is_ok else "FAILED"

                lines.append("━" * 80)
                lines.append(f"[{status_icon}] DATABASE: {name}  ({status_label} • {elapsed} ms)")
                lines.append("━" * 80)

                if is_ok:
                    out = res.get("output", "")
                    lines.append(out.strip() if out else "Query OK (0 rows affected)")
                else:
                    err = res.get("error", "Unknown error")
                    lines.append(f"ERROR:\n{err.strip()}")
                lines.append("\n")

            combined_text = "\n".join(lines)
            self.txt_result.insert("1.0", combined_text)
            self.lbl_result_meta.configure(
                text=f"Total: {total} DBs  •  ✓ {success_count} OK  •  ✗ {failed_count} Failed",
                text_color=COLORS["success"] if failed_count == 0 else COLORS["danger"]
            )
            return

        # Single DB Result
        res = self.query_results_cache.get(selected_name)
        if not res:
            self.txt_result.insert("1.0", f"Belum ada hasil untuk database '{selected_name}'.")
            self.lbl_result_meta.configure(text="")
            return

        if res.get("success"):
            self.txt_result.insert("1.0", res.get("output", "Query OK (0 rows affected)"))
            self.lbl_result_meta.configure(
                text=f"Status: SUCCESS  •  Time: {res.get('elapsed_ms', 0)} ms",
                text_color=COLORS["success"]
            )
        else:
            self.txt_result.insert("1.0", f"ERROR:\n{res.get('error', 'Unknown error')}")
            self.lbl_result_meta.configure(
                text=f"Status: FAILED  •  Time: {res.get('elapsed_ms', 0)} ms",
                text_color=COLORS["danger"]
            )
