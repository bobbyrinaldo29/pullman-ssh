from datetime import date, datetime, timedelta
import json
import math
import re
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional
import webbrowser

import customtkinter as ctk

from theme import COLORS, get_color, apply_treeview_styles
from icons import get_icon
from redmine_notifier import NotificationCenter
from redmine_service import DEFAULT_STATUS_FILTER, RedmineClient, RedmineError, STATUS_FILTERS
from ui.redmine_account_dialog import RedmineAccountDialog
from ui.redmine_edit_task_dialog import RedmineEditTaskDialog
from ui.redmine_issue_panel import RedmineIssuePanel, format_date, format_datetime
from ui.tab_bar import HorizontalScrollableTabBar

SCOPE_FILTERS = {
    "Assigned ke saya": ("assigned_to_id", "me"),
    "Dibuat oleh saya": ("author_id", "me"),
    "Saya watch": ("watcher_id", "me"),
    "Semua (Tanpa scope)": (None, None),
}
DUE_FILTERS = ["Semua", "Terlambat", "Hari ini", "7 hari ke depan", "30 hari ke depan", "Tanpa due date"]
UPDATED_FILTERS = ["Semua", "Hari ini", "7 hari terakhir", "30 hari terakhir"]
PER_PAGE_OPTIONS = ["25", "50", "100"]
ALL_QUERIES = "Semua / Tanpa query"
ALL_PROJECTS = "Semua project"
ALL_TRACKERS = "Semua tracker"
ALL_PRIORITIES = "Semua priority"

# kolom tabel -> (judul, lebar, anchor, stretch, sort key Redmine)
COLUMNS = {
    "id": ("#", 65, "center", False, "id"),
    "project": ("Project", 140, "w", False, "project"),
    "tracker": ("Tracker", 85, "center", False, "tracker"),
    "status": ("Status", 110, "center", False, "status"),
    "priority": ("Priority", 75, "center", False, "priority"),
    "subject": ("Subject", 320, "w", True, "subject"),
    "due": ("Due Date", 95, "center", False, "due_date"),
    "done": ("Done", 55, "center", False, "done_ratio"),
    "updated": ("Updated", 125, "center", False, "updated_on"),
}
MAX_ISSUE_TABS = 8
LIST_TAB = "list"
SETTINGS_KEY = "redmine_filters"


class RedmineView(ctk.CTkFrame):
    """Task Redmine milik user: daftar ber-filter & ber-paging, dengan detail task sebagai tab in-app."""

    def __init__(self, parent: ctk.CTk, db_manager: Any, notification_center: NotificationCenter,
                 on_account_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.app = parent
        self.db = db_manager
        self.notifications = notification_center
        self._on_account_changed = on_account_changed

        self._client: Optional[RedmineClient] = None
        self._issues: List[Dict[str, Any]] = []
        self._issue_by_item: Dict[str, Dict[str, Any]] = {}
        self._total = 0
        self._page = 0
        self._sort_col = "updated"
        self._sort_desc = True
        self._request_seq = 0
        self._is_loading = False
        self._has_loaded = False
        self._needs_reload = False
        self._metadata_loaded = False
        self._search_job: Optional[str] = None

        # id -> nama, dipakai untuk filter & menerjemahkan riwayat perubahan
        self._lookups: Dict[str, Dict[str, str]] = {
            "status_id": {}, "tracker_id": {}, "priority_id": {}, "project_id": {}, "assigned_to_id": {},
        }
        self._status_ids: Dict[str, int] = {}
        self._project_ids: Dict[str, int] = {}
        self._tracker_ids: Dict[str, int] = {}
        self._priority_ids: Dict[str, int] = {}
        self._query_ids: Dict[str, int] = {}
        self._query_meta: Dict[str, Dict[str, Any]] = {}

        # Tab: LIST_TAB atau issue_id (int)
        self._tab_order: List[Any] = [LIST_TAB]
        self._tab_titles: Dict[Any, str] = {LIST_TAB: "Daftar Task"}
        self._issue_panels: Dict[int, RedmineIssuePanel] = {}
        self._active_tab: Any = LIST_TAB

        self._saved_filters = self._load_saved_filters()
        if self._saved_filters.get("sort_col") in COLUMNS:
            self._sort_col = self._saved_filters["sort_col"]
            self._sort_desc = bool(self._saved_filters.get("sort_desc", True))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._setup_ui()
        self._create_context_menu()
        self._render_tab_strip()
        self.notifications.subscribe(self._update_bell)
        self._update_bell()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_show(self):
        """Dipanggil setiap kali menu Task Redmine dibuka."""
        if not self._has_loaded:
            self.refresh()
        elif self._needs_reload:
            self._load_issues()

    def on_theme_changed(self, mode: str):
        apply_treeview_styles(mode)
        self._create_context_menu()
        self._apply_tag_colors()
        for panel in self._issue_panels.values():
            panel.on_theme_changed()
        self._render_tab_strip()

    def refresh(self):
        """Muat ulang akun, metadata filter, dan halaman task saat ini."""
        credential = self.db.get_redmine_credential()
        if not credential:
            self._client = None
            self._issues, self._total = [], 0
            self._close_all_issue_tabs()
            self._render_issues()
            self._show_empty_state(True)
            self.lbl_user.configure(text="Akun Redmine belum terhubung")
            self._set_status("")
            self._update_pager()
            return

        self._show_empty_state(False)
        client = RedmineClient(credential["base_url"], credential["api_key"])
        if self._client is None or self._client.base_url != client.base_url or self._client.api_key != client.api_key:
            self._metadata_loaded = False
            self._close_all_issue_tabs()
        self._client = client
        user_name = credential.get("user_name") or "-"
        self.lbl_user.configure(text=f"Task milik {user_name}  •  {client.base_url}")
        if not self._metadata_loaded:
            self._load_metadata()
        self._load_issues()

    def notify_issues_changed(self, issue_ids: List[int]):
        """Dipanggil app saat notifier menemukan perubahan task."""
        for issue_id in issue_ids:
            panel = self._issue_panels.get(issue_id)
            if panel is not None:
                panel.refresh()
        if self.winfo_ismapped() and self._active_tab == LIST_TAB:
            self._load_issues()
        else:
            self._needs_reload = True

    def open_issue_tab(self, issue_id: int):
        if self._client is None:
            return
        if issue_id not in self._issue_panels:
            issue_tabs = [t for t in self._tab_order if t != LIST_TAB]
            if len(issue_tabs) >= MAX_ISSUE_TABS:
                self._close_tab(issue_tabs[0])
            known = next((i for i in self._issues if i.get("id") == issue_id), None)
            self._tab_titles[issue_id] = self._issue_tab_title(issue_id, known.get("subject") if known else "")
            panel = RedmineIssuePanel(
                self.content, self._client, issue_id, self._lookups,
                on_loaded=self._on_issue_panel_loaded, on_open_issue=self.open_issue_tab,
                on_status_changed=self._on_issue_status_changed,
                text_format=self.db.get_setting("redmine_text_format", "auto")
            )
            self._issue_panels[issue_id] = panel
            self._tab_order.append(issue_id)
        self._select_tab(issue_id)

    def _on_issue_status_changed(self, issue_id: int):
        self._load_issues()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        # 1. HEADER
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.grid_columnconfigure(0, weight=1)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(title_box, text="Task Redmine", text_color=COLORS["text"], font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        self.lbl_user = ctk.CTkLabel(title_box, text="", text_color=COLORS["muted"], font=ctk.CTkFont(size=12))
        self.lbl_user.pack(anchor="w")

        self.btn_bell = ctk.CTkButton(
            header, text="", image=get_icon("bell", (15, 15), COLORS["text"]), compound="left",
            width=34, height=34, corner_radius=8, fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=12, weight="bold"), command=self._show_notification_menu
        )
        self.btn_bell.grid(row=0, column=1, sticky="e", padx=(5, 0))

        ctk.CTkButton(
            header, text=" Akun Redmine", image=get_icon("settings", (14, 14), COLORS["text"]), compound="left",
            width=130, height=34, corner_radius=8, fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=12, weight="bold"), command=self._open_account_dialog
        ).grid(row=0, column=2, sticky="e", padx=(5, 0))

        # 2. TAB STRIP (Scrollable horizontal frame with nav buttons)
        self.tab_bar_frame = ctk.CTkFrame(self, fg_color="transparent", height=38)
        self.tab_bar_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.tab_bar_frame.grid_columnconfigure(1, weight=1)

        self.btn_tab_left = ctk.CTkButton(
            self.tab_bar_frame,
            text="‹",
            width=26,
            height=28,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self.tab_strip.scroll_left()
        )

        self.tab_strip = HorizontalScrollableTabBar(self.tab_bar_frame, height=38, fg_color="transparent")
        self.tab_strip.grid(row=0, column=1, sticky="ew")

        self.btn_tab_right = ctk.CTkButton(
            self.tab_bar_frame,
            text="›",
            width=26,
            height=28,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self.tab_strip.scroll_right()
        )

        # 3. CONTENT (daftar task & panel detail ditumpuk di sel yang sama)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=2, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.list_page = ctk.CTkFrame(self.content, fg_color="transparent")
        self.list_page.grid(row=0, column=0, sticky="nsew")
        self.list_page.grid_columnconfigure(0, weight=1)
        self.list_page.grid_rowconfigure(1, weight=1)

        self._build_filter_card()
        self._build_table()
        self._build_pager()

    def _filter_menu(self, parent, values: List[str], initial: str, on_change: Optional[Callable[[str], None]] = None) -> ctk.CTkOptionMenu:
        cmd = on_change if on_change else (lambda _: self._on_filter_changed())
        menu = ctk.CTkOptionMenu(
            parent, values=values, height=32, corner_radius=8, dynamic_resizing=False,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=12),
            command=cmd
        )
        menu.set(initial if initial in values else values[0])
        return menu

    def _on_query_changed(self, choice: str):
        if choice != ALL_QUERIES:
            if self.opt_scope.get() == "Assigned ke saya":
                self.opt_scope.set("Semua (Tanpa scope)")
            query_meta = self._query_meta.get(choice)
            if query_meta and query_meta.get("project_id"):
                proj_id_str = str(query_meta["project_id"])
                proj_name = self._lookups.get("project_id", {}).get(proj_id_str)
                if proj_name and proj_name in self._project_ids:
                    self.opt_project.set(proj_name)
        self._on_filter_changed()

    def _build_filter_card(self):
        card = ctk.CTkFrame(self.list_page, fg_color=COLORS["surface"], corner_radius=8, border_width=1, border_color=COLORS["line"])
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for col in range(5):
            card.grid_columnconfigure(col, weight=1, uniform="filters")

        saved = self._saved_filters

        def caption(text: str, row: int, col: int, colspan: int = 1):
            ctk.CTkLabel(card, text=text, text_color=COLORS["muted"], font=ctk.CTkFont(size=11, weight="bold"), anchor="w").grid(
                row=row, column=col, columnspan=colspan, sticky="w", padx=(12 if col == 0 else 6, 6), pady=(10 if row == 0 else 6, 0)
            )

        def place(widget, row: int, col: int, colspan: int = 1, pady=(2, 0)):
            widget.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=(12 if col == 0 else 6, 12 if col + colspan == 5 else 6), pady=pady)

        caption("My Custom Query", 0, 0)
        caption("Scope", 0, 1)
        caption("Status", 0, 2)
        caption("Project", 0, 3)
        caption("Tracker", 0, 4)
        self.opt_query = self._filter_menu(card, [ALL_QUERIES], saved.get("query", ""), on_change=self._on_query_changed)
        self.opt_scope = self._filter_menu(card, list(SCOPE_FILTERS.keys()), saved.get("scope", ""))
        self.opt_status = self._filter_menu(card, list(STATUS_FILTERS.keys()), saved.get("status", ""))
        self.opt_project = self._filter_menu(card, [ALL_PROJECTS], ALL_PROJECTS)
        self.opt_tracker = self._filter_menu(card, [ALL_TRACKERS], ALL_TRACKERS)
        for col, menu in enumerate([self.opt_query, self.opt_scope, self.opt_status, self.opt_project, self.opt_tracker]):
            place(menu, 1, col)

        caption("Priority", 2, 0)
        caption("Due date", 2, 1)
        caption("Updated", 2, 2)
        caption("Subject / #ID", 2, 3)
        self.opt_priority = self._filter_menu(card, [ALL_PRIORITIES], ALL_PRIORITIES)
        self.opt_due = self._filter_menu(card, DUE_FILTERS, saved.get("due", ""))
        self.opt_updated = self._filter_menu(card, UPDATED_FILTERS, saved.get("updated", ""))
        place(self.opt_priority, 3, 0, pady=(2, 12))
        place(self.opt_due, 3, 1, pady=(2, 12))
        place(self.opt_updated, 3, 2, pady=(2, 12))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_typed)
        search = ctk.CTkEntry(
            card, textvariable=self.search_var, placeholder_text="Cari subject atau nomor task...",
            height=32, corner_radius=8, border_width=1, border_color=COLORS["line"], fg_color=COLORS["input_bg"],
            text_color=COLORS["text"], placeholder_text_color=COLORS["muted"], font=ctk.CTkFont(size=12)
        )
        place(search, 3, 3, pady=(2, 12))
        search.bind("<Return>", lambda _: self._apply_search_now())

        actions = ctk.CTkFrame(card, fg_color="transparent")
        place(actions, 3, 4, pady=(2, 12))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions, text="Reset", height=32, corner_radius=8, fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["line"], font=ctk.CTkFont(size=12, weight="bold"),
            command=self._reset_filters
        ).grid(row=0, column=0, sticky="ew")
        self.btn_refresh = ctk.CTkButton(
            actions, text="", image=get_icon("refresh-cw", (14, 14), "#FFFFFF"), width=36, height=32, corner_radius=8,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self.refresh
        )
        self.btn_refresh.grid(row=0, column=1, padx=(6, 0))

    def _build_table(self):
        self.table_container = ctk.CTkFrame(self.list_page, fg_color=COLORS["input_bg"], border_width=1, border_color=COLORS["line"], corner_radius=8)
        self.table_container.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        self.table_container.grid_columnconfigure(0, weight=1)
        self.table_container.grid_rowconfigure(0, weight=1)

        apply_treeview_styles()
        self.tree = ttk.Treeview(
            self.table_container, columns=tuple(COLUMNS.keys()), show="headings",
            style="Pullman.Treeview", selectmode="browse"
        )
        for key, (label, width, anchor, stretch, _sort) in COLUMNS.items():
            self.tree.heading(key, text=label, anchor=anchor, command=lambda k=key: self._on_sort_clicked(k))
            self.tree.column(key, width=width, anchor=anchor, stretch=stretch)
        self._update_sort_headings()

        vsb = ttk.Scrollbar(self.table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self._apply_tag_colors()

        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)
        self.tree.bind("<Return>", lambda _: self._open_selected_tab())
        self.tree.bind("<Button-3>", self._show_context_menu)

        # Empty state (akun belum terhubung)
        self.empty_state = ctk.CTkFrame(self.table_container, fg_color="transparent")
        ctk.CTkLabel(self.empty_state, text="", image=get_icon("list-checks", (40, 40), COLORS["muted"])).pack(pady=(0, 10))
        ctk.CTkLabel(self.empty_state, text="Hubungkan akun Redmine Anda", text_color=COLORS["text"], font=ctk.CTkFont(size=16, weight="bold")).pack()
        ctk.CTkLabel(
            self.empty_state, text="Masukkan URL Redmine dan API key pribadi untuk melihat task Anda.",
            text_color=COLORS["muted"], font=ctk.CTkFont(size=12)
        ).pack(pady=(4, 14))
        ctk.CTkButton(
            self.empty_state, text=" Hubungkan Akun", image=get_icon("key", (14, 14), "#FFFFFF"), compound="left",
            height=34, corner_radius=8, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(size=12, weight="bold"), command=self._open_account_dialog
        ).pack()

    def _build_pager(self):
        bar = ctk.CTkFrame(self.list_page, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        self.lbl_status = ctk.CTkLabel(bar, text="", text_color=COLORS["muted"], font=ctk.CTkFont(size=11), anchor="w")
        self.lbl_status.grid(row=0, column=0, sticky="ew")

        pager = ctk.CTkFrame(bar, fg_color="transparent")
        pager.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(pager, text="Per halaman", text_color=COLORS["muted"], font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))
        self.opt_per_page = ctk.CTkOptionMenu(
            pager, values=PER_PAGE_OPTIONS, width=68, height=28, corner_radius=7,
            fg_color=COLORS["surface"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=11), command=lambda _: self._on_filter_changed()
        )
        self.opt_per_page.set(self._saved_filters.get("per_page") if self._saved_filters.get("per_page") in PER_PAGE_OPTIONS else "25")
        self.opt_per_page.pack(side="left", padx=(0, 10))

        def nav_button(text: str, command):
            btn = ctk.CTkButton(
                pager, text=text, width=30, height=28, corner_radius=7, fg_color=COLORS["surface"],
                hover_color=COLORS["surface_hover"], text_color=COLORS["text"], border_width=1,
                border_color=COLORS["line"], font=ctk.CTkFont(size=13, weight="bold"), command=command
            )
            btn.pack(side="left", padx=2)
            return btn

        self.btn_first = nav_button("«", lambda: self._go_to_page(0))
        self.btn_prev = nav_button("‹", lambda: self._go_to_page(self._page - 1))
        self.lbl_page = ctk.CTkLabel(pager, text="Hal 1 / 1", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12), width=90)
        self.lbl_page.pack(side="left", padx=4)
        self.btn_next = nav_button("›", lambda: self._go_to_page(self._page + 1))
        self.btn_last = nav_button("»", lambda: self._go_to_page(self._page_count() - 1))
        self._update_pager()

    @staticmethod
    def _get_status_tag(status_name: str, is_closed: bool = False) -> str:
        s = (status_name or "").strip().lower()
        s_norm = s.replace("-", " ").replace("_", " ")

        # 1. Merah: test-failed / failed / reject / gagal
        if "failed" in s_norm or "test failed" in s_norm or "gagal" in s_norm or "reject" in s_norm:
            return "status_test_failed"
        # 2. Hijau: test-passed / passed / resolved / selesai
        if "passed" in s_norm or "test passed" in s_norm or "pass" in s_norm or "resolved" in s_norm or "selesai" in s_norm:
            return "status_test_passed"
        # 3. Putih: new / baru / open
        if s_norm in ("new", "baru", "open") or "new" in s_norm:
            return "status_new"
        # 4. In progress / development
        if "progress" in s_norm or "ongoing" in s_norm or "working" in s_norm or "proses" in s_norm:
            return "status_in_progress"
        # 5. Feedback / Waiting / Need info
        if "feedback" in s_norm or "waiting" in s_norm or "tunggu" in s_norm or "pending" in s_norm:
            return "status_feedback"
        # 6. Reopened
        if "reopened" in s_norm or "reopen" in s_norm or "buka kembali" in s_norm:
            return "status_reopened"
        # 7. Assigned / Review
        if "assigned" in s_norm or "review" in s_norm:
            return "status_assigned"
        # 8. Closed
        if is_closed or "closed" in s_norm or "tutup" in s_norm:
            return "status_closed"
        # 9. Lainnya
        return "status_other"

    def _apply_tag_colors(self):
        is_dark = ctk.get_appearance_mode().lower() == "dark"

        # Warna status sesuai instruksi:
        # test-failed: Merah
        self.tree.tag_configure("status_test_failed", foreground="#EF4444" if is_dark else "#DC2626")
        # test-passed: Hijau
        self.tree.tag_configure("status_test_passed", foreground="#22C55E" if is_dark else "#16A34A")
        # new: Putih (Dark Mode: #FFFFFF, Light Mode: Slate #0F172A)
        self.tree.tag_configure("status_new", foreground="#FFFFFF" if is_dark else "#0F172A")
        # Status lainnya dengan warna yang kontras dan elegan
        self.tree.tag_configure("status_in_progress", foreground="#38BDF8" if is_dark else "#0284C7")
        self.tree.tag_configure("status_feedback", foreground="#FBBF24" if is_dark else "#D97706")
        self.tree.tag_configure("status_reopened", foreground="#C084FC" if is_dark else "#7C3AED")
        self.tree.tag_configure("status_assigned", foreground="#818CF8" if is_dark else "#4F46E5")
        self.tree.tag_configure("status_closed", foreground="#94A3B8" if is_dark else "#64748B")
        self.tree.tag_configure("status_other", foreground="#E2E8F0" if is_dark else "#334155")

        self.tree.tag_configure("overdue", foreground=get_color("danger"))
        self.tree.tag_configure("closed", foreground=get_color("muted"))

    def _create_context_menu(self):
        self.context_menu = tk.Menu(
            self, tearoff=0, bg=get_color("surface"), fg=get_color("text"),
            activebackground=get_color("accent"), activeforeground="#FFFFFF", bd=1
        )
        self.context_menu.add_command(label="Buka Detail (Tab Baru)", command=self._open_selected_tab)
        self.context_menu.add_command(label="Buka di Browser", command=self._open_selected_in_browser)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Copy ID Task", command=lambda: self._copy_selected("id"))
        self.context_menu.add_command(label="Copy Subject", command=lambda: self._copy_selected("subject"))
        self.context_menu.add_command(label="Copy URL Task", command=lambda: self._copy_selected("url"))

    def _show_empty_state(self, show: bool):
        if show:
            self.empty_state.place(relx=0.5, rely=0.45, anchor="center")
        else:
            self.empty_state.place_forget()

    def _set_status(self, text: str, is_error: bool = False):
        self.lbl_status.configure(text=text, text_color=COLORS["danger"] if is_error else COLORS["muted"])

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    @staticmethod
    def _issue_tab_title(issue_id: int, subject: str) -> str:
        subject = (subject or "").strip()
        if len(subject) > 22:
            subject = subject[:21] + "…"
        return f"#{issue_id} {subject}".strip()

    def _render_tab_strip(self):
        for child in self.tab_strip.winfo_children():
            child.destroy()
        active_tab_widget = None
        for key in self._tab_order:
            active = key == self._active_tab
            tab = ctk.CTkFrame(
                self.tab_strip, corner_radius=8, border_width=1,
                fg_color=COLORS["accent_subtle"] if active else COLORS["surface"],
                border_color=COLORS["accent_border"] if active else COLORS["line"],
            )
            tab.pack(side="left", padx=(0, 6))
            self.tab_strip.bind_child_scroll(tab)
            if active:
                active_tab_widget = tab
            icon = "list-checks" if key == LIST_TAB else "file-text"
            color = COLORS["accent_text"] if active else COLORS["text_secondary"]
            btn = ctk.CTkButton(
                tab, text=f" {self._tab_titles.get(key, key)}", image=get_icon(icon, (13, 13), color), compound="left",
                height=28, corner_radius=7, fg_color="transparent", hover_color=COLORS["surface_hover"],
                text_color=color, font=ctk.CTkFont(size=12, weight="bold" if active else "normal"),
                command=lambda k=key: self._select_tab(k)
            )
            btn.pack(side="left", padx=(2, 0 if key != LIST_TAB else 2), pady=2)
            self.tab_strip.bind_child_scroll(btn)
            if key != LIST_TAB:
                btn.bind("<Button-2>", lambda _e, k=key: self._close_tab(k))
                close_btn = ctk.CTkButton(
                    tab, text="", image=get_icon("x", (11, 11), COLORS["muted"]), width=22, height=22, corner_radius=6,
                    fg_color="transparent", hover_color=COLORS["surface_hover"], command=lambda k=key: self._close_tab(k)
                )
                close_btn.pack(side="left", padx=(0, 4))
                self.tab_strip.bind_child_scroll(close_btn)

        if active_tab_widget:
            self.after(50, lambda: self.tab_strip.scroll_to_child(active_tab_widget))

        # Tampilkan tombol navigasi ‹ dan › jika tab mulai banyak
        if len(self._tab_order) >= 3:
            self.btn_tab_left.grid(row=0, column=0, padx=(0, 4), sticky="w")
            self.btn_tab_right.grid(row=0, column=2, padx=(4, 0), sticky="e")
        else:
            self.btn_tab_left.grid_forget()
            self.btn_tab_right.grid_forget()

    def _select_tab(self, key: Any):
        self._active_tab = key
        if key == LIST_TAB:
            for panel in self._issue_panels.values():
                panel.grid_remove()
            self.list_page.grid()
            if self._needs_reload:
                self._load_issues()
        else:
            self.list_page.grid_remove()
            for issue_id, panel in self._issue_panels.items():
                if issue_id == key:
                    panel.grid(row=0, column=0, sticky="nsew")
                else:
                    panel.grid_remove()
        self._render_tab_strip()

    def _close_tab(self, key: Any):
        if key == LIST_TAB or key not in self._tab_order:
            return
        index = self._tab_order.index(key)
        self._tab_order.remove(key)
        self._tab_titles.pop(key, None)
        panel = self._issue_panels.pop(key, None)
        if panel is not None:
            panel.destroy()
        if self._active_tab == key:
            self._select_tab(self._tab_order[min(index, len(self._tab_order) - 1)])
        else:
            self._render_tab_strip()

    def _close_all_issue_tabs(self):
        for key in [k for k in self._tab_order if k != LIST_TAB]:
            self._close_tab(key)
        if self._active_tab != LIST_TAB:
            self._select_tab(LIST_TAB)

    def _on_issue_panel_loaded(self, issue_id: int, issue: Dict[str, Any]):
        self._tab_titles[issue_id] = self._issue_tab_title(issue_id, issue.get("subject", ""))
        self._render_tab_strip()

    # ------------------------------------------------------------------
    # Filters & paging
    # ------------------------------------------------------------------

    def _load_saved_filters(self) -> Dict[str, Any]:
        try:
            return json.loads(self.db.get_setting(SETTINGS_KEY, "{}") or "{}")
        except ValueError:
            return {}

    def _save_filters(self):
        self._saved_filters = {
            "query": self.opt_query.get(), "scope": self.opt_scope.get(), "status": self.opt_status.get(), "project": self.opt_project.get(),
            "tracker": self.opt_tracker.get(), "priority": self.opt_priority.get(), "due": self.opt_due.get(),
            "updated": self.opt_updated.get(), "per_page": self.opt_per_page.get(),
            "sort_col": self._sort_col, "sort_desc": self._sort_desc,
        }
        self.db.set_setting(SETTINGS_KEY, json.dumps(self._saved_filters))

    def _on_filter_changed(self):
        self._page = 0
        self._save_filters()
        self._load_issues()

    def _on_search_typed(self, *_):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(600, self._apply_search_now)

    def _apply_search_now(self):
        if self._search_job:
            self.after_cancel(self._search_job)
            self._search_job = None
        self._page = 0
        self._load_issues()

    def _reset_filters(self):
        self.opt_query.set(ALL_QUERIES)
        self.opt_scope.set(list(SCOPE_FILTERS.keys())[0])
        self.opt_status.set(DEFAULT_STATUS_FILTER)
        self.opt_project.set(ALL_PROJECTS)
        self.opt_tracker.set(ALL_TRACKERS)
        self.opt_priority.set(ALL_PRIORITIES)
        self.opt_due.set(DUE_FILTERS[0])
        self.opt_updated.set(UPDATED_FILTERS[0])
        self._sort_col, self._sort_desc = "updated", True
        self._update_sort_headings()
        if self.search_var.get():
            self.search_var.set("")  # memicu pencarian ulang via debounce
        self._on_filter_changed()

    def _on_sort_clicked(self, column: str):
        if self._sort_col == column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col, self._sort_desc = column, column in ("updated", "id", "priority", "done")
        self._update_sort_headings()
        self._on_filter_changed()

    def _update_sort_headings(self):
        for key, (label, *_rest) in COLUMNS.items():
            arrow = (" ▼" if self._sort_desc else " ▲") if key == self._sort_col else ""
            self.tree.heading(key, text=f"{label}{arrow}")

    def _per_page(self) -> int:
        return int(self.opt_per_page.get())

    def _page_count(self) -> int:
        return max(1, math.ceil(self._total / self._per_page()))

    def _go_to_page(self, page: int):
        page = max(0, min(page, self._page_count() - 1))
        if page != self._page:
            self._page = page
            self._load_issues()

    def _update_pager(self):
        pages = self._page_count()
        self.lbl_page.configure(text=f"Hal {self._page + 1} / {pages}")
        can_prev = self._page > 0 and not self._is_loading
        can_next = self._page < pages - 1 and not self._is_loading
        for btn, enabled in ((self.btn_first, can_prev), (self.btn_prev, can_prev), (self.btn_next, can_next), (self.btn_last, can_next)):
            btn.configure(state="normal" if enabled else "disabled")

    def _build_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        query_name = self.opt_query.get()
        query_meta = self._query_meta.get(query_name)
        if query_meta:
            params["query_id"] = query_meta["id"]
            if query_meta.get("project_id") is not None:
                params["project_id"] = query_meta["project_id"]

        scope_key, scope_value = SCOPE_FILTERS.get(self.opt_scope.get(), ("assigned_to_id", "me"))
        if scope_key and scope_value:
            params[scope_key] = scope_value

        status = self.opt_status.get()
        if status in STATUS_FILTERS:
            status_val = STATUS_FILTERS[status]
            if query_meta is None or status != DEFAULT_STATUS_FILTER:
                params["status_id"] = status_val
        elif status in self._status_ids:
            params["status_id"] = self._status_ids[status]

        if self.opt_project.get() in self._project_ids and "project_id" not in params:
            params["project_id"] = self._project_ids[self.opt_project.get()]
        if self.opt_tracker.get() in self._tracker_ids:
            params["tracker_id"] = self._tracker_ids[self.opt_tracker.get()]
        if self.opt_priority.get() in self._priority_ids:
            params["priority_id"] = self._priority_ids[self.opt_priority.get()]

        today = date.today()
        iso = lambda d: d.isoformat()
        due = self.opt_due.get()
        if due == "Terlambat":
            params["due_date"] = f"<={iso(today - timedelta(days=1))}"
        elif due == "Hari ini":
            params["due_date"] = f"><{iso(today)}|{iso(today)}"
        elif due == "7 hari ke depan":
            params["due_date"] = f"><{iso(today)}|{iso(today + timedelta(days=7))}"
        elif due == "30 hari ke depan":
            params["due_date"] = f"><{iso(today)}|{iso(today + timedelta(days=30))}"
        elif due == "Tanpa due date":
            params["due_date"] = "!*"

        updated = self.opt_updated.get()
        if updated == "Hari ini":
            params["updated_on"] = f">={iso(today)}"
        elif updated == "7 hari terakhir":
            params["updated_on"] = f">={iso(today - timedelta(days=7))}"
        elif updated == "30 hari terakhir":
            params["updated_on"] = f">={iso(today - timedelta(days=30))}"

        query = self.search_var.get().strip()
        id_match = re.fullmatch(r"#?(\d+)", query)
        if id_match:
            params["issue_id"] = id_match.group(1)
        elif query:
            params["subject"] = f"~{query}"

        sort_key = COLUMNS[self._sort_col][4]
        params["sort"] = f"{sort_key}:desc" if self._sort_desc else sort_key
        return params

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_metadata(self):
        client = self._client

        def safe(fn):
            try:
                return fn()
            except Exception:
                return []

        def safe_dict(fn):
            try:
                return fn()
            except Exception:
                return {}

        def worker():
            data = {
                "statuses": safe(client.list_statuses),
                "trackers": safe(client.list_trackers),
                "priorities": safe(client.list_priorities),
                "projects": safe(client.list_projects),
                "queries": safe(client.list_queries),
                "current_user": safe_dict(client.get_current_user),
            }
            self.after(0, lambda: self._on_metadata_loaded(client, data))

        threading.Thread(target=worker, daemon=True).start()

    def _on_metadata_loaded(self, client: RedmineClient, data: Dict[str, Any]):
        if client is not self._client or not self.winfo_exists():
            return
        self._metadata_loaded = True
        self._lookups["status_id"] = {str(s["id"]): s["name"] for s in data.get("statuses", [])}
        self._lookups["tracker_id"] = {str(t["id"]): t["name"] for t in data.get("trackers", [])}
        self._lookups["priority_id"] = {str(p["id"]): p["name"] for p in data.get("priorities", [])}
        self._lookups["project_id"] = {str(p["id"]): p["name"] for p in data.get("projects", [])}

        self._status_ids = {s["name"]: s["id"] for s in data.get("statuses", [])}
        self._tracker_ids = {t["name"]: t["id"] for t in data.get("trackers", [])}
        self._priority_ids = {p["name"]: p["id"] for p in data.get("priorities", [])}
        self._project_ids = {p["name"]: p["id"] for p in sorted(data.get("projects", []), key=lambda p: p["name"].lower())}

        # Parse Custom Queries (Hanya yang dibuat sendiri: is_public == False atau author id cocok)
        self._query_ids.clear()
        self._query_meta.clear()
        query_names = []
        project_lookup = self._lookups["project_id"]
        current_user_id = str((data.get("current_user") or {}).get("id") or "")

        for q in data.get("queries", []):
            qid = q.get("id")
            qname = (q.get("name") or "").strip()
            if not qid or not qname:
                continue

            is_public = q.get("is_public")
            q_user = q.get("user_id") or (q.get("user") or {}).get("id") or (q.get("author") or {}).get("id")
            is_mine = False
            if is_public is False or str(is_public).lower() in ("false", "0", "f"):
                is_mine = True
            elif q_user and current_user_id and str(q_user) == current_user_id:
                is_mine = True

            if not is_mine:
                continue

            proj_val = q.get("project_id")
            proj_id_int = None
            if isinstance(proj_val, dict):
                proj_id_int = proj_val.get("id")
            elif proj_val is not None:
                try:
                    proj_id_int = int(proj_val)
                except (ValueError, TypeError):
                    proj_id_int = None

            disp_name = qname
            if disp_name in self._query_ids:
                if proj_id_int and str(proj_id_int) in project_lookup:
                    disp_name = f"{qname} ({project_lookup[str(proj_id_int)]})"
                else:
                    disp_name = f"{qname} [#{qid}]"

            self._query_ids[disp_name] = qid
            self._query_meta[disp_name] = {"id": qid, "project_id": proj_id_int}
            query_names.append(disp_name)

        saved = self._saved_filters
        self._refill_menu(self.opt_query, [ALL_QUERIES] + query_names, saved.get("query"), ALL_QUERIES)
        self._refill_menu(self.opt_status, list(STATUS_FILTERS.keys()) + list(self._status_ids.keys()), saved.get("status"), DEFAULT_STATUS_FILTER)
        self._refill_menu(self.opt_project, [ALL_PROJECTS] + list(self._project_ids.keys()), saved.get("project"), ALL_PROJECTS)
        self._refill_menu(self.opt_tracker, [ALL_TRACKERS] + list(self._tracker_ids.keys()), saved.get("tracker"), ALL_TRACKERS)
        self._refill_menu(self.opt_priority, [ALL_PRIORITIES] + list(self._priority_ids.keys()), saved.get("priority"), ALL_PRIORITIES)

        # Filter tersimpan (query/project/tracker/priority) baru bisa dipakai setelah id-nya diketahui
        params_changed = any(
            saved.get(key) not in (None, default) for key, default in
            (("project", ALL_PROJECTS), ("tracker", ALL_TRACKERS), ("priority", ALL_PRIORITIES), ("query", ALL_QUERIES))
        ) or saved.get("status") in self._status_ids
        if params_changed:
            self._load_issues()

    @staticmethod
    def _refill_menu(menu: ctk.CTkOptionMenu, values: List[str], preferred: Optional[str], default: str):
        current = menu.get()
        menu.configure(values=values)
        if preferred in values and current in (default, preferred):
            menu.set(preferred)
        elif current not in values:
            menu.set(default)

    def _load_issues(self):
        if self._client is None:
            return
        self._needs_reload = False
        self._request_seq += 1
        seq = self._request_seq
        self._is_loading = True
        self.btn_refresh.configure(state="disabled")
        self._update_pager()
        self._set_status("Memuat task dari Redmine...")

        client = self._client
        params = self._build_params()
        per_page = self._per_page()
        offset = self._page * per_page

        def worker():
            try:
                issues, total = client.list_issues(params, limit=per_page, offset=offset)
                self.after(0, lambda: self._on_issues_loaded(seq, issues, total))
            except RedmineError as error:
                message = str(error)
                self.after(0, lambda: self._on_issues_failed(seq, message))

        threading.Thread(target=worker, daemon=True).start()

    def _on_issues_loaded(self, seq: int, issues: List[Dict[str, Any]], total: int):
        if seq != self._request_seq or not self.winfo_exists():
            return  # respons usang dari filter sebelumnya
        self._is_loading = False
        self._has_loaded = True
        self.btn_refresh.configure(state="normal")
        self._issues, self._total = issues, total
        if self._page > 0 and not issues and total:
            self._page = self._page_count() - 1
            self._load_issues()
            return
        for issue in issues:
            for ref in (issue.get("assigned_to"), issue.get("author")):
                if ref and ref.get("id"):
                    self._lookups["assigned_to_id"][str(ref["id"])] = ref.get("name", "")
        self._render_issues()
        self._update_pager()

    def _on_issues_failed(self, seq: int, message: str):
        if seq != self._request_seq or not self.winfo_exists():
            return
        self._is_loading = False
        self.btn_refresh.configure(state="normal")
        self._update_pager()
        self._set_status(f"Gagal memuat task: {message}", is_error=True)

    def _render_issues(self):
        self.tree.delete(*self.tree.get_children())
        self._issue_by_item.clear()
        today = date.today().isoformat()

        for issue in self._issues:
            status = issue.get("status") or {}
            status_name = status.get("name", "-")
            is_closed = bool(status.get("is_closed"))

            values = (
                f"#{issue.get('id')}",
                (issue.get("project") or {}).get("name", "-"),
                (issue.get("tracker") or {}).get("name", "-"),
                status_name,
                (issue.get("priority") or {}).get("name", "-"),
                issue.get("subject", ""),
                format_date(issue.get("due_date")),
                f"{issue.get('done_ratio', 0)}%",
                format_datetime(issue.get("updated_on")),
            )

            status_tag = self._get_status_tag(status_name, is_closed)
            tags = [status_tag]
            if is_closed:
                tags.append("closed")
            elif issue.get("due_date") and issue["due_date"] < today:
                tags.append("overdue")

            item_id = self.tree.insert("", "end", values=values, tags=tags)
            self._issue_by_item[item_id] = issue

        if self._has_loaded:
            if self._total:
                start = self._page * self._per_page() + 1
                end = start + len(self._issues) - 1
                text = f"Menampilkan {start}–{end} dari {self._total} task"
            else:
                text = "Tidak ada task yang cocok dengan filter"
            self._set_status(f"{text}  •  diperbarui {datetime.now().strftime('%H:%M:%S')}")

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _update_bell(self):
        if not self.winfo_exists():
            return
        unread = self.notifications.unread
        self.btn_bell.configure(
            text=f" {unread}" if unread else "",
            width=54 if unread else 34,
            fg_color=COLORS["accent_subtle"] if unread else COLORS["surface"],
            border_color=COLORS["accent_border"] if unread else COLORS["line"],
            text_color=COLORS["accent_text"],
            image=get_icon("bell", (15, 15), COLORS["accent_text"] if unread else COLORS["text"]),
        )

    def _show_notification_menu(self):
        menu = tk.Menu(
            self, tearoff=0, bg=get_color("surface"), fg=get_color("text"),
            activebackground=get_color("accent"), activeforeground="#FFFFFF", bd=1
        )
        items = self.notifications.items[:15]
        if not items:
            menu.add_command(label="Belum ada notifikasi", state="disabled")
        for idx, item in enumerate(items):
            prefix = "● " if idx < self.notifications.unread else "   "
            label = f"{prefix}{item['received_at'].strftime('%H:%M')}  {item['title'][:45]} — {item['message'][:60]}"
            menu.add_command(label=label, command=lambda i=item["issue_id"]: self.open_issue_tab(i))
        if items:
            menu.add_separator()
            menu.add_command(label="Hapus semua notifikasi", command=self.notifications.clear)
        x = self.btn_bell.winfo_rootx()
        y = self.btn_bell.winfo_rooty() + self.btn_bell.winfo_height()
        self.notifications.mark_all_read()
        menu.tk_popup(x, y)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_account_dialog(self):
        RedmineAccountDialog(self.app, self.db, on_saved=self._on_account_saved)

    def _on_account_saved(self):
        self._has_loaded = False
        self.refresh()
        if self._on_account_changed:
            self._on_account_changed()

    def _selected_issue(self) -> Optional[Dict[str, Any]]:
        selection = self.tree.selection()
        return self._issue_by_item.get(selection[0]) if selection else None

    def _on_tree_double_click(self, event):
        if self.tree.identify_row(event.y):
            self._open_selected_tab()

    def _open_selected_tab(self):
        issue = self._selected_issue()
        if issue:
            self.open_issue_tab(issue["id"])

    def _open_selected_in_browser(self):
        issue = self._selected_issue()
        if issue and self._client:
            webbrowser.open(self._client.issue_url(issue["id"]))

    def _copy_selected(self, field: str):
        issue = self._selected_issue()
        if not issue or not self._client:
            return
        if field == "id":
            text = f"#{issue['id']}"
        elif field == "subject":
            text = issue.get("subject", "")
        else:
            text = self._client.issue_url(issue["id"])
        self.clipboard_clear()
        self.clipboard_append(text)

    def _open_edit_task_dialog(self):
        issue = self._selected_issue()
        if not issue or not self._client:
            return
        issue_id = issue["id"]
        client = self._client

        self._set_status(f"Mempersiapkan form edit task #{issue_id}...")

        def worker():
            try:
                full_issue = client.get_issue(issue_id)
            except Exception:
                full_issue = issue
            self.after(0, lambda: self._show_edit_task_dialog(full_issue))

        threading.Thread(target=worker, daemon=True).start()

    def _show_edit_task_dialog(self, issue: Dict[str, Any]):
        if not self.winfo_exists() or not self._client:
            return
        self._set_status("")
        RedmineEditTaskDialog(
            parent=self.winfo_toplevel(),
            client=self._client,
            issue=issue,
            lookups=self._lookups,
            status_ids=self._status_ids,
            priority_ids=self._priority_ids,
            on_saved=self._on_task_updated_from_dialog,
        )

    def _on_task_updated_from_dialog(self):
        self._load_issues()
        for panel in self._issue_panels.values():
            panel.refresh()

    def _quick_change_status(self, issue_id: int, status_id: int, status_name: str):
        if not self._client:
            return
        client = self._client
        self._set_status(f"Mengubah status task #{issue_id} ke '{status_name}'...")

        def worker():
            try:
                client.update_issue_status(issue_id, status_id)
                self.after(0, lambda: self._on_quick_status_success(issue_id, status_name))
            except RedmineError as err:
                msg = str(err)
                self.after(0, lambda: self._set_status(f"Gagal mengubah status: {msg}", is_error=True))
            except Exception as err:
                msg = str(err)
                self.after(0, lambda: self._set_status(f"Error: {msg}", is_error=True))

        threading.Thread(target=worker, daemon=True).start()

    def _on_quick_status_success(self, issue_id: int, status_name: str):
        if not self.winfo_exists():
            return
        self._set_status(f"Status task #{issue_id} berhasil diubah ke '{status_name}'.")
        self._load_issues()
        if issue_id in self._issue_panels:
            self._issue_panels[issue_id].refresh()

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        issue = self._selected_issue()
        if not issue:
            return

        menu = tk.Menu(
            self, tearoff=0, bg=get_color("surface"), fg=get_color("text"),
            activebackground=get_color("accent"), activeforeground="#FFFFFF", bd=1
        )
        menu.add_command(label="Buka Detail (Tab Baru)", command=self._open_selected_tab)
        menu.add_command(label="Buka di Browser", command=self._open_selected_in_browser)
        menu.add_separator()
        menu.add_command(label="Edit Task...", command=self._open_edit_task_dialog)

        # Quick Status submenu
        if self._status_ids:
            status_menu = tk.Menu(
                menu, tearoff=0, bg=get_color("surface"), fg=get_color("text"),
                activebackground=get_color("accent"), activeforeground="#FFFFFF", bd=1
            )
            current_status = (issue.get("status") or {}).get("name", "")
            for name, sid in self._status_ids.items():
                prefix = "✓ " if name == current_status else "   "
                status_menu.add_command(
                    label=f"{prefix}{name}",
                    command=lambda s_id=sid, s_name=name, i_id=issue["id"]: self._quick_change_status(i_id, s_id, s_name)
                )
            menu.add_cascade(label="Ubah Status Cepat", menu=status_menu)

        menu.add_separator()
        menu.add_command(label="Copy ID Task", command=lambda: self._copy_selected("id"))
        menu.add_command(label="Copy Subject", command=lambda: self._copy_selected("subject"))
        menu.add_command(label="Copy URL Task", command=lambda: self._copy_selected("url"))

        menu.tk_popup(event.x_root, event.y_root)
