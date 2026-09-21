import asyncio
import os
import threading
import time
from datetime import datetime
from tkinter import filedialog, messagebox
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
    - Sisi Kiri: Panel Koneksi Database (Pencarian, Filter, Check All, Tambah, Import/Export, Aksi per DB)
    - Sisi Kanan: SQL Query Editor & Tab Hasil (Log Eksekusi & Tabel Hasil Query)
    - Dioptimalkan dengan widget caching & show/hide virtualisasi agar pencarian super cepat (<2ms).
    """

    def __init__(self, parent: ctk.CTk, db_manager: Any, on_data_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.parent = parent
        self.db = db_manager
        self._on_data_changed = on_data_changed

        self.selected_db_ids: Set[int] = set()
        self.connection_cards: Dict[int, Dict[str, Any]] = {}
        self.query_results_cache: Dict[str, Dict[str, Any]] = {}
        self.is_running_blast = False
        self.search_debounce_id = None
        self._is_loaded = False

        # Auto-seed dari connections.ncx / db_connections.js jika database lokal masih kosong
        self._check_initial_seed()

        self._setup_ui()
        self._refresh_connections()

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
        self.grid_columnconfigure(0, weight=3, minsize=380)
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
            width=130, height=28,
            corner_radius=6,
            fg_color="#2A2C33",
            button_color="#383B44",
            command=lambda _: self._apply_filter()
        )
        self.opt_group.pack(side="right")

        # 3. Scrollable List of DB Cards
        self.conns_scroll = ctk.CTkScrollableFrame(self.left_panel, fg_color="transparent", corner_radius=0)
        self.conns_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

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
        editor_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 4))
        ctk.CTkLabel(
            editor_header,
            text="SQL Query Editor",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"]
        ).pack(side="left")

        ctk.CTkLabel(
            editor_header,
            text="Tekan '⚡ Run Blast' untuk menjalankan query ke target database terpilih",
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
    # OPTIMIZED CONNECTIONS MANAGEMENT (CARD CACHING & FAST FILTERING)
    # =========================================================================
    def _refresh_connections(self):
        """Ambil koneksi dari database SQLite, bangun kartu sekali, perbarui opsi grup, lalu filter."""
        # 1. Bersihkan kartu lama dari UI jika ada
        for widget in self.conns_scroll.winfo_children():
            widget.destroy()

        self.connection_cards.clear()

        # 2. Ambil seluruh koneksi tanpa dekripsi password (super cepat <1ms!)
        connections = self.db.get_all_db_connections(decrypt_passwords=False)

        # Update title count
        self.lbl_db_title.configure(text=f"Databases ({len(connections)})")

        # Update group dropdown
        groups = sorted(list({c.get("group_name") or "Default" for c in connections}))
        group_opts = ["All Groups"] + groups
        curr = self.opt_group.get()
        self.opt_group.configure(values=group_opts)
        if curr in group_opts:
            self.opt_group.set(curr)
        else:
            self.opt_group.set("All Groups")

        # 3. Label kosong (ketika filter tidak menemukan hasil)
        self.lbl_empty_results = ctk.CTkLabel(
            self.conns_scroll,
            text="Tidak ada database yang cocok.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12)
        )

        # 4. Bangun kartu satu kali saja untuk semua koneksi
        for conn in connections:
            self._create_conn_card(conn)

        # 5. Bind mousewheel satu kali ke conns_scroll
        self.after(50, lambda: self._bind_mousewheel(self.conns_scroll))

        # 6. Terapkan filter saat ini
        self._apply_filter()
        self._is_loaded = True

    def _on_search_changed(self, *_):
        """Debounce pencarian 30ms agar pengetikan cepat terasa sangat responsif dan tidak freeze."""
        if self.search_debounce_id:
            self.after_cancel(self.search_debounce_id)
        self.search_debounce_id = self.after(30, self._apply_filter)

    def _apply_filter(self):
        """Menyaring kartu yang tampil tanpa create/destroy widget (Super Fast: <2ms!)."""
        query = self.search_var.get().strip().lower()
        selected_grp = self.opt_group.get()

        visible_count = 0
        for item in self.connection_cards.values():
            match_grp = (selected_grp == "All Groups") or (item["group"] == selected_grp)
            match_query = (not query) or (
                query in item["name_lower"]
                or query in item["host_lower"]
                or query in item["ssh_host_lower"]
            )
            should_show = match_grp and match_query

            if should_show:
                if not item["is_visible"]:
                    item["card"].pack(fill="x", padx=2, pady=4)
                    item["is_visible"] = True
                visible_count += 1
            else:
                if item["is_visible"]:
                    item["card"].pack_forget()
                    item["is_visible"] = False

        if hasattr(self, 'lbl_empty_results'):
            if visible_count == 0:
                self.lbl_empty_results.pack(pady=40)
            else:
                self.lbl_empty_results.pack_forget()

        self._sync_check_all_state()
        self._update_blast_button_label()

    def _bind_mousewheel(self, widget):
        """Rekursif bind event scroll trackpad/mouse ke semua child widget di CTkScrollableFrame."""
        try:
            canvas = self.conns_scroll._parent_canvas
            def _scroll(event):
                canvas.yview_scroll(int(-1 * (event.delta / 60)), "units")
            widget.bind("<MouseWheel>", _scroll, add="+")
            for child in widget.winfo_children():
                self._bind_mousewheel(child)
        except Exception:
            pass

    def _create_conn_card(self, conn: Dict[str, Any]):
        conn_id = conn["id"]
        card = ctk.CTkFrame(
            self.conns_scroll,
            fg_color="#1A1B1F",
            corner_radius=10,
            border_width=1,
            border_color=COLORS["line"]
        )
        card.pack(fill="x", padx=2, pady=4)

        # Checkbox
        is_sel = conn_id in self.selected_db_ids
        chk_var = ctk.BooleanVar(value=is_sel)

        chk = ctk.CTkCheckBox(
            card,
            text="",
            variable=chk_var,
            width=20, checkbox_width=17, checkbox_height=17,
            corner_radius=4,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=lambda c_id=conn_id: self._on_conn_checked(c_id)
        )
        chk.pack(side="left", padx=(10, 4))

        # Detail info
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=6, pady=8)

        # Baris 1: Nama + Badges
        r1 = ctk.CTkFrame(info, fg_color="transparent")
        r1.pack(anchor="w")

        lbl_name = ctk.CTkLabel(
            r1,
            text=conn.get("name") or "Unnamed",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"]
        )
        lbl_name.pack(side="left")

        # Type Badge (MySQL)
        db_type = conn.get("db_type") or "MYSQL"
        lbl_type = ctk.CTkLabel(
            r1,
            text=db_type,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#0F3A22",
            text_color="#4ADE80",
            corner_radius=5,
            padx=5, pady=1
        )
        lbl_type.pack(side="left", padx=(6, 0))

        # SSH Badge
        if conn.get("use_ssh"):
            lbl_ssh = ctk.CTkLabel(
                r1,
                text="SSH",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#1E293B",
                text_color="#93C5FD",
                corner_radius=5,
                padx=5, pady=1
            )
            lbl_ssh.pack(side="left", padx=(4, 0))

        # Baris 2: Subtitle
        ssh_info = f" via {conn.get('ssh_host')}" if conn.get("use_ssh") and conn.get("ssh_host") else ""
        sub_text = f"{conn.get('host', 'localhost')}:{conn.get('port', 3306)}{ssh_info}"
        lbl_sub = ctk.CTkLabel(
            info,
            text=sub_text,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"],
            anchor="w"
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))

        # Live status label
        lbl_status = ctk.CTkLabel(
            info,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["muted"],
            anchor="w"
        )
        lbl_status.pack(anchor="w")

        # Action Buttons
        btn_del = ctk.CTkButton(
            card,
            text="✕",
            width=28, height=26, corner_radius=6,
            fg_color="transparent", border_width=1, border_color="#71322E",
            text_color=COLORS["danger"], hover_color="#3B2223",
            command=lambda c_id=conn_id, nm=conn.get("name"): self._delete_conn(c_id, nm)
        )
        btn_del.pack(side="right", padx=(2, 8), pady=8)

        btn_edit = ctk.CTkButton(
            card,
            text="Edit",
            width=42, height=26, corner_radius=6,
            fg_color="#2A2C33", hover_color="#383B44",
            font=ctk.CTkFont(size=11),
            command=lambda c_id=conn_id: self._open_edit_db_dialog(c_id)
        )
        btn_edit.pack(side="right", padx=2, pady=8)

        btn_test = ctk.CTkButton(
            card,
            text="Test",
            width=42, height=26, corner_radius=6,
            fg_color="#18283E", hover_color="#223B5D",
            text_color="#60A5FA", border_width=1, border_color="#254A78",
            font=ctk.CTkFont(size=11),
            command=lambda c_id=conn_id: self._test_single_conn(c_id)
        )
        btn_test.pack(side="right", padx=2, pady=8)

        btn_single_run = ctk.CTkButton(
            card,
            text="Run",
            width=42, height=26, corner_radius=6,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda c_id=conn_id: self._run_query_on_single_conn(c_id)
        )
        btn_single_run.pack(side="right", padx=2, pady=8)

        # Cache item
        self.connection_cards[conn_id] = {
            "card": card,
            "chk_var": chk_var,
            "status_lbl": lbl_status,
            "data": conn,
            "name_lower": (conn.get("name") or "").lower(),
            "host_lower": (conn.get("host") or "").lower(),
            "ssh_host_lower": (conn.get("ssh_host") or "").lower(),
            "group": conn.get("group_name") or "Default",
            "is_visible": True,
        }

    def _on_conn_checked(self, conn_id: int):
        item = self.connection_cards.get(conn_id)
        if item:
            if item["chk_var"].get():
                self.selected_db_ids.add(conn_id)
            else:
                self.selected_db_ids.discard(conn_id)
        self._sync_check_all_state()
        self._update_blast_button_label()

    def _sync_check_all_state(self):
        visible_items = [item for item in self.connection_cards.values() if item["is_visible"]]
        if visible_items:
            all_chk = all(item["chk_var"].get() for item in visible_items)
            self.chk_all_var.set(all_chk)
        else:
            self.chk_all_var.set(False)

    def _toggle_check_all(self):
        is_chk = self.chk_all_var.get()
        for item in self.connection_cards.values():
            if item["is_visible"]:
                item["chk_var"].set(is_chk)
                c_id = item["data"]["id"]
                if is_chk:
                    self.selected_db_ids.add(c_id)
                else:
                    self.selected_db_ids.discard(c_id)
        self._update_blast_button_label()

    def _update_blast_button_label(self):
        visible_items = [item for item in self.connection_cards.values() if item["is_visible"]]
        total_visible = len(visible_items)
        selected_visible = len([item for item in visible_items if item["chk_var"].get()])

        if selected_visible > 0:
            self.btn_run_blast.configure(text=f"⚡ Run Blast ({selected_visible})")
            self.lbl_blast_status.configure(text=f"{selected_visible} of {total_visible} selected")
        else:
            self.btn_run_blast.configure(text="⚡ Run Blast (All)")
            self.lbl_blast_status.configure(text=f"All {total_visible} will run")

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
            item = self.connection_cards.pop(conn_id, None)
            if item:
                item["card"].destroy()
            self._sync_check_all_state()
            self._update_blast_button_label()
            self.lbl_db_title.configure(text=f"Databases ({len(self.connection_cards)})")
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
        item = self.connection_cards.get(conn_id)
        if not item:
            return
        lbl_status = item["status_lbl"]
        lbl_status.configure(text="Testing...", text_color=COLORS["warning"])

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
                    lbl_status.configure(text=f"✓ OK ({res['elapsed_ms']}ms)", text_color=COLORS["success"])
                    self._log_message(f"✓ [{name}] Connection SUCCESS ({res['elapsed_ms']}ms): {res['output'].strip()}\n")
                    messagebox.showinfo(
                        "Test Connection",
                        f"Koneksi ke '{name}' BERHASIL!\n\nResponse time: {res['elapsed_ms']} ms\nOutput:\n{res['output'].strip()}"
                    )
                else:
                    lbl_status.configure(text="✗ Error", text_color=COLORS["danger"])
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

        item = self.connection_cards.get(conn_id)
        if not item:
            return

        lbl_status = item["status_lbl"]
        lbl_status.configure(text="Running...", text_color=COLORS["warning"])

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
                    lbl_status.configure(text=f"✓ OK ({res['elapsed_ms']}ms)", text_color=COLORS["success"])
                    self._log_message(f"✓ Output:\n{res['output']}\nElapsed: {res['elapsed_ms']} ms\n")
                    self._cache_result(name, res)
                else:
                    lbl_status.configure(text="✗ Error", text_color=COLORS["danger"])
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
        checked_visible_ids = [
            item["data"]["id"]
            for item in self.connection_cards.values()
            if item["is_visible"] and item["chk_var"].get()
        ]

        if checked_visible_ids:
            target_ids = checked_visible_ids
        else:
            # Jika tidak ada yang dicentang, jalankan ke semua yang sedang visible
            target_ids = [
                item["data"]["id"]
                for item in self.connection_cards.values()
                if item["is_visible"]
            ]

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
            self._update_card_status(t["id"], "Pending...", COLORS["muted"])

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
                    self.after(0, lambda: self._update_card_status(c_id, "Running...", COLORS["warning"]))
                    self.after(0, lambda: self._log_message(f"[{datetime.now().strftime('%H:%M:%S')}] >> Blasting '{name}' ({target.get('host')})...\n"))

                    # Eksekusi di thread terpisah agar async loop tidak terblokir
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(None, run_db_query, target, query, 20)

                    elapsed = res.get("elapsed_ms", 0)
                    total_elapsed += elapsed

                    if res.get("success"):
                        success_count += 1
                        self.after(0, lambda: self._update_card_status(c_id, f"✓ OK ({elapsed}ms)", COLORS["success"]))
                        self.after(0, lambda: self._log_message(f"✓ [{name}] SUCCESS ({elapsed}ms):\n{res.get('output', '')}\n\n"))
                    else:
                        failed_count += 1
                        self.after(0, lambda: self._update_card_status(c_id, "✗ Error", COLORS["danger"]))
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

    def _update_card_status(self, conn_id: int, text: str, color: str):
        item = self.connection_cards.get(conn_id)
        if item:
            item["status_lbl"].configure(text=text, text_color=color)

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
