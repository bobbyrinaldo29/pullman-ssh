import asyncio
from datetime import datetime
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional
import uuid

import customtkinter as ctk

from theme import COLORS, get_color, apply_treeview_styles
from icons import get_icon, get_tk_image
from sftp_service import SFTPService
from ui.file_editor_dialog import FileEditorDialog
from terminal_launcher import launch_ssh_terminal, launch_local_terminal


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class SFTPTabSession:
    """Representasi satu tab koneksi/sesi file manager."""

    def __init__(self, tab_id: str, host: Optional[Dict[str, Any]] = None, local_path: Optional[str] = None):
        self.tab_id: str = tab_id
        self.host: Optional[Dict[str, Any]] = host
        self.category: str = (host.get("group_name") or "All Categories") if host else "All Categories"
        self.local_path: str = local_path or os.getcwd()
        self.local_items: List[Dict[str, Any]] = []
        self.local_sort_col: str = "name"
        self.local_sort_reverse: bool = False

        repo_path = (host.get("repo_path") or "").strip() if host else ""
        self.remote_path: str = repo_path or "/"
        self.remote_items: List[Dict[str, Any]] = []
        self.remote_sort_col: str = "name"
        self.remote_sort_reverse: bool = False

        self.is_connected: bool = False
        self.is_connecting: bool = False
        self.status_msg: str = "Pilih server lalu klik 'Connect' untuk membuka sesi SFTP."
        self.status_server: str = ""

    @property
    def title(self) -> str:
        if self.host:
            label = self.host.get("label") or self.host.get("hostname")
            if label:
                return label.strip()
        return "New Session"


class SFTPView(ctk.CTkFrame):
    """Tampilan Dual-Pane File Manager di dalam Pullman SSH (bergaya FileZilla & WinSCP):
    - Multi-Tab per koneksi server
    - Sisi Kiri: Local File Explorer (My Computer)
    - Sisi Kanan: Remote SFTP Explorer (Target Remote Server)
    - Transfer langsung dua arah (Upload dan Download).
    """

    def __init__(self, parent: ctk.CTk, db_manager: Any, on_data_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.app = parent
        self.db = db_manager
        self._on_data_changed = on_data_changed

        # Database & Server state
        self._all_hosts: List[Dict[str, Any]] = []
        self._groups: List[Dict[str, Any]] = []
        self._host_by_item_id: Dict[str, Dict[str, Any]] = {}
        self._current_host: Optional[Dict[str, Any]] = None
        self._is_connecting: bool = False
        self._is_connected: bool = False
        self._needs_refresh: bool = False

        # Local Site State
        self._local_path: str = os.getcwd()
        self._local_items: List[Dict[str, Any]] = []
        self._local_sort_col: str = "name"
        self._local_sort_reverse: bool = False

        # Remote Site State
        self._remote_path: str = "/"
        self._remote_items: List[Dict[str, Any]] = []
        self._remote_sort_col: str = "name"
        self._remote_sort_reverse: bool = False
        self._is_remote_busy: bool = False

        # Tabs State
        self._tabs: List[SFTPTabSession] = []
        self._active_tab_id: Optional[str] = None

        initial_tab = SFTPTabSession(tab_id=f"tab_{uuid.uuid4().hex[:6]}", local_path=self._local_path)
        self._tabs.append(initial_tab)
        self._active_tab_id = initial_tab.tab_id

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Main workspace at row 1

        self._setup_ui()
        self.refresh_hosts_list()
        self._load_local_dir(self._local_path)
        self._render_tabs()

    def mark_needs_refresh(self):
        """Tandai bahwa data host di database berubah."""
        if self.winfo_ismapped():
            self.refresh_hosts_list()
        else:
            self._needs_refresh = True

    def refresh_hosts_list(self):
        """Muat ulang daftar host dan grup dari database untuk host list sidebar."""
        self._needs_refresh = False
        self._all_hosts = self.db.get_all_hosts(decrypt_passwords=False)
        self._groups = self.db.get_groups()
        self._render_hosts_tree()

    def _render_hosts_tree(self):
        """Render pohon daftar host berdasarkan grup dan pencarian."""
        if not hasattr(self, "hosts_tree"):
            return
        query = self.host_search_var.get().strip().lower() if hasattr(self, "host_search_var") else ""
        self.hosts_tree.delete(*self.hosts_tree.get_children())
        self._host_by_item_id.clear()

        if query:
            filtered = [
                h for h in self._all_hosts
                if query in (h.get("label") or "").lower()
                or query in (h.get("hostname") or "").lower()
                or query in (h.get("username") or "").lower()
                or query in (h.get("group_name") or "").lower()
            ]
        else:
            filtered = list(self._all_hosts)

        self.lbl_hosts_count.configure(text=f" My hosts ({len(filtered)})")

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for h in filtered:
            grp = (h.get("group_name") or "Default").strip() or "Default"
            grouped.setdefault(grp, []).append(h)

        folder_icon = get_tk_image("folder", (13, 13), COLORS["accent"])
        terminal_icon = get_tk_image("terminal", (13, 13), COLORS["text_secondary"])

        active_node_id = None
        for grp_name, hosts in sorted(grouped.items(), key=lambda x: x[0].lower()):
            grp_node_id = f"grp_{grp_name}"
            self.hosts_tree.insert(
                "", "end",
                iid=grp_node_id,
                text=f"  {grp_name} ({len(hosts)})",
                image=folder_icon,
                open=True
            )
            for h in sorted(hosts, key=lambda x: (x.get("label") or x.get("hostname") or "").lower()):
                host_node_id = f"host_{h['id']}"
                label = h.get("label") or h.get("hostname") or f"Host #{h['id']}"
                self.hosts_tree.insert(
                    grp_node_id, "end",
                    iid=host_node_id,
                    text=f"  {label}",
                    image=terminal_icon
                )
                self._host_by_item_id[host_node_id] = h
                if self._current_host and self._current_host.get("id") == h["id"]:
                    active_node_id = host_node_id

        if active_node_id:
            try:
                self.hosts_tree.selection_set(active_node_id)
                self.hosts_tree.see(active_node_id)
            except Exception:
                pass

    def _get_active_host_config(self) -> Optional[Dict[str, Any]]:
        """Mengambil host aktif dengan credential dan password terdekripsi dari database."""
        host = self._current_host
        if not host:
            active_tab = self._get_active_tab()
            if active_tab and active_tab.host:
                host = active_tab.host
        if not host:
            return None
        if hasattr(self, "db") and host.get("id"):
            full = self.db.get_host_by_id(host["id"])
            if full:
                self._current_host = full
                return full
        return host

    def select_host(self, host: Dict[str, Any]):
        """Pilih target host tertentu secara terprogram (misal saat dibuka dari HostsView / klik host)."""
        host_id = host.get("id")
        if hasattr(self, "db") and host_id:
            full_host = self.db.get_host_by_id(host_id)
            if full_host:
                host = full_host

        existing_tab = next((t for t in self._tabs if t.host and t.host.get("id") == host_id), None)
        if existing_tab:
            existing_tab.host = host
            self._switch_to_tab(existing_tab.tab_id)
            if not self._is_connected:
                self._connect_to_selected_host()
            return

        active_tab = self._get_active_tab()
        if active_tab and not active_tab.is_connected and (not active_tab.host or active_tab.host.get("id") == host_id):
            active_tab.host = host
            active_tab.category = (host.get("group_name") or "All Categories").strip() or "All Categories"
            self._restore_tab_state(active_tab)
            self._connect_to_selected_host()
            self._render_tabs()
        else:
            self._add_new_tab(host=host)

    def on_theme_changed(self, mode: str):
        """Update styling Treeview dan context menu saat mode tampilan berubah."""
        apply_treeview_styles(mode)
        self._create_context_menus()
        self._update_action_buttons_state()
        self._render_tabs()
        self._render_hosts_tree()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        # 1. HEADER: Title & Connection Control Status
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)

        # Title
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")

        lbl_title = ctk.CTkLabel(
            title_box,
            text="File Manager",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=24, weight="bold")
        )
        lbl_title.pack(anchor="w")

        # Connection Control Box (Quick Connect / Disconnect + Badge)
        ctrl_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        ctrl_box.grid(row=0, column=1, sticky="e")

        self.btn_connect = ctk.CTkButton(
            ctrl_box,
            text=" Connect",
            image=get_icon("play", (13, 13), "#FFFFFF"),
            compound="left",
            width=96,
            height=32,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_connection
        )
        self.btn_connect.pack(side="left", padx=(0, 6))

        self.conn_badge = ctk.CTkLabel(
            ctrl_box,
            text="Disconnected",
            fg_color=COLORS["surface"],
            text_color=COLORS["muted"],
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            width=95,
            height=32
        )
        self.conn_badge.pack(side="left")

        # 2. MAIN WORKSPACE (Left: Target Server List Sidebar, Right: Active Session Pane)
        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.grid(row=1, column=0, sticky="nsew", pady=(0, 4))
        workspace.grid_columnconfigure(0, weight=0)
        workspace.grid_columnconfigure(1, weight=1)
        workspace.grid_rowconfigure(0, weight=1)

        # Left Column: Target Server List Sidebar
        self._build_host_sidebar(workspace)

        # Right Column: Active Session Container
        session_frame = ctk.CTkFrame(workspace, fg_color="transparent")
        session_frame.grid(row=0, column=1, sticky="nsew")
        session_frame.grid_columnconfigure(0, weight=1)
        session_frame.grid_rowconfigure(1, weight=1)

        # 2a. Browser Tab Bar Container
        self.tab_bar_frame = ctk.CTkFrame(session_frame, fg_color="transparent", height=34)
        self.tab_bar_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.tab_bar_frame.grid_columnconfigure(0, weight=1)

        self.tab_items_box = ctk.CTkFrame(self.tab_bar_frame, fg_color="transparent")
        self.tab_items_box.grid(row=0, column=0, sticky="w")

        tab_border = ctk.CTkFrame(self.tab_bar_frame, fg_color=COLORS["line"], height=1)
        tab_border.grid(row=1, column=0, sticky="ew", pady=(0, 0))

        # 2b. Dual-Pane Container (Local Site on Left, Remote Site on Right)
        dual_pane = ctk.CTkFrame(session_frame, fg_color="transparent")
        dual_pane.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        dual_pane.grid_columnconfigure(0, weight=1)
        dual_pane.grid_columnconfigure(1, weight=1)
        dual_pane.grid_rowconfigure(0, weight=1)

        # Build Left Pane (Local File Explorer)
        self._build_local_pane(dual_pane)

        # Build Right Pane (Remote SFTP File Explorer)
        self._build_remote_pane(dual_pane)

        # 2c. Bottom Status Bar
        status_bar = ctk.CTkFrame(session_frame, fg_color=COLORS["surface"], corner_radius=8, height=32, border_width=1, border_color=COLORS["line"])
        status_bar.grid(row=2, column=0, sticky="ew")
        status_bar.grid_columnconfigure(1, weight=1)

        self.lbl_status_msg = ctk.CTkLabel(
            status_bar,
            text="Pilih server lalu klik 'Connect' untuk membuka sesi SFTP.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11)
        )
        self.lbl_status_msg.grid(row=0, column=0, padx=12, pady=4, sticky="w")

        self.lbl_status_server = ctk.CTkLabel(
            status_bar,
            text="",
            text_color=COLORS["accent_text"],
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_status_server.grid(row=0, column=2, padx=12, pady=4, sticky="e")

        self._create_context_menus()
        self._update_action_buttons_state()

    # ------------------------------------------------------------------
    # Left Sidebar: Target Server List
    # ------------------------------------------------------------------

    def _build_host_sidebar(self, parent: ctk.CTkFrame):
        host_sidebar = ctk.CTkFrame(parent, fg_color=COLORS["surface"], width=230, corner_radius=10, border_width=1, border_color=COLORS["line"])
        host_sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        host_sidebar.grid_columnconfigure(0, weight=1)
        host_sidebar.grid_rowconfigure(2, weight=1)

        # Header Title & Count
        title_box = ctk.CTkFrame(host_sidebar, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        title_box.grid_columnconfigure(0, weight=1)

        self.lbl_hosts_count = ctk.CTkLabel(
            title_box,
            text=" My hosts (0)",
            image=get_icon("folder", (14, 14), COLORS["accent"]),
            compound="left",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_hosts_count.grid(row=0, column=0, sticky="w")

        btn_refresh_hosts = ctk.CTkButton(
            title_box,
            text="",
            image=get_icon("refresh-cw", (12, 12), COLORS["muted"]),
            width=24,
            height=24,
            corner_radius=6,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            command=self.refresh_hosts_list
        )
        btn_refresh_hosts.grid(row=0, column=1, sticky="e")

        # Search box
        search_box = ctk.CTkFrame(host_sidebar, fg_color="transparent")
        search_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        search_box.grid_columnconfigure(0, weight=1)

        self.host_search_var = ctk.StringVar()
        self.host_search_entry = ctk.CTkEntry(
            search_box,
            placeholder_text="Search hosts...",
            textvariable=self.host_search_var,
            height=26,
            corner_radius=6,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["line"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=11)
        )
        self.host_search_entry.grid(row=0, column=0, sticky="ew")
        self.host_search_entry.bind("<KeyRelease>", lambda e: self._render_hosts_tree())

        # Host Treeview Container
        tree_container = ctk.CTkFrame(host_sidebar, fg_color=COLORS["input_bg"], border_width=1, border_color=COLORS["line"], corner_radius=6)
        tree_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        self.hosts_tree = ttk.Treeview(
            tree_container,
            show="tree",
            style="Pullman.Treeview",
            selectmode="browse"
        )
        self.hosts_tree.column("#0", width=200, minwidth=120, anchor="w")

        hosts_vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.hosts_tree.yview)
        self.hosts_tree.configure(yscrollcommand=hosts_vsb.set)

        self.hosts_tree.grid(row=0, column=0, sticky="nsew")
        hosts_vsb.grid(row=0, column=1, sticky="ns")

        self.hosts_tree.bind("<<TreeviewSelect>>", self._on_host_tree_select)
        self.hosts_tree.bind("<Double-1>", self._on_host_tree_double_click)
        self.hosts_tree.bind("<Return>", lambda e: self._on_host_tree_double_click(None))
        self.hosts_tree.bind("<Button-3>", self._show_host_tree_context_menu)

    def _on_host_tree_select(self, event=None):
        sel = self.hosts_tree.selection()
        if not sel:
            return
        node_id = sel[0]
        raw_host = self._host_by_item_id.get(node_id)
        if raw_host:
            full_host = self.db.get_host_by_id(raw_host["id"]) if hasattr(self, "db") else raw_host
            host = full_host or raw_host
            self._current_host = host
            active_tab = self._get_active_tab()
            if active_tab and not self._is_connected:
                active_tab.host = host
                repo_path = (host.get("repo_path") or "").strip() or "/var/www/html"
                active_tab.remote_path = repo_path
                self._remote_path = repo_path
                self.remote_path_var.set(repo_path)
                self.lbl_status_server.configure(text=f"{host['label']} ({host['hostname']})")
                self._render_tabs()

    def _on_host_tree_double_click(self, event=None):
        sel = self.hosts_tree.selection()
        if not sel:
            return
        node_id = sel[0]
        host = self._host_by_item_id.get(node_id)
        if host:
            self.select_host(host)

    def _show_host_tree_context_menu(self, event):
        item_id = self.hosts_tree.identify_row(event.y)
        if item_id:
            self.hosts_tree.selection_set(item_id)
        sel = self.hosts_tree.selection()
        host = self._host_by_item_id.get(sel[0]) if sel else None

        self.host_tree_menu.delete(0, "end")
        if host:
            label = host.get("label") or host.get("hostname")
            self.host_tree_menu.add_command(
                label=f"  Connect to {label}",
                image=get_tk_image("play", (13, 13), COLORS["accent"]),
                compound="left",
                command=lambda: self.select_host(host)
            )
            self.host_tree_menu.add_command(
                label="  Open in New Tab",
                image=get_tk_image("plus", (13, 13), COLORS["text"]),
                compound="left",
                command=lambda: self._add_new_tab(host=host)
            )
            self.host_tree_menu.add_separator()
            self.host_tree_menu.add_command(
                label="  Open SSH Terminal",
                image=get_tk_image("terminal", (13, 13), COLORS["text"]),
                compound="left",
                command=lambda h=host: self._open_terminal_for_host(h)
            )
            target_str = f"{host.get('username', 'root')}@{host.get('hostname')}:{host.get('port', 22)}"
            self.host_tree_menu.add_command(
                label="  Copy Target (user@host:port)",
                image=get_tk_image("copy", (13, 13), COLORS["text_secondary"]),
                compound="left",
                command=lambda: self._copy_clipboard(target_str, "Target server")
            )
            self.host_tree_menu.add_separator()

        self.host_tree_menu.add_command(
            label="  Refresh Hosts",
            image=get_tk_image("refresh-cw", (13, 13), COLORS["text"]),
            compound="left",
            command=self.refresh_hosts_list
        )

        try:
            self.host_tree_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.host_tree_menu.grab_release()

    # ------------------------------------------------------------------
    # Left Pane: Local File Explorer
    # ------------------------------------------------------------------

    def _build_local_pane(self, parent: ctk.CTkFrame):
        local_frame = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        local_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        local_frame.grid_columnconfigure(0, weight=1)
        local_frame.grid_rowconfigure(2, weight=1)

        # Header Title
        title_box = ctk.CTkFrame(local_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        title_box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            title_box,
            text=" Local Site (My Computer)",
            image=get_icon("laptop", (15, 15), COLORS["text"]),
            compound="left",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        self.lbl_local_count = ctk.CTkLabel(
            title_box,
            text="0 items",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11)
        )
        self.lbl_local_count.grid(row=0, column=1, sticky="e")

        # Local Nav Bar (Path & Buttons)
        nav_box = ctk.CTkFrame(local_frame, fg_color="transparent")
        nav_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        nav_box.grid_columnconfigure(2, weight=1)

        btn_box = ctk.CTkFrame(nav_box, fg_color="transparent")
        btn_box.grid(row=0, column=0, sticky="w", padx=(0, 6))

        btn_up = ctk.CTkButton(
            btn_box, text="", image=get_icon("arrow-up", (13, 13), COLORS["text"]),
            width=28, height=28, corner_radius=6, fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=self._nav_local_up
        )
        btn_up.pack(side="left", padx=(0, 3))

        btn_home = ctk.CTkButton(
            btn_box, text="", image=get_icon("house", (13, 13), COLORS["text"]),
            width=28, height=28, corner_radius=6, fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=self._nav_local_home
        )
        btn_home.pack(side="left", padx=(0, 3))

        btn_local_term = ctk.CTkButton(
            btn_box, text="", image=get_icon("terminal", (13, 13), COLORS["text"]),
            width=28, height=28, corner_radius=6, fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=lambda: self._action_open_local_terminal()
        )
        btn_local_term.pack(side="left", padx=(0, 3))

        self.local_path_var = ctk.StringVar(value=self._local_path)
        self.local_path_entry = ctk.CTkEntry(
            nav_box,
            textvariable=self.local_path_var,
            height=28,
            corner_radius=6,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["line"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(family="Courier", size=11)
        )
        self.local_path_entry.grid(row=0, column=2, sticky="ew", padx=(0, 4))
        self.local_path_entry.bind("<Return>", lambda e: self._load_local_dir(self.local_path_var.get()))

        btn_go = ctk.CTkButton(
            nav_box, text="Go", width=36, height=28, corner_radius=6,
            fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            text_color=COLORS["text"], font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._load_local_dir(self.local_path_var.get())
        )
        btn_go.grid(row=0, column=3, padx=(0, 3))

        btn_refresh = ctk.CTkButton(
            nav_box, text="", image=get_icon("refresh-cw", (13, 13), COLORS["text"]),
            width=28, height=28, corner_radius=6, fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=lambda: self._load_local_dir(self._local_path)
        )
        btn_refresh.grid(row=0, column=4)

        # Local Table Explorer
        table_container = ctk.CTkFrame(local_frame, fg_color=COLORS["input_bg"], border_width=1, border_color=COLORS["line"], corner_radius=6)
        table_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 6))
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        self.local_tree = ttk.Treeview(
            table_container,
            columns=("size", "modified"),
            show="tree headings",
            style="Pullman.Treeview",
            selectmode="extended"
        )
        self.local_tree.heading("#0", text="Local Filename", anchor="w", command=lambda: self._sort_local_by("name"))
        self.local_tree.heading("size", text="Size", anchor="e", command=lambda: self._sort_local_by("size_bytes"))
        self.local_tree.heading("modified", text="Date Modified", anchor="w", command=lambda: self._sort_local_by("mtime"))

        self.local_tree.column("#0", width=220, minwidth=140, anchor="w")
        self.local_tree.column("size", width=85, minwidth=70, anchor="e")
        self.local_tree.column("modified", width=140, minwidth=110, anchor="w")

        local_vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.local_tree.yview)
        self.local_tree.configure(yscrollcommand=local_vsb.set)

        self.local_tree.grid(row=0, column=0, sticky="nsew")
        local_vsb.grid(row=0, column=1, sticky="ns")

        self.local_tree.bind("<Double-Button-1>", self._on_local_double_click)
        self.local_tree.bind("<Button-3>", self._show_local_context_menu)
        self.local_tree.bind("<<TreeviewSelect>>", lambda e: self._update_action_buttons_state())

        # Local Action Buttons Toolbar
        action_bar = ctk.CTkFrame(local_frame, fg_color="transparent")
        action_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 8))

        self.btn_local_upload = ctk.CTkButton(
            action_bar,
            text=" Upload",
            image=get_icon("upload", (12, 12), "#FFFFFF"),
            compound="left",
            height=26,
            corner_radius=6,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._action_upload_selected_local
        )
        self.btn_local_upload.pack(side="left", padx=(0, 4))

        btn_new_file = ctk.CTkButton(
            action_bar, text=" New File", image=get_icon("file-plus", (12, 12), COLORS["text"]),
            compound="left", height=26, corner_radius=6, fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"], text_color=COLORS["text"], font=ctk.CTkFont(size=11),
            command=self._action_local_new_file
        )
        btn_new_file.pack(side="left", padx=(0, 4))

        btn_new_folder = ctk.CTkButton(
            action_bar, text=" New Folder", image=get_icon("folder-tree", (12, 12), COLORS["text"]),
            compound="left", height=26, corner_radius=6, fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"], text_color=COLORS["text"], font=ctk.CTkFont(size=11),
            command=self._action_local_new_folder
        )
        btn_new_folder.pack(side="left", padx=(0, 4))

        btn_local_term_bar = ctk.CTkButton(
            action_bar, text=" Terminal", image=get_icon("terminal", (12, 12), COLORS["text"]),
            compound="left", height=26, corner_radius=6, fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"], text_color=COLORS["text"], font=ctk.CTkFont(size=11),
            command=lambda: self._action_open_local_terminal()
        )
        btn_local_term_bar.pack(side="left", padx=(0, 4))

        self.btn_local_del = ctk.CTkButton(
            action_bar, text=" Delete", image=get_icon("trash", (12, 12), COLORS["danger_text"]),
            compound="left", height=26, corner_radius=6, fg_color=COLORS["danger_subtle"],
            border_width=1, border_color=COLORS["danger_border"], text_color=COLORS["danger_text"],
            hover_color=COLORS["danger_hover"], font=ctk.CTkFont(size=11),
            command=self._action_local_delete
        )
        self.btn_local_del.pack(side="left")

    # ------------------------------------------------------------------
    # Right Pane: Remote SFTP Explorer
    # ------------------------------------------------------------------

    def _build_remote_pane(self, parent: ctk.CTkFrame):
        remote_frame = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        remote_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        remote_frame.grid_columnconfigure(0, weight=1)
        remote_frame.grid_rowconfigure(2, weight=1)

        # Header Title
        title_box = ctk.CTkFrame(remote_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        title_box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            title_box,
            text=" Remote Site (SFTP Server)",
            image=get_icon("server", (15, 15), COLORS["accent_text"]),
            compound="left",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        self.lbl_remote_count = ctk.CTkLabel(
            title_box,
            text="0 items",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11)
        )
        self.lbl_remote_count.grid(row=0, column=1, sticky="e")

        # Remote Nav Bar (Path & Buttons)
        nav_box = ctk.CTkFrame(remote_frame, fg_color="transparent")
        nav_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        nav_box.grid_columnconfigure(3, weight=1)

        btn_box = ctk.CTkFrame(nav_box, fg_color="transparent")
        btn_box.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.btn_remote_up = ctk.CTkButton(
            btn_box, text="", image=get_icon("arrow-up", (13, 13), COLORS["text"]),
            width=28, height=28, corner_radius=6, fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=self._nav_remote_up
        )
        self.btn_remote_up.pack(side="left", padx=(0, 3))

        self.btn_remote_home = ctk.CTkButton(
            btn_box, text="", image=get_icon("house", (13, 13), COLORS["text"]),
            width=28, height=28, corner_radius=6, fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=self._nav_remote_home
        )
        self.btn_remote_home.pack(side="left", padx=(0, 3))

        self.btn_remote_repo = ctk.CTkButton(
            btn_box, text=" Repo", image=get_icon("folder", (12, 12), COLORS["text"]),
            compound="left", height=28, corner_radius=6, fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"], text_color=COLORS["text"], font=ctk.CTkFont(size=11),
            command=self._nav_remote_repo
        )
        self.btn_remote_repo.pack(side="left", padx=(0, 3))

        self.btn_remote_terminal = ctk.CTkButton(
            btn_box, text=" SSH", image=get_icon("terminal", (12, 12), COLORS["accent_text"]),
            compound="left", height=28, corner_radius=6, fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"], text_color=COLORS["accent_text"], font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._action_open_remote_terminal()
        )
        self.btn_remote_terminal.pack(side="left", padx=(0, 3))

        self.remote_path_var = ctk.StringVar(value="/")
        self.remote_path_entry = ctk.CTkEntry(
            nav_box,
            textvariable=self.remote_path_var,
            height=28,
            corner_radius=6,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["line"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(family="Courier", size=11)
        )
        self.remote_path_entry.grid(row=0, column=3, sticky="ew", padx=(0, 4))
        self.remote_path_entry.bind("<Return>", lambda e: self._navigate_remote_to(self.remote_path_var.get()))

        self.btn_remote_go = ctk.CTkButton(
            nav_box, text="Go", width=36, height=28, corner_radius=6,
            fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            text_color=COLORS["text"], font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._navigate_remote_to(self.remote_path_var.get())
        )
        self.btn_remote_go.grid(row=0, column=4, padx=(0, 3))

        self.btn_remote_refresh = ctk.CTkButton(
            nav_box, text="", image=get_icon("refresh-cw", (13, 13), COLORS["text"]),
            width=28, height=28, corner_radius=6, fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=self._refresh_remote_current_dir
        )
        self.btn_remote_refresh.grid(row=0, column=5)

        # Remote Table Explorer
        table_container = ctk.CTkFrame(remote_frame, fg_color=COLORS["input_bg"], border_width=1, border_color=COLORS["line"], corner_radius=6)
        table_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 6))
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        self.remote_tree = ttk.Treeview(
            table_container,
            columns=("size", "permissions", "modified"),
            show="tree headings",
            style="Pullman.Treeview",
            selectmode="extended"
        )
        self.remote_tree.heading("#0", text="Remote Filename", anchor="w", command=lambda: self._sort_remote_by("name"))
        self.remote_tree.heading("size", text="Size", anchor="e", command=lambda: self._sort_remote_by("size_bytes"))
        self.remote_tree.heading("permissions", text="Perms", anchor="center", command=lambda: self._sort_remote_by("permissions"))
        self.remote_tree.heading("modified", text="Date Modified", anchor="w", command=lambda: self._sort_remote_by("mtime"))

        self.remote_tree.column("#0", width=200, minwidth=130, anchor="w")
        self.remote_tree.column("size", width=80, minwidth=65, anchor="e")
        self.remote_tree.column("permissions", width=75, minwidth=60, anchor="center")
        self.remote_tree.column("modified", width=135, minwidth=105, anchor="w")

        remote_vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.remote_tree.yview)
        self.remote_tree.configure(yscrollcommand=remote_vsb.set)

        self.remote_tree.grid(row=0, column=0, sticky="nsew")
        remote_vsb.grid(row=0, column=1, sticky="ns")

        self.remote_tree.bind("<Double-Button-1>", self._on_remote_double_click)
        self.remote_tree.bind("<Button-3>", self._show_remote_context_menu)
        self.remote_tree.bind("<<TreeviewSelect>>", lambda e: self._update_action_buttons_state())

        # Remote Action Buttons Toolbar
        action_bar = ctk.CTkFrame(remote_frame, fg_color="transparent")
        action_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 8))

        self.btn_remote_download = ctk.CTkButton(
            action_bar,
            text=" Download",
            image=get_icon("download", (12, 12), "#FFFFFF"),
            compound="left",
            height=26,
            corner_radius=6,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._action_download_selected_remote
        )
        self.btn_remote_download.pack(side="left", padx=(0, 4))

        self.btn_remote_edit = ctk.CTkButton(
            action_bar, text=" Edit Remote", image=get_icon("pencil", (12, 12), COLORS["text"]),
            compound="left", height=26, corner_radius=6, fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"], text_color=COLORS["text"], font=ctk.CTkFont(size=11),
            command=self._action_edit_file
        )
        self.btn_remote_edit.pack(side="left", padx=(0, 4))

        self.btn_remote_new_file = ctk.CTkButton(
            action_bar, text=" New File", image=get_icon("file-plus", (12, 12), COLORS["text"]),
            compound="left", height=26, corner_radius=6, fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"], text_color=COLORS["text"], font=ctk.CTkFont(size=11),
            command=self._action_new_file
        )
        self.btn_remote_new_file.pack(side="left", padx=(0, 4))

        self.btn_remote_new_folder = ctk.CTkButton(
            action_bar, text=" New Folder", image=get_icon("folder-tree", (12, 12), COLORS["text"]),
            compound="left", height=26, corner_radius=6, fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"], text_color=COLORS["text"], font=ctk.CTkFont(size=11),
            command=self._action_new_dir
        )
        self.btn_remote_new_folder.pack(side="left", padx=(0, 4))

        self.btn_remote_terminal_action = ctk.CTkButton(
            action_bar, text=" SSH Terminal", image=get_icon("terminal", (12, 12), COLORS["text"]),
            compound="left", height=26, corner_radius=6, fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"], text_color=COLORS["text"], font=ctk.CTkFont(size=11),
            command=lambda: self._action_open_remote_terminal()
        )
        self.btn_remote_terminal_action.pack(side="left", padx=(0, 4))

        self.btn_remote_del = ctk.CTkButton(
            action_bar, text=" Delete", image=get_icon("trash", (12, 12), COLORS["danger_text"]),
            compound="left", height=26, corner_radius=6, fg_color=COLORS["danger_subtle"],
            border_width=1, border_color=COLORS["danger_border"], text_color=COLORS["danger_text"],
            hover_color=COLORS["danger_hover"], font=ctk.CTkFont(size=11),
            command=self._action_delete
        )
        self.btn_remote_del.pack(side="left")

    # ------------------------------------------------------------------
    # Context Menus
    # ------------------------------------------------------------------

    def _create_context_menus(self):
        self.host_tree_menu = tk.Menu(
            self, tearoff=0, bg=get_color("surface"), fg=get_color("text"),
            activebackground=get_color("accent"), activeforeground="#FFFFFF", bd=1
        )
        self.local_context_menu = tk.Menu(
            self, tearoff=0, bg=get_color("surface"), fg=get_color("text"),
            activebackground=get_color("accent"), activeforeground="#FFFFFF", bd=1
        )
        self.remote_context_menu = tk.Menu(
            self, tearoff=0, bg=get_color("surface"), fg=get_color("text"),
            activebackground=get_color("accent"), activeforeground="#FFFFFF", bd=1
        )

    def _show_local_context_menu(self, event):
        item_id = self.local_tree.identify_row(event.y)
        if item_id:
            if not self.local_tree.selection() or item_id not in self.local_tree.selection():
                self.local_tree.selection_set(item_id)
            self._update_action_buttons_state()

        sel = self.local_tree.selection()
        item = self._get_local_item_by_name(sel[0]) if sel else None

        self.local_context_menu.delete(0, "end")
        if item:
            if item.get("is_dir"):
                self.local_context_menu.add_command(
                    label="  Open Folder",
                    image=get_tk_image("folder-tree", (14, 14), COLORS["text"]),
                    compound="left",
                    command=lambda: self._load_local_dir(item["path"])
                )
                self.local_context_menu.add_command(
                    label="  Open Terminal in Here",
                    image=get_tk_image("terminal", (14, 14), COLORS["text"]),
                    compound="left",
                    command=lambda p=item["path"]: self._action_open_local_terminal(p)
                )
            else:
                self.local_context_menu.add_command(
                    label="  Open with Default App",
                    image=get_tk_image("eye", (14, 14), COLORS["text"]),
                    compound="left",
                    command=lambda: self._open_local_file(item["path"])
                )
                self.local_context_menu.add_command(
                    label="  Open Terminal in Folder",
                    image=get_tk_image("terminal", (14, 14), COLORS["text"]),
                    compound="left",
                    command=lambda p=os.path.dirname(item["path"]): self._action_open_local_terminal(p)
                )

            if self._is_connected:
                self.local_context_menu.add_command(
                    label="  Upload to Remote",
                    image=get_tk_image("upload", (14, 14), COLORS["accent_text"]),
                    compound="left",
                    command=self._action_upload_selected_local
                )

            self.local_context_menu.add_separator()
            self.local_context_menu.add_command(
                label="  Copy Local Path",
                image=get_tk_image("copy", (14, 14), COLORS["text_secondary"]),
                compound="left",
                command=lambda: self._copy_clipboard(item["path"], "Local path")
            )
            self.local_context_menu.add_command(
                label="  Rename...",
                image=get_tk_image("pencil", (14, 14), COLORS["text_secondary"]),
                compound="left",
                command=self._action_local_rename
            )
            self.local_context_menu.add_command(
                label="  Delete",
                image=get_tk_image("trash", (14, 14), COLORS["danger_text"]),
                compound="left",
                command=self._action_local_delete
            )
            self.local_context_menu.add_separator()

        self.local_context_menu.add_command(
            label="  Open Terminal in Here",
            image=get_tk_image("terminal", (14, 14), COLORS["text"]),
            compound="left",
            command=lambda: self._action_open_local_terminal(self._local_path)
        )
        self.local_context_menu.add_command(
            label="  New File...",
            image=get_tk_image("file-plus", (14, 14), COLORS["text"]),
            compound="left",
            command=self._action_local_new_file
        )
        self.local_context_menu.add_command(
            label="  New Folder...",
            image=get_tk_image("folder-tree", (14, 14), COLORS["text"]),
            compound="left",
            command=self._action_local_new_folder
        )
        self.local_context_menu.add_separator()
        self.local_context_menu.add_command(
            label="  Refresh",
            image=get_tk_image("refresh-cw", (14, 14), COLORS["text"]),
            compound="left",
            command=lambda: self._load_local_dir(self._local_path)
        )

        try:
            self.local_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.local_context_menu.grab_release()

    def _show_remote_context_menu(self, event):
        item_id = self.remote_tree.identify_row(event.y)
        if item_id:
            if not self.remote_tree.selection() or item_id not in self.remote_tree.selection():
                self.remote_tree.selection_set(item_id)
            self._update_action_buttons_state()

        sel = self.remote_tree.selection()
        item = self._get_remote_item_by_name(sel[0]) if sel else None

        self.remote_context_menu.delete(0, "end")
        if item:
            if item.get("is_dir"):
                self.remote_context_menu.add_command(
                    label="  Open Directory",
                    image=get_tk_image("folder-tree", (14, 14), COLORS["text"]),
                    compound="left",
                    command=lambda: self._navigate_remote_to(item["path"])
                )
                self.remote_context_menu.add_command(
                    label="  Open Terminal in Here (SSH)",
                    image=get_tk_image("terminal", (14, 14), COLORS["accent_text"]),
                    compound="left",
                    command=lambda p=item["path"]: self._action_open_remote_terminal(p)
                )
            else:
                self.remote_context_menu.add_command(
                    label="  Edit Remote File",
                    image=get_tk_image("eye", (14, 14), COLORS["text"]),
                    compound="left",
                    command=lambda: self._action_edit_file(as_sudo=False)
                )
                self.remote_context_menu.add_command(
                    label="  Edit as sudo...",
                    image=get_tk_image("shield", (14, 14), COLORS["danger_text"]),
                    compound="left",
                    command=lambda: self._action_edit_file(as_sudo=True)
                )
                self.remote_context_menu.add_command(
                    label="  Open Terminal in Folder (SSH)",
                    image=get_tk_image("terminal", (14, 14), COLORS["accent_text"]),
                    compound="left",
                    command=lambda p=os.path.dirname(item["path"]): self._action_open_remote_terminal(p)
                )
            self.remote_context_menu.add_command(
                label="  Download to Current Local Folder",
                image=get_tk_image("download", (14, 14), COLORS["accent_text"]),
                compound="left",
                command=self._action_download_selected_remote
            )
            self.remote_context_menu.add_separator()
            self.remote_context_menu.add_command(
                label="  Copy Remote Path",
                image=get_tk_image("copy", (14, 14), COLORS["text_secondary"]),
                compound="left",
                command=lambda: self._copy_clipboard(item["path"], "Remote path")
            )
            self.remote_context_menu.add_command(
                label="  Rename...",
                image=get_tk_image("pencil", (14, 14), COLORS["text_secondary"]),
                compound="left",
                command=self._action_rename
            )
            self.remote_context_menu.add_command(
                label="  Delete",
                image=get_tk_image("trash", (14, 14), COLORS["danger_text"]),
                compound="left",
                command=self._action_delete
            )
            self.remote_context_menu.add_separator()

        if self._is_connected:
            self.remote_context_menu.add_command(
                label="  Open Terminal in Here (SSH)",
                image=get_tk_image("terminal", (14, 14), COLORS["accent_text"]),
                compound="left",
                command=lambda: self._action_open_remote_terminal(self._remote_path)
            )
        self.remote_context_menu.add_command(
            label="  New File...",
            image=get_tk_image("file-plus", (14, 14), COLORS["text"]),
            compound="left",
            command=self._action_new_file
        )
        self.remote_context_menu.add_command(
            label="  New Folder...",
            image=get_tk_image("folder-tree", (14, 14), COLORS["text"]),
            compound="left",
            command=self._action_new_dir
        )
        self.remote_context_menu.add_separator()
        self.remote_context_menu.add_command(
            label="  Refresh",
            image=get_tk_image("refresh-cw", (14, 14), COLORS["text"]),
            compound="left",
            command=self._refresh_remote_current_dir
        )

        try:
            self.remote_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.remote_context_menu.grab_release()

    def _copy_clipboard(self, text: str, label: str):
        try:
            self.app.clipboard_clear()
            self.app.clipboard_append(text)
            self._set_status(f"{label} disalin ke clipboard: {text}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Local Operations (List, Nav, Create, Delete, Rename)
    # ------------------------------------------------------------------

    def _load_local_dir(self, target_path: str):
        target_path = os.path.abspath(target_path)
        if not os.path.exists(target_path):
            target_path = os.path.expanduser("~")

        self._local_path = target_path
        self.local_path_var.set(self._local_path)
        self._local_items = []

        try:
            with os.scandir(self._local_path) as it:
                for entry in it:
                    try:
                        st = entry.stat()
                        is_dir = entry.is_dir()
                        size = st.st_size if not is_dir else 0
                        mtime = st.st_mtime
                        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                        
                        self._local_items.append({
                            "name": entry.name,
                            "path": entry.path,
                            "is_dir": is_dir,
                            "size_bytes": size,
                            "size_str": "-" if is_dir else _format_size(size),
                            "mtime": mtime,
                            "mtime_str": mtime_str
                        })
                    except (PermissionError, FileNotFoundError):
                        continue
        except Exception as e:
            self._set_status(f"Gagal membaca folder lokal: {e}")

        self._render_local_table()

    def _render_local_table(self):
        self.local_tree.delete(*self.local_tree.get_children())

        def sort_key(item: Dict[str, Any]):
            is_folder = 0 if item.get("is_dir") else 1
            if self._local_sort_col == "name":
                val = item.get("name", "").lower()
            elif self._local_sort_col == "size_bytes":
                val = item.get("size_bytes", 0)
            elif self._local_sort_col == "mtime":
                val = item.get("mtime", 0)
            else:
                val = item.get("name", "").lower()
            return (is_folder, val)

        sorted_items = sorted(self._local_items, key=sort_key, reverse=self._local_sort_reverse)
        dir_count = sum(1 for x in sorted_items if x.get("is_dir"))
        file_count = len(sorted_items) - dir_count

        for item in sorted_items:
            is_dir = item.get("is_dir", False)
            icon = get_tk_image("folder" if is_dir else "file", (14, 14), COLORS["accent"] if is_dir else COLORS["text_secondary"])
            self.local_tree.insert(
                "", "end",
                iid=item.get("name"),
                text=f"  {item.get('name')}",
                image=icon,
                values=(item.get("size_str", "-"), item.get("mtime_str", ""))
            )

        self.lbl_local_count.configure(text=f"{len(sorted_items)} items ({dir_count} f, {file_count} fl)")
        self._update_action_buttons_state()

    def _sort_local_by(self, col: str):
        if self._local_sort_col == col:
            self._local_sort_reverse = not self._local_sort_reverse
        else:
            self._local_sort_col = col
            self._local_sort_reverse = False
        self._render_local_table()

    def _nav_local_up(self):
        parent = os.path.dirname(self._local_path.rstrip("/\\"))
        if parent and parent != self._local_path:
            self._load_local_dir(parent)

    def _nav_local_home(self):
        self._load_local_dir(os.path.expanduser("~"))

    def _get_local_item_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return next((it for it in self._local_items if it.get("name") == name), None)

    def _on_local_double_click(self, event):
        item_id = self.local_tree.identify_row(event.y)
        if not item_id:
            return
        item = self._get_local_item_by_name(item_id)
        if not item:
            return
        if item.get("is_dir"):
            self._load_local_dir(item["path"])
        else:
            if self._is_connected:
                # Jika terhubung ke remote, double click mengunggah ke remote
                self._action_upload_single_local(item["path"])
            else:
                self._open_local_file(item["path"])

    def _open_local_file(self, path: str):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka file: {e}")

    def _action_local_new_file(self):
        dialog = ctk.CTkInputDialog(text="Nama file lokal baru:", title="New Local File")
        filename = dialog.get_input()
        if not filename or not filename.strip():
            return
        filepath = os.path.join(self._local_path, filename.strip())
        try:
            Path(filepath).touch()
            self._load_local_dir(self._local_path)
            self._set_status(f"File lokal '{filename}' berhasil dibuat.")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuat file lokal: {e}")

    def _action_local_new_folder(self):
        dialog = ctk.CTkInputDialog(text="Nama folder lokal baru:", title="New Local Folder")
        dirname = dialog.get_input()
        if not dirname or not dirname.strip():
            return
        dirpath = os.path.join(self._local_path, dirname.strip())
        try:
            os.makedirs(dirpath, exist_ok=True)
            self._load_local_dir(self._local_path)
            self._set_status(f"Folder lokal '{dirname}' berhasil dibuat.")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuat folder lokal: {e}")

    def _action_local_rename(self):
        sel = self.local_tree.selection()
        if not sel:
            return
        item = self._get_local_item_by_name(sel[0])
        if not item:
            return
        dialog = ctk.CTkInputDialog(text=f"Nama baru untuk '{item.get('name')}':", title="Rename Local Item")
        new_name = dialog.get_input()
        if not new_name or not new_name.strip() or new_name.strip() == item.get("name"):
            return
        new_path = os.path.join(self._local_path, new_name.strip())
        try:
            os.rename(item["path"], new_path)
            self._load_local_dir(self._local_path)
            self._set_status(f"Berhasil rename ke '{new_name}'.")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal rename: {e}")

    def _action_local_delete(self):
        sel = self.local_tree.selection()
        if not sel:
            return
        count = len(sel)
        names = ", ".join(sel[:3]) + (f" dan {count - 3} lainnya" if count > 3 else "")
        if not messagebox.askyesno("Hapus File Lokal", f"Yakin ingin menghapus {count} item ({names}) di komputer lokal?"):
            return
        for name in sel:
            item = self._get_local_item_by_name(name)
            if item:
                try:
                    if item.get("is_dir"):
                        shutil.rmtree(item["path"])
                    else:
                        os.remove(item["path"])
                except Exception:
                    pass
        self._load_local_dir(self._local_path)
        self._set_status(f"{count} item lokal telah dihapus.")

    # ------------------------------------------------------------------
    # Transfer Operations (Local ➔ Remote & Remote ➔ Local)
    # ------------------------------------------------------------------

    def _action_upload_selected_local(self):
        """Upload selected local files/folders directly to active remote directory."""
        if not self._is_connected or not self._current_host:
            messagebox.showinfo("Koneksi Diperlukan", "Hubungkan ke remote server terlebih dahulu.")
            return

        sel = self.local_tree.selection()
        if not sel:
            messagebox.showinfo("Pilih Item", "Pilih file atau folder lokal yang ingin diunggah.")
            return

        items = [self._get_local_item_by_name(n) for n in sel if self._get_local_item_by_name(n)]
        if not items:
            return

        self._set_status(f"Mengunggah {len(items)} item ke remote: {self._remote_path}...")

        def worker():
            host_cfg = self._get_active_host_config() or self._current_host
            total = 0
            for it in items:
                local_f = it["path"]
                fname = it["name"]
                remote_f = os.path.join(self._remote_path, fname).replace("\\", "/")
                
                if it.get("is_dir"):
                    # Folder upload
                    SFTPService.create_dir(host_cfg, remote_f)
                    for root, dirs, files in os.walk(local_f):
                        rel = os.path.relpath(root, local_f)
                        cur_rem = remote_f if rel == "." else os.path.join(remote_f, rel).replace("\\", "/")
                        SFTPService.create_dir(host_cfg, cur_rem)
                        for f in files:
                            lf = os.path.join(root, f)
                            rf = os.path.join(cur_rem, f).replace("\\", "/")
                            ok, _ = SFTPService.upload_file(host_cfg, lf, rf)
                            if ok:
                                total += 1
                else:
                    ok, _ = SFTPService.upload_file(host_cfg, local_f, remote_f)
                    if ok:
                        total += 1

            def on_done():
                self._set_status(f"Upload selesai ({total} file berhasil diunggah).")
                self._refresh_remote_current_dir()
            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _action_upload_single_local(self, local_file_path: str):
        fname = os.path.basename(local_file_path)
        remote_target = os.path.join(self._remote_path, fname).replace("\\", "/")
        self._set_status(f"Mengunggah '{fname}'...")

        def worker():
            host_cfg = self._get_active_host_config() or self._current_host
            ok, err = SFTPService.upload_file(host_cfg, local_file_path, remote_target)
            def on_done():
                if ok:
                    self._set_status(f"Berhasil mengunggah '{fname}'.")
                    self._refresh_remote_current_dir()
                else:
                    self._set_status(f"Gagal mengunggah: {err}")
                    messagebox.showerror("Upload Error", f"Gagal mengunggah:\n{err}")
            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _action_download_selected_remote(self):
        """Download selected remote files/folders directly to active local directory."""
        if not self._is_connected or not self._current_host:
            return

        sel = self.remote_tree.selection()
        if not sel:
            messagebox.showinfo("Pilih Item", "Pilih file remote yang ingin diunduh.")
            return

        items = [self._get_remote_item_by_name(n) for n in sel if self._get_remote_item_by_name(n)]
        if not items:
            return

        self._set_status(f"Mengunduh {len(items)} item ke lokal: {self._local_path}...")

        def worker():
            host_cfg = self._get_active_host_config() or self._current_host
            total = 0
            for it in items:
                if it.get("is_dir"):
                    # Download directory not yet supported directly, download files
                    continue
                remote_f = it["path"]
                local_f = os.path.join(self._local_path, it["name"])
                ok, _ = SFTPService.download_file(host_cfg, remote_f, local_f)
                if ok:
                    total += 1

            def on_done():
                self._set_status(f"Download selesai ({total} file berhasil diunduh).")
                self._load_local_dir(self._local_path)
            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Tab Management & Multi-Session
    # ------------------------------------------------------------------

    def _get_active_tab(self) -> Optional[SFTPTabSession]:
        for tab in self._tabs:
            if tab.tab_id == self._active_tab_id:
                return tab
        return self._tabs[0] if self._tabs else None

    def _render_tabs(self):
        """Render tab dengan desain modern seperti browser (Chrome / Arc / VS Code):
        - Favicon icon server di sebelah kiri
        - Tab card dengan sudut membulat (corner_radius=8)
        - Active tab dengan latar surface dan border elegan
        - Inactive tab dengan subtle divider dan hover effect
        - Tombol close 'x' dan tombol new tab '+' berbentuk sirkular
        """
        for widget in self.tab_items_box.winfo_children():
            widget.destroy()

        for idx, tab in enumerate(self._tabs):
            is_active = (tab.tab_id == self._active_tab_id)

            # Inactive divider before tab (jika bukan tab pertama dan tab sebelumnya tidak aktif)
            if idx > 0 and not is_active and (self._tabs[idx - 1].tab_id != self._active_tab_id):
                divider = ctk.CTkFrame(self.tab_items_box, width=1, height=16, fg_color=COLORS["line"])
                divider.pack(side="left", padx=(0, 4), pady=(6, 0))

            # Tab Card Container (Browser Tab Style)
            tab_frame = ctk.CTkFrame(
                self.tab_items_box,
                fg_color=COLORS["surface"] if is_active else "transparent",
                corner_radius=8,
                border_width=1 if is_active else 0,
                border_color=COLORS["line"],
                cursor="hand2"
            )
            tab_frame.pack(side="left", padx=(0, 4), pady=(2, 0))

            # Inner content
            content_frame = ctk.CTkFrame(tab_frame, fg_color="transparent", cursor="hand2")
            content_frame.pack(side="top", padx=(10, 6), pady=(4, 4))

            # 1. Favicon Icon (Server / Laptop icon)
            icon_color = COLORS["success"] if tab.is_connected else (COLORS["accent"] if is_active else COLORS["muted"])
            lbl_icon = ctk.CTkLabel(
                content_frame,
                text="",
                image=get_icon("server", (13, 13), icon_color),
                cursor="hand2",
                width=16
            )
            lbl_icon.pack(side="left", padx=(0, 6))

            # 2. Tab Title Label
            lbl_title = ctk.CTkLabel(
                content_frame,
                text=tab.title,
                text_color=COLORS["text"] if is_active else COLORS["muted"],
                font=ctk.CTkFont(size=12, weight="bold" if is_active else "normal"),
                cursor="hand2"
            )
            lbl_title.pack(side="left", padx=(0, 8))

            # 3. Close 'x' button (Browser style circular hover)
            btn_close = ctk.CTkButton(
                content_frame,
                text="",
                image=get_icon("x", (10, 10), COLORS["text"] if is_active else COLORS["muted"]),
                width=18,
                height=18,
                corner_radius=9,
                fg_color="transparent",
                hover_color=COLORS["danger_subtle"],
                command=lambda tid=tab.tab_id: self._close_tab(tid)
            )
            btn_close.pack(side="left")

            # Bind clicks to switch tab
            tab_frame.bind("<Button-1>", lambda e, tid=tab.tab_id: self._switch_to_tab(tid))
            content_frame.bind("<Button-1>", lambda e, tid=tab.tab_id: self._switch_to_tab(tid))
            lbl_icon.bind("<Button-1>", lambda e, tid=tab.tab_id: self._switch_to_tab(tid))
            lbl_title.bind("<Button-1>", lambda e, tid=tab.tab_id: self._switch_to_tab(tid))

            # Inactive Tab Hover effect
            if not is_active:
                def on_enter(e, tf=tab_frame):
                    tf.configure(fg_color=COLORS["surface_hover"])
                def on_leave(e, tf=tab_frame):
                    tf.configure(fg_color="transparent")
                tab_frame.bind("<Enter>", on_enter)
                tab_frame.bind("<Leave>", on_leave)
                content_frame.bind("<Enter>", on_enter)
                content_frame.bind("<Leave>", on_leave)
                lbl_title.bind("<Enter>", on_enter)
                lbl_title.bind("<Leave>", on_leave)

        # Plus '+' button to add new tab (Browser style rounded button)
        btn_add = ctk.CTkButton(
            self.tab_items_box,
            text="",
            image=get_icon("plus", (13, 13), COLORS["text"]),
            width=26,
            height=26,
            corner_radius=13,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            command=self._add_new_tab
        )
        btn_add.pack(side="left", padx=(4, 4), pady=(4, 0))

    def _save_current_tab_state(self):
        active_tab = self._get_active_tab()
        if not active_tab:
            return
        active_tab.host = self._current_host
        active_tab.local_path = self._local_path
        active_tab.local_items = list(self._local_items)
        active_tab.local_sort_col = self._local_sort_col
        active_tab.local_sort_reverse = self._local_sort_reverse
        active_tab.remote_path = self._remote_path
        active_tab.remote_items = list(self._remote_items)
        active_tab.remote_sort_col = self._remote_sort_col
        active_tab.remote_sort_reverse = self._remote_sort_reverse
        active_tab.is_connected = self._is_connected
        active_tab.is_connecting = self._is_connecting
        active_tab.status_msg = self.lbl_status_msg.cget("text")
        active_tab.status_server = self.lbl_status_server.cget("text")

    def _switch_to_tab(self, tab_id: str):
        if self._active_tab_id == tab_id:
            return
        self._save_current_tab_state()
        self._active_tab_id = tab_id
        target_tab = self._get_active_tab()
        if not target_tab:
            return
        self._restore_tab_state(target_tab)
        self._render_tabs()

    def _restore_tab_state(self, tab: SFTPTabSession):
        self._current_host = tab.host
        self._local_path = tab.local_path
        self._local_items = list(tab.local_items)
        self._local_sort_col = tab.local_sort_col
        self._local_sort_reverse = tab.local_sort_reverse
        self._remote_path = tab.remote_path
        self._remote_items = list(tab.remote_items)
        self._remote_sort_col = tab.remote_sort_col
        self._remote_sort_reverse = tab.remote_sort_reverse
        self._is_connected = tab.is_connected
        self._is_connecting = tab.is_connecting

        # Highlight active host in sidebar tree
        if tab.host:
            host_id = tab.host.get("id")
            tree_item_id = f"host_{host_id}"
            try:
                if self.hosts_tree.exists(tree_item_id):
                    self.hosts_tree.selection_set(tree_item_id)
                    self.hosts_tree.see(tree_item_id)
            except Exception:
                pass
        else:
            try:
                self.hosts_tree.selection_set(())
            except Exception:
                pass

        # Paths
        self.local_path_var.set(self._local_path)
        self.remote_path_var.set(self._remote_path)

        # Connection UI widgets
        if self._is_connected:
            self.btn_connect.configure(
                state="normal",
                text=" Disconnect",
                fg_color=COLORS["danger_subtle"],
                hover_color=COLORS["danger_hover"],
                text_color=COLORS["danger_text"],
                image=get_icon("x", (13, 13), COLORS["danger_text"])
            )
            self.conn_badge.configure(text="Connected", fg_color=COLORS["accent"], text_color="#FFFFFF")
        elif self._is_connecting:
            self.btn_connect.configure(state="disabled", text=" Connecting...")
            self.conn_badge.configure(text="Connecting...", fg_color=COLORS["surface"], text_color=COLORS["accent_text"])
        else:
            self.btn_connect.configure(
                state="normal",
                text=" Connect",
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                text_color="#FFFFFF",
                image=get_icon("play", (13, 13), "#FFFFFF")
            )
            self.conn_badge.configure(text="Disconnected", fg_color=COLORS["surface"], text_color=COLORS["muted"])

        self.lbl_status_msg.configure(text=tab.status_msg)
        self.lbl_status_server.configure(text=tab.status_server)

        # Render tables
        if not self._local_items:
            self._load_local_dir(self._local_path)
        else:
            self._render_local_table()

        self._render_remote_table()

    def _add_new_tab(self, host: Optional[Dict[str, Any]] = None):
        self._save_current_tab_state()
        new_id = f"tab_{uuid.uuid4().hex[:6]}"
        new_tab = SFTPTabSession(tab_id=new_id, host=host, local_path=self._local_path)
        self._tabs.append(new_tab)
        self._active_tab_id = new_id
        self._restore_tab_state(new_tab)
        self._render_tabs()
        if host:
            self._connect_to_selected_host()

    def _close_tab(self, tab_id: str):
        tab_to_close = next((t for t in self._tabs if t.tab_id == tab_id), None)
        if not tab_to_close:
            return

        idx = self._tabs.index(tab_to_close)
        self._tabs.remove(tab_to_close)

        if not self._tabs:
            new_id = f"tab_{uuid.uuid4().hex[:6]}"
            new_tab = SFTPTabSession(tab_id=new_id, local_path=self._local_path)
            self._tabs.append(new_tab)
            self._active_tab_id = new_id
            self._restore_tab_state(new_tab)
        elif self._active_tab_id == tab_id:
            new_idx = min(idx, len(self._tabs) - 1)
            new_tab = self._tabs[new_idx]
            self._active_tab_id = new_tab.tab_id
            self._restore_tab_state(new_tab)

        self._render_tabs()

    # ------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------

    def _toggle_connection(self):
        if self._is_connected:
            self._disconnect()
        else:
            self._connect_to_selected_host()

    def _connect_to_selected_host(self, target_host: Optional[Dict[str, Any]] = None):
        host = target_host or self._current_host
        if not host:
            active_tab = self._get_active_tab()
            if active_tab and active_tab.host:
                host = active_tab.host

        if not host:
            messagebox.showwarning("Pilih Server", "Pilih server tujuan dari daftar host di sebelah kiri terlebih dahulu.")
            return

        # Pastikan password dan credential terdekripsi penuh dari database
        if hasattr(self, "db") and host.get("id"):
            full_host = self.db.get_host_by_id(host["id"])
            if full_host:
                host = full_host

        self._current_host = host
        self._is_connecting = True
        active_tab = self._get_active_tab()
        if active_tab:
            active_tab.host = host
            active_tab.is_connecting = True
            self._render_tabs()

        self.btn_connect.configure(state="disabled", text=" Connecting...")
        self.conn_badge.configure(text="Connecting...", fg_color=COLORS["surface"], text_color=COLORS["accent_text"])
        self._set_status(f"Menghubungkan SFTP ke {host['label']} ({host['hostname']}:{host.get('port', 22)})...")
        self.lbl_status_server.configure(text=f"{host['label']} ({host['hostname']})")

        # Ambil remote path dari input remote_path_var atau repository path host
        initial_path = self.remote_path_var.get().strip() or (host.get("repo_path") or "").strip() or "/var/www/html"
        self._remote_path = initial_path
        self.remote_path_var.set(initial_path)

        def worker():
            host_cfg = self._get_active_host_config() or self._current_host
            res = SFTPService.list_dir(host_cfg, initial_path)
            self.after(0, lambda: self._on_connect_finished(res))

        threading.Thread(target=worker, daemon=True).start()

    def _on_connect_finished(self, res: Dict[str, Any]):
        self._is_connecting = False
        active_tab = self._get_active_tab()
        if res.get("success"):
            self._is_connected = True
            if active_tab:
                active_tab.is_connected = True
                active_tab.is_connecting = False
                active_tab.host = self._current_host
            self.btn_connect.configure(
                state="normal",
                text=" Disconnect",
                fg_color=COLORS["danger_subtle"],
                hover_color=COLORS["danger_hover"],
                text_color=COLORS["danger_text"],
                image=get_icon("x", (13, 13), COLORS["danger_text"])
            )
            self.conn_badge.configure(text="Connected", fg_color=COLORS["accent"], text_color="#FFFFFF")
            self._set_status("Koneksi SFTP berhasil.")
            
            self._remote_path = res.get("current_path", "/")
            self.remote_path_var.set(self._remote_path)
            self._remote_items = res.get("items", [])
            if active_tab:
                active_tab.remote_path = self._remote_path
                active_tab.remote_items = list(self._remote_items)
            self._render_remote_table()
            self._render_tabs()
        else:
            self._is_connected = False
            if active_tab:
                active_tab.is_connected = False
                active_tab.is_connecting = False
            error = res.get("error", "Unknown error")
            self.btn_connect.configure(
                state="normal",
                text=" Connect",
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                text_color="#FFFFFF",
                image=get_icon("play", (13, 13), "#FFFFFF")
            )
            self.conn_badge.configure(text="Offline", fg_color=COLORS["danger_subtle"], text_color=COLORS["danger_text"])
            self._set_status(f"Gagal terhubung: {error}")
            self._render_tabs()
            messagebox.showerror("SFTP Connection Failed", f"Gagal terhubung ke {self._current_host.get('label') if self._current_host else 'Server'}:\n\n{error}")

    def _disconnect(self):
        self._is_connected = False
        active_tab = self._get_active_tab()
        if active_tab:
            active_tab.is_connected = False
            active_tab.remote_items = []
        self.btn_connect.configure(
            state="normal",
            text=" Connect",
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            image=get_icon("play", (13, 13), "#FFFFFF")
        )
        self.conn_badge.configure(text="Disconnected", fg_color=COLORS["surface"], text_color=COLORS["muted"])
        self.remote_tree.delete(*self.remote_tree.get_children())
        self._remote_items = []
        self.lbl_remote_count.configure(text="0 items")
        self._set_status("SFTP terputus.")
        self.lbl_status_server.configure(text="")
        self._update_action_buttons_state()
        self._render_tabs()

    # ------------------------------------------------------------------
    # Remote Navigation & Operations
    # ------------------------------------------------------------------

    def _navigate_remote_to(self, path: str):
        if not self._is_connected or not self._current_host:
            return
        if self._is_remote_busy:
            return

        self._is_remote_busy = True
        self._set_status(f"Memuat direktori remote: {path}...")
        host_cfg = self._get_active_host_config() or self._current_host

        def worker():
            res = SFTPService.list_dir(host_cfg, path)
            self.after(0, lambda: self._on_remote_list_finished(res))

        threading.Thread(target=worker, daemon=True).start()

    def _on_remote_list_finished(self, res: Dict[str, Any]):
        self._is_remote_busy = False
        if not res.get("success"):
            err = res.get("error", "Error membaca direktori")
            self._set_status(f"Error: {err}")
            messagebox.showerror("Error Navigasi", f"Gagal membaca direktori:\n{err}")
            return

        self._remote_path = res.get("current_path", "/")
        self.remote_path_var.set(self._remote_path)
        self._remote_items = res.get("items", [])
        self._render_remote_table()

    def _render_remote_table(self):
        self.remote_tree.delete(*self.remote_tree.get_children())

        def sort_key(item: Dict[str, Any]):
            is_folder = 0 if item.get("is_dir") else 1
            if self._remote_sort_col == "name":
                val = item.get("name", "").lower()
            elif self._remote_sort_col == "size_bytes":
                val = item.get("size_bytes", 0)
            elif self._remote_sort_col == "permissions":
                val = item.get("permissions", "")
            elif self._remote_sort_col == "mtime":
                val = item.get("mtime", 0)
            else:
                val = item.get("name", "").lower()
            return (is_folder, val)

        sorted_items = sorted(self._remote_items, key=sort_key, reverse=self._remote_sort_reverse)
        dir_count = sum(1 for x in sorted_items if x.get("is_dir"))
        file_count = len(sorted_items) - dir_count

        for item in sorted_items:
            is_dir = item.get("is_dir", False)
            icon = get_tk_image("folder" if is_dir else "file", (14, 14), COLORS["accent"] if is_dir else COLORS["text_secondary"])
            self.remote_tree.insert(
                "", "end",
                iid=item.get("name"),
                text=f"  {item.get('name')}",
                image=icon,
                values=(item.get("size_str", "-"), item.get("permissions", ""), item.get("mtime_str", ""))
            )

        self.lbl_remote_count.configure(text=f"{len(sorted_items)} items ({dir_count} f, {file_count} fl)")
        self._set_status(f"Remote: {self._remote_path}")
        self._update_action_buttons_state()

    def _sort_remote_by(self, col: str):
        if self._remote_sort_col == col:
            self._remote_sort_reverse = not self._remote_sort_reverse
        else:
            self._remote_sort_col = col
            self._remote_sort_reverse = False
        self._render_remote_table()

    def _nav_remote_up(self):
        if not self._remote_path or self._remote_path == "/":
            return
        parent = os.path.dirname(self._remote_path.rstrip("/"))
        if not parent:
            parent = "/"
        self._navigate_remote_to(parent)

    def _nav_remote_home(self):
        self._navigate_remote_to(".")

    def _nav_remote_repo(self):
        if self._current_host and self._current_host.get("repo_path"):
            self._navigate_remote_to(self._current_host["repo_path"])
        else:
            self._navigate_remote_to("/")

    def _refresh_remote_current_dir(self):
        self._navigate_remote_to(self._remote_path)

    def _get_remote_item_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return next((it for it in self._remote_items if it.get("name") == name), None)

    def _on_remote_double_click(self, event):
        item_id = self.remote_tree.identify_row(event.y)
        if not item_id:
            return
        item = self._get_remote_item_by_name(item_id)
        if not item:
            return
        if item.get("is_dir"):
            self._navigate_remote_to(item["path"])
        else:
            self._open_file_in_editor(item)

    def _action_new_file(self):
        if not self._is_connected or not self._current_host:
            return
        dialog = ctk.CTkInputDialog(text="Nama file remote baru:", title="New Remote File")
        filename = dialog.get_input()
        if not filename or not filename.strip():
            return
        filename = filename.strip()
        remote_path = os.path.join(self._remote_path, filename).replace("\\", "/")
        host_cfg = self._get_active_host_config() or self._current_host

        def worker():
            ok, err = SFTPService.create_file(host_cfg, remote_path)
            def on_done():
                if ok:
                    self._set_status(f"File remote '{filename}' berhasil dibuat.")
                    self._refresh_remote_current_dir()
                else:
                    messagebox.showerror("Error", f"Gagal membuat file:\n{err}")
            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _action_new_dir(self):
        if not self._is_connected or not self._current_host:
            return
        dialog = ctk.CTkInputDialog(text="Nama folder remote baru:", title="New Remote Folder")
        dirname = dialog.get_input()
        if not dirname or not dirname.strip():
            return
        dirname = dirname.strip()
        remote_path = os.path.join(self._remote_path, dirname).replace("\\", "/")
        host_cfg = self._get_active_host_config() or self._current_host

        def worker():
            ok, err = SFTPService.create_dir(host_cfg, remote_path)
            def on_done():
                if ok:
                    self._set_status(f"Folder remote '{dirname}' berhasil dibuat.")
                    self._refresh_remote_current_dir()
                else:
                    messagebox.showerror("Error", f"Gagal membuat folder:\n{err}")
            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _action_rename(self):
        if not self._is_connected or not self._current_host:
            return
        sel = self.remote_tree.selection()
        if not sel:
            return
        item = self._get_remote_item_by_name(sel[0])
        if not item:
            return
        dialog = ctk.CTkInputDialog(text=f"Nama baru untuk '{item.get('name')}':", title="Rename Remote Item")
        new_name = dialog.get_input()
        if not new_name or not new_name.strip() or new_name.strip() == item.get("name"):
            return
        new_path = os.path.join(os.path.dirname(item.get("path")), new_name.strip()).replace("\\", "/")
        host_cfg = self._get_active_host_config() or self._current_host

        def worker():
            ok, err = SFTPService.rename(host_cfg, item.get("path"), new_path)
            def on_done():
                if ok:
                    self._set_status(f"Berhasil rename remote ke '{new_name}'.")
                    self._refresh_remote_current_dir()
                else:
                    messagebox.showerror("Error", f"Gagal rename:\n{err}")
            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _action_delete(self):
        if not self._is_connected or not self._current_host:
            return
        sel = self.remote_tree.selection()
        if not sel:
            return
        count = len(sel)
        names = ", ".join(sel[:3]) + (f" dan {count - 3} lainnya" if count > 3 else "")
        if not messagebox.askyesno("Hapus Remote Item", f"Yakin ingin menghapus {count} item ({names}) di remote server?"):
            return
        host_cfg = self._get_active_host_config() or self._current_host

        def worker():
            for name in sel:
                item = self._get_remote_item_by_name(name)
                if item:
                    SFTPService.delete_item(host_cfg, item.get("path"), item.get("is_dir", False))
            def on_done():
                self._set_status(f"{count} item remote telah dihapus.")
                self._refresh_remote_current_dir()
            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _action_edit_file(self, as_sudo: bool = False):
        sel = self.remote_tree.selection()
        if not sel:
            return
        item = self._get_remote_item_by_name(sel[0])
        if item and not item.get("is_dir"):
            self._open_file_in_editor(item, as_sudo=as_sudo)

    def _open_file_in_editor(self, item: Dict[str, Any], as_sudo: bool = False):
        if not self._is_connected or not self._current_host:
            return
        size_bytes = item.get("size_bytes", 0)
        if size_bytes > 5 * 1024 * 1024:
            if not messagebox.askyesno("File Besar", f"Ukuran file '{item.get('name')}' cukup besar ({item.get('size_str')}). Buka di editor?"):
                return

        host_config = self._get_active_host_config() or self._current_host

        FileEditorDialog(
            parent=self.app,
            host=host_config,
            remote_file_path=item.get("path"),
            as_sudo=as_sudo,
            on_saved_callback=self._refresh_remote_current_dir
        )

    def _save_remote_file(self, file_path: str, new_content: str) -> bool:
        if not self._is_connected or not self._current_host:
            messagebox.showerror("Save Error", "Koneksi SFTP terputus.")
            return False
        host_cfg = self._get_active_host_config() or self._current_host
        ok, err = SFTPService.write_file_text(host_cfg, file_path, new_content)
        if not ok:
            messagebox.showerror("Save Error", f"Gagal menyimpan file:\n{err}")
            return False
        self._set_status(f"File remote '{os.path.basename(file_path)}' berhasil disimpan.")
        self._refresh_remote_current_dir()
        return True

    def _set_status(self, msg: str):
        self.lbl_status_msg.configure(text=msg)

    def _update_action_buttons_state(self):
        is_conn = self._is_connected
        
        # Local pane states
        local_sel = self.local_tree.selection()
        has_local_sel = bool(local_sel)
        self.btn_local_upload.configure(state="normal" if (is_conn and has_local_sel) else "disabled")
        self.btn_local_del.configure(state="normal" if has_local_sel else "disabled")

        # Remote pane states
        remote_sel = self.remote_tree.selection()
        has_remote_sel = bool(remote_sel)
        single_remote_file = (len(remote_sel) == 1 and bool(self._get_remote_item_by_name(remote_sel[0]) and not self._get_remote_item_by_name(remote_sel[0]).get("is_dir")))

        state_conn = "normal" if is_conn else "disabled"
        self.btn_remote_up.configure(state=state_conn)
        self.btn_remote_home.configure(state=state_conn)
        self.btn_remote_repo.configure(state=state_conn)
        self.btn_remote_go.configure(state=state_conn)
        self.btn_remote_refresh.configure(state=state_conn)
        self.btn_remote_new_file.configure(state=state_conn)
        self.btn_remote_new_folder.configure(state=state_conn)

        self.btn_remote_download.configure(state="normal" if (is_conn and has_remote_sel) else "disabled")
        self.btn_remote_edit.configure(state="normal" if (is_conn and single_remote_file) else "disabled")
        self.btn_remote_del.configure(state="normal" if (is_conn and has_remote_sel) else "disabled")
        if hasattr(self, "btn_remote_terminal"):
            self.btn_remote_terminal.configure(state=state_conn)
        if hasattr(self, "btn_remote_terminal_action"):
            self.btn_remote_terminal_action.configure(state=state_conn)

    def _action_open_remote_terminal(self, target_path: Optional[str] = None):
        """Membuka sesi SSH terminal interaktif langsung pada direktori remote tertentu."""
        host = self._current_host
        if not host:
            active_tab = self._get_active_tab()
            if active_tab and active_tab.host:
                host = active_tab.host

        if not host:
            messagebox.showwarning("Pilih Server", "Pilih atau hubungkan ke server tujuan terlebih dahulu untuk membuka SSH terminal.")
            return

        path_to_open = target_path or self._remote_path or host.get("repo_path") or "/var/www/html"
        full_host = self.db.get_host_by_id(host["id"]) if (hasattr(self, "db") and "id" in host) else host
        host_config = dict(full_host or host)

        res = launch_ssh_terminal(host=host_config, initial_dir=path_to_open, app=self.app)
        if res.get("success"):
            self._set_status(f"🚀 {res.get('message', 'Membuka SSH Terminal')} di '{path_to_open}'")
        else:
            messagebox.showerror("Terminal Error", res.get("error", "Gagal membuka terminal"))

    def _action_open_local_terminal(self, target_path: Optional[str] = None):
        """Membuka terminal lokal pada direktori lokal yang sedang diakses."""
        path_to_open = target_path or self._local_path or os.path.expanduser("~")
        res = launch_local_terminal(initial_dir=path_to_open, app=self.app)
        if res.get("success"):
            self._set_status(f"💻 {res.get('message', 'Membuka Terminal Lokal')}")
        else:
            messagebox.showerror("Terminal Error", res.get("error", "Gagal membuka terminal"))

    def _open_terminal_for_host(self, host: Dict[str, Any]):
        """Membuka SSH terminal untuk host yang dipilih dari tree host sidebar."""
        full_host = self.db.get_host_by_id(host["id"]) if (hasattr(self, "db") and "id" in host) else host
        host_config = dict(full_host or host)
        initial_dir = host_config.get("repo_path") or "/var/www/html"
        res = launch_ssh_terminal(host=host_config, initial_dir=initial_dir, app=self.app)
        if res.get("success"):
            self._set_status(f"🚀 {res.get('message', 'Membuka SSH Terminal')}")
        else:
            messagebox.showerror("Terminal Error", res.get("error", "Gagal membuka terminal"))
