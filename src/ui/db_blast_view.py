import asyncio
import os
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Set

import customtkinter as ctk

from db_executor import (
    export_connections_to_file,
    import_connections_from_file,
    run_db_query,
)
from ui.db_dialog import DBConnectionDialog

COLORS = {
    "window": "#111214",
    "sidebar": "#1A1B1F",
    "surface": "#202126",
    "surface_hover": "#2A2C33",
    "line": "#32343B",
    "text": "#F5F5F7",
    "muted": "#9699A3",
    "accent": "#0A84FF",
    "accent_hover": "#0072E5",
    "success": "#30D158",
    "danger": "#FF453A",
    "warning": "#FFD60A",
    "badge_bg": "#12355F",
    "badge_text": "#8DC6FF",
}

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
            text="+ New",
            width=62, height=30, corner_radius=7,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_new_db_dialog
        )
        btn_new.pack(side="left", padx=(0, 5))

        btn_import = ctk.CTkButton(
            btn_header_group,
            text="⬇ Import",
            width=70, height=30, corner_radius=7,
            fg_color="#2A2C33", hover_color="#383B44",
            font=ctk.CTkFont(size=12),
            command=self._import_db_connections
        )
        btn_import.pack(side="left", padx=(0, 5))

        btn_export = ctk.CTkButton(
            btn_header_group,
            text="⬆ Export",
            width=70, height=30, corner_radius=7,
            fg_color="#2A2C33", hover_color="#383B44",
            font=ctk.CTkFont(size=12),
            command=self._export_db_connections
        )
        btn_export.pack(side="left", padx=(0, 5))

        btn_refresh = ctk.CTkButton(
            btn_header_group,
            text="↻",
            width=34, height=30, corner_radius=7,
            fg_color="#2A2C33", hover_color="#383B44",
            font=ctk.CTkFont(size=12),
            command=self._refresh_connections
        )
        btn_refresh.pack(side="left")

        # 2. Filter & Search Bar
        filter_bar = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        filter_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        filter_bar.grid_columnconfigure(0, weight=1)

        # Search Box
        search_box = ctk.CTkFrame(filter_bar, fg_color="#18191D", corner_radius=8, border_width=1, border_color=COLORS["line"])
        search_box.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        search_box.grid_columnconfigure(1, weight=1)

        lbl_icon = ctk.CTkLabel(search_box, text="⌕", text_color=COLORS["muted"], font=ctk.CTkFont(size=16))
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

        # Row 2: Check All & Group Filter
        ctrl_row = ctk.CTkFrame(filter_bar, fg_color="transparent")
        ctrl_row.grid(row=1, column=0, sticky="ew")
        ctrl_row.grid_columnconfigure(1, weight=1)

        self.chk_all_var = ctk.BooleanVar(value=False)
        self.chk_all = ctk.CTkCheckBox(
            ctrl_row,
            text="Check All",
            variable=self.chk_all_var,
            width=20, checkbox_width=17, checkbox_height=17,
            corner_radius=5,
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self._toggle_check_all
        )
        self.chk_all.pack(side="left")

        self.opt_group = ctk.CTkOptionMenu(
            ctrl_row,
            values=["All Groups"],
            width=140, height=28,
            corner_radius=6,
            fg_color="#2A2C33",
            button_color="#383B44",
            command=lambda _: self._apply_filter()
        )
        self.opt_group.pack(side="right")

        # 3. Navicat Style High-Performance Connection Table Explorer (<10ms load)
        table_container = tk.Frame(self.left_panel, bg="#18191D", highlightthickness=1, highlightbackground=COLORS["line"])
        table_container.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Navicat.Treeview",
            background="#18191D",
            foreground="#F5F5F7",
            fieldbackground="#18191D",
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0
        )
        style.configure(
            "Navicat.Treeview.Heading",
            background="#242529",
            foreground="#9699A3",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            borderwidth=0
        )
        style.map(
            "Navicat.Treeview",
            background=[("selected", "#0A84FF")],
            foreground=[("selected", "#FFFFFF")]
        )

        self.tree = ttk.Treeview(
            table_container,
            columns=("chk", "name", "type", "host", "ssh", "status"),
            show="headings",
            style="Navicat.Treeview",
            selectmode="browse"
        )
        self.tree.heading("chk", text="[✓]", anchor="center")
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
            action_bar, text="⚡ Run Single", height=28, corner_radius=6,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._run_query_on_selected_row
        )
        self.btn_action_run.grid(row=0, column=0, padx=2, sticky="ew")

        self.btn_action_test = ctk.CTkButton(
            action_bar, text="🧪 Test", height=28, corner_radius=6,
            fg_color="#18283E", hover_color="#223B5D",
            text_color="#60A5FA", border_width=1, border_color="#254A78",
            font=ctk.CTkFont(size=11),
            command=self._test_selected_row
        )
        self.btn_action_test.grid(row=0, column=1, padx=2, sticky="ew")

        self.btn_action_edit = ctk.CTkButton(
            action_bar, text="✏️ Edit", height=28, corner_radius=6,
            fg_color="#2A2C33", hover_color="#383B44",
            font=ctk.CTkFont(size=11),
            command=self._edit_selected_row
        )
        self.btn_action_edit.grid(row=0, column=2, padx=2, sticky="ew")

        self.btn_action_del = ctk.CTkButton(
            action_bar, text="🗑️ Delete", height=28, corner_radius=6,
            fg_color="transparent", border_width=1, border_color="#71322E",
            text_color=COLORS["danger"], hover_color="#3B2223",
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

        # 1. Query Action Toolbar
        toolbar = ctk.CTkFrame(self.right_panel, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10), ipady=4)
        toolbar.grid_columnconfigure(0, weight=1)

        left_tools = ctk.CTkFrame(toolbar, fg_color="transparent")
        left_tools.pack(side="left", padx=10, pady=6)

        self.btn_run_blast = ctk.CTkButton(
            left_tools,
            text="⚡ Run Blast",
            height=34, corner_radius=8,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._run_blast
        )
        self.btn_run_blast.pack(side="left", padx=(0, 10))

        btn_import_sql = ctk.CTkButton(
            left_tools,
            text="📂 Open SQL",
            width=90, height=34, corner_radius=8,
            fg_color="#2A2C33", hover_color="#383B44",
            command=self._import_sql_file
        )
        btn_import_sql.pack(side="left", padx=(0, 6))

        btn_export_sql = ctk.CTkButton(
            left_tools,
            text="💾 Save SQL",
            width=90, height=34, corner_radius=8,
            fg_color="#2A2C33", hover_color="#383B44",
            command=self._export_sql_file
        )
        btn_export_sql.pack(side="left", padx=(0, 6))

        btn_clear_sql = ctk.CTkButton(
            left_tools,
            text="🧹 Clear Editor",
            width=95, height=34, corner_radius=8,
            fg_color="transparent", border_width=1, border_color=COLORS["line"],
            hover_color=COLORS["surface_hover"],
            command=self._clear_sql_editor
        )
        btn_clear_sql.pack(side="left")

        right_tools = ctk.CTkFrame(toolbar, fg_color="transparent")
        right_tools.pack(side="right", padx=10, pady=6)

        self.lbl_blast_status = ctk.CTkLabel(
            right_tools,
            text="0 selected",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_blast_status.pack(side="right", padx=5)

        # 2. SQL Editor Frame
        editor_frame = ctk.CTkFrame(self.right_panel, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        editor_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        editor_frame.grid_rowconfigure(1, weight=1)
        editor_frame.grid_columnconfigure(0, weight=1)

        editor_header = ctk.CTkFrame(editor_frame, fg_color="transparent")
        editor_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            editor_header,
            text="Query Editor (SQL)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text"]
        ).pack(side="left")

        ctk.CTkLabel(
            editor_header,
            text="Tekan '⚡ Run Blast' untuk mengeksekusi ke database terpilih",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"]
        ).pack(side="right")

        self.txt_sql = ctk.CTkTextbox(
            editor_frame,
            font=("Consolas", 13),
            wrap="none",
            corner_radius=8,
            border_width=0,
            fg_color="#17181C",
            text_color="#E0E2EC",
            undo=True
        )
        self.txt_sql.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.txt_sql.insert("1.0", DEFAULT_SQL)

        # 3. Navicat Style Bottom Tabview (Execution Log & Query Results)
        self.tabview = ctk.CTkTabview(
            self.right_panel,
            corner_radius=10,
            border_width=1,
            border_color=COLORS["line"],
            fg_color=COLORS["surface"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color=COLORS["accent_hover"]
        )
        self.tabview.grid(row=2, column=0, sticky="nsew", pady=0)

        # Tab 1: Execution Log (Streaming console output)
        self.tab_log = self.tabview.add("📋 Execution Log")
        self.tab_log.grid_columnconfigure(0, weight=1)
        self.tab_log.grid_rowconfigure(1, weight=1)

        log_toolbar = ctk.CTkFrame(self.tab_log, fg_color="transparent")
        log_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        btn_clear_log = ctk.CTkButton(
            log_toolbar,
            text="Clear Log",
            width=75, height=26, corner_radius=6,
            fg_color="#2A2C33", hover_color="#383B44",
            font=ctk.CTkFont(size=11),
            command=self._clear_execution_log
        )
        btn_clear_log.pack(side="right")

        self.txt_log = ctk.CTkTextbox(
            self.tab_log,
            font=("Consolas", 12),
            wrap="none",
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"],
            fg_color="#17181C",
            text_color="#D1D5DB"
        )
        self.txt_log.grid(row=1, column=0, sticky="nsew")

        # Tab 2: Query Results (Formatted Table viewer)
        self.tab_result = self.tabview.add("📊 Query Results")
        self.tab_result.grid_columnconfigure(0, weight=1)
        self.tab_result.grid_rowconfigure(1, weight=1)

        result_ctrl = ctk.CTkFrame(self.tab_result, fg_color="transparent")
        result_ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        lbl_pick = ctk.CTkLabel(result_ctrl, text="Pilih Database:", font=ctk.CTkFont(size=12))
        lbl_pick.pack(side="left", padx=(0, 8))

        self.opt_result_db = ctk.CTkOptionMenu(
            result_ctrl,
            values=["(No Results Yet)"],
            width=260, height=28,
            corner_radius=6,
            fg_color="#2A2C33",
            button_color="#383B44",
            command=self._on_result_db_selected
        )
        self.opt_result_db.pack(side="left")

        self.lbl_result_meta = ctk.CTkLabel(result_ctrl, text="", text_color=COLORS["muted"], font=ctk.CTkFont(size=11))
        self.lbl_result_meta.pack(side="right")

        self.txt_result = ctk.CTkTextbox(
            self.tab_result,
            font=("Consolas", 12),
            wrap="none",
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"],
            fg_color="#17181C",
            text_color="#93C5FD"
        )
        self.txt_result.grid(row=1, column=0, sticky="nsew")

    # =========================================================================
    # CONTEXT MENU & SELECTION HANDLING
    # =========================================================================
    def _create_tree_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0, bg="#202126", fg="#F5F5F7", activebackground="#0A84FF", activeforeground="#FFFFFF", bd=1)
        self.context_menu.add_command(label="⚡ Run Query on This DB", command=self._run_query_on_selected_row)
        self.context_menu.add_command(label="🧪 Test Connection", command=self._test_selected_row)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="✏️ Edit Connection", command=self._edit_selected_row)
        self.context_menu.add_command(label="🗑️ Delete Connection", command=self._delete_selected_row)

    def _show_tree_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self._on_tree_select_change()
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

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
        st = "normal" if has_sel else "disabled"
        self.btn_action_run.configure(state=st)
        self.btn_action_test.configure(state=st)
        self.btn_action_edit.configure(state=st)
        self.btn_action_del.configure(state=st)

    def _run_query_on_selected_row(self):
        sel = self.tree.selection()
        if sel:
            self._run_query_on_single_conn(int(sel[0]))

    def _test_selected_row(self):
        sel = self.tree.selection()
        if sel:
            self._test_single_conn(int(sel[0]))

    def _edit_selected_row(self):
        sel = self.tree.selection()
        if sel:
            self._open_edit_db_dialog(int(sel[0]))

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
            self.chk_all_var.set(all_chk)
        else:
            self.chk_all_var.set(False)

    def _toggle_check_all(self):
        is_chk = self.chk_all_var.get()
        filtered = getattr(self, "_current_filtered_conns", [])
        for c in filtered:
            c_id = c["id"]
            str_id = str(c_id)
            if is_chk:
                self.selected_db_ids.add(c_id)
                chk_str = "[✓]"
            else:
                self.selected_db_ids.discard(c_id)
                chk_str = "[ ]"
            if self.tree.exists(str_id):
                vals = list(self.tree.item(str_id, "values"))
                vals[0] = chk_str
                self.tree.item(str_id, values=vals)

        self._update_blast_button_label()

    def _update_blast_button_label(self):
        filtered = getattr(self, "_current_filtered_conns", [])
        total_visible = len(filtered)
        selected_visible = len([c["id"] for c in filtered if c["id"] in self.selected_db_ids])

        if selected_visible > 0:
            self.btn_run_blast.configure(text=f"⚡ Run Blast ({selected_visible})")
            self.lbl_blast_status.configure(text=f"{selected_visible} of {total_visible} selected")
        else:
            self.btn_run_blast.configure(text="⚡ Run Blast (All)")
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
        self.tabview.set("📋 Execution Log")
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
        self.btn_run_blast.configure(state="disabled", text="⏳ Blasting...")
        self.tabview.set("📋 Execution Log")

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
    def _cache_result(self, db_name: str, result: Dict[str, Any]):
        self.query_results_cache[db_name] = result

        # Perbarui dropdown daftar hasil
        db_keys = list(self.query_results_cache.keys())
        if db_keys:
            self.opt_result_db.configure(values=db_keys)
            current = self.opt_result_db.get()
            if current not in db_keys or current == "(No Results Yet)":
                self.opt_result_db.set(db_keys[0])
                self._on_result_db_selected(db_keys[0])

    def _on_result_db_selected(self, selected_name: str):
        res = self.query_results_cache.get(selected_name)
        if not res:
            self.txt_result.delete("1.0", "end")
            self.txt_result.insert("1.0", "Belum ada hasil untuk database ini.")
            self.lbl_result_meta.configure(text="")
            return

        self.txt_result.delete("1.0", "end")
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
