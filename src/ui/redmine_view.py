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
from ui.redmine_issue_panel import RedmineIssuePanel, format_date, format_datetime

SCOPE_FILTERS = {
    "Assigned ke saya": ("assigned_to_id", "me"),
    "Dibuat oleh saya": ("author_id", "me"),
    "Saya watch": ("watcher_id", "me"),
}
DUE_FILTERS = ["Semua", "Terlambat", "Hari ini", "7 hari ke depan", "30 hari ke depan", "Tanpa due date"]
UPDATED_FILTERS = ["Semua", "Hari ini", "7 hari terakhir", "30 hari terakhir"]
PER_PAGE_OPTIONS = ["25", "50", "100"]
ALL_PROJECTS = "Semua project"
ALL_TRACKERS = "Semua tracker"
ALL_PRIORITIES = "Semua priority"

# kolom tabel -> (judul, lebar, anchor, stretch, sort key Redmine)
COLUMNS = {
    "id": ("#", 60, "center", False, "id"),
    "project": ("Project", 130, "w", False, "project"),
    "tracker": ("Tracker", 80, "center", False, "tracker"),
    "status": ("Status", 95, "center", False, "status"),
    "priority": ("Priority", 75, "center", False, "priority"),
    "subject": ("Subject", 280, "w", True, "subject"),
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
                text_format=self.db.get_setting("redmine_text_format", "auto")
            )
            self._issue_panels[issue_id] = panel
            self._tab_order.append(issue_id)
        self._select_tab(issue_id)

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        # 1. HEADER
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
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

        # 2. TAB STRIP
        self.tab_strip = ctk.CTkFrame(self, fg_color="transparent", height=32)
        self.tab_strip.grid(row=1, column=0, sticky="ew", pady=(0, 8))

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

    def _filter_menu(self, parent, values: List[str], initial: str) -> ctk.CTkOptionMenu:
        menu = ctk.CTkOptionMenu(
            parent, values=values, height=30, corner_radius=7, dynamic_resizing=False,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=12),
            command=lambda _: self._on_filter_changed()
        )
        menu.set(initial if initial in values else values[0])
        return menu

    def _build_filter_card(self):
        card = ctk.CTkFrame(self.list_page, fg_color=COLORS["surface"], corner_radius=8, border_width=1, border_color=COLORS["line"])
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for col in range(5):
            card.grid_columnconfigure(col, weight=1, uniform="filters")

        saved = self._saved_filters

        def caption(text: str, row: int, col: int, colspan: int = 1):
            ctk.CTkLabel(card, text=text, text_color=COLORS["muted"], font=ctk.CTkFont(size=11, weight="bold"), anchor="w").grid(
                row=row, column=col, columnspan=colspan, sticky="w", padx=(12 if col == 0 else 4, 4), pady=(8 if row == 0 else 4, 0)
            )

        def place(widget, row: int, col: int, colspan: int = 1, pady=(2, 0)):
            widget.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=(12 if col == 0 else 4, 12 if col + colspan == 5 else 4), pady=pady)

        caption("Scope", 0, 0)
        caption("Status", 0, 1)
        caption("Project", 0, 2)
        caption("Tracker", 0, 3)
        caption("Priority", 0, 4)
        self.opt_scope = self._filter_menu(card, list(SCOPE_FILTERS.keys()), saved.get("scope", ""))
        self.opt_status = self._filter_menu(card, list(STATUS_FILTERS.keys()), saved.get("status", ""))
        self.opt_project = self._filter_menu(card, [ALL_PROJECTS], ALL_PROJECTS)
        self.opt_tracker = self._filter_menu(card, [ALL_TRACKERS], ALL_TRACKERS)
        self.opt_priority = self._filter_menu(card, [ALL_PRIORITIES], ALL_PRIORITIES)
        for col, menu in enumerate([self.opt_scope, self.opt_status, self.opt_project, self.opt_tracker, self.opt_priority]):
            place(menu, 1, col)

        caption("Due date", 2, 0)
        caption("Updated", 2, 1)
        caption("Subject / #ID", 2, 2, colspan=2)
        self.opt_due = self._filter_menu(card, DUE_FILTERS, saved.get("due", ""))
        self.opt_updated = self._filter_menu(card, UPDATED_FILTERS, saved.get("updated", ""))
        place(self.opt_due, 3, 0, pady=(2, 10))
        place(self.opt_updated, 3, 1, pady=(2, 10))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_typed)
        search = ctk.CTkEntry(
            card, textvariable=self.search_var, placeholder_text="Cari subject atau nomor task...",
            height=30, corner_radius=7, border_width=1, border_color=COLORS["line"], fg_color=COLORS["input_bg"],
            text_color=COLORS["text"], placeholder_text_color=COLORS["muted"]
        )
        place(search, 3, 2, colspan=2, pady=(2, 10))
        search.bind("<Return>", lambda _: self._apply_search_now())

        actions = ctk.CTkFrame(card, fg_color="transparent")
        place(actions, 3, 4, pady=(2, 10))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions, text="Reset", height=30, corner_radius=7, fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["line"], font=ctk.CTkFont(size=12),
            command=self._reset_filters
        ).grid(row=0, column=0, sticky="ew")
        self.btn_refresh = ctk.CTkButton(
            actions, text="", image=get_icon("refresh-cw", (14, 14), "#FFFFFF"), width=34, height=30, corner_radius=7,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self.refresh
        )
        self.btn_refresh.grid(row=0, column=1, padx=(6, 0))

    def _build_table(self):
        self.table_container = ctk.CTkFrame(self.list_page, fg_color=COLORS["input_bg"], border_width=1, border_color=COLORS["line"], corner_radius=6)
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

    def _apply_tag_colors(self):
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
        for key in self._tab_order:
            active = key == self._active_tab
            tab = ctk.CTkFrame(
                self.tab_strip, corner_radius=8, border_width=1,
                fg_color=COLORS["accent_subtle"] if active else COLORS["surface"],
                border_color=COLORS["accent_border"] if active else COLORS["line"],
            )
            tab.pack(side="left", padx=(0, 6))
            icon = "list-checks" if key == LIST_TAB else "file-text"
            color = COLORS["accent_text"] if active else COLORS["text_secondary"]
            btn = ctk.CTkButton(
                tab, text=f" {self._tab_titles.get(key, key)}", image=get_icon(icon, (13, 13), color), compound="left",
                height=28, corner_radius=7, fg_color="transparent", hover_color=COLORS["surface_hover"],
                text_color=color, font=ctk.CTkFont(size=12, weight="bold" if active else "normal"),
                command=lambda k=key: self._select_tab(k)
            )
            btn.pack(side="left", padx=(2, 0 if key != LIST_TAB else 2), pady=2)
            if key != LIST_TAB:
                btn.bind("<Button-2>", lambda _e, k=key: self._close_tab(k))
                ctk.CTkButton(
                    tab, text="", image=get_icon("x", (11, 11), COLORS["muted"]), width=22, height=22, corner_radius=6,
                    fg_color="transparent", hover_color=COLORS["surface_hover"], command=lambda k=key: self._close_tab(k)
                ).pack(side="left", padx=(0, 4))

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
            "scope": self.opt_scope.get(), "status": self.opt_status.get(), "project": self.opt_project.get(),
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
        scope_key, scope_value = SCOPE_FILTERS.get(self.opt_scope.get(), ("assigned_to_id", "me"))
        params: Dict[str, Any] = {scope_key: scope_value}

        status = self.opt_status.get()
        params["status_id"] = STATUS_FILTERS[status] if status in STATUS_FILTERS else self._status_ids.get(status, "open")
        if self.opt_project.get() in self._project_ids:
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
            except RedmineError:
                return []

        def worker():
            data = {
                "statuses": safe(client.list_statuses),
                "trackers": safe(client.list_trackers),
                "priorities": safe(client.list_priorities),
                "projects": safe(client.list_projects),
            }
            self.after(0, lambda: self._on_metadata_loaded(client, data))

        threading.Thread(target=worker, daemon=True).start()

    def _on_metadata_loaded(self, client: RedmineClient, data: Dict[str, List[Dict[str, Any]]]):
        if client is not self._client or not self.winfo_exists():
            return
        self._metadata_loaded = True
        self._lookups["status_id"] = {str(s["id"]): s["name"] for s in data["statuses"]}
        self._lookups["tracker_id"] = {str(t["id"]): t["name"] for t in data["trackers"]}
        self._lookups["priority_id"] = {str(p["id"]): p["name"] for p in data["priorities"]}
        self._lookups["project_id"] = {str(p["id"]): p["name"] for p in data["projects"]}

        self._status_ids = {s["name"]: s["id"] for s in data["statuses"]}
        self._tracker_ids = {t["name"]: t["id"] for t in data["trackers"]}
        self._priority_ids = {p["name"]: p["id"] for p in data["priorities"]}
        self._project_ids = {p["name"]: p["id"] for p in sorted(data["projects"], key=lambda p: p["name"].lower())}

        saved = self._saved_filters
        # Status spesifik ditaruh setelah opsi standar Open / Closed / Semua
        self._refill_menu(self.opt_status, list(STATUS_FILTERS.keys()) + list(self._status_ids.keys()), saved.get("status"), DEFAULT_STATUS_FILTER)
        self._refill_menu(self.opt_project, [ALL_PROJECTS] + list(self._project_ids.keys()), saved.get("project"), ALL_PROJECTS)
        self._refill_menu(self.opt_tracker, [ALL_TRACKERS] + list(self._tracker_ids.keys()), saved.get("tracker"), ALL_TRACKERS)
        self._refill_menu(self.opt_priority, [ALL_PRIORITIES] + list(self._priority_ids.keys()), saved.get("priority"), ALL_PRIORITIES)

        # Filter tersimpan (project/tracker/priority) baru bisa dipakai setelah id-nya diketahui
        params_changed = any(
            saved.get(key) not in (None, default) for key, default in
            (("project", ALL_PROJECTS), ("tracker", ALL_TRACKERS), ("priority", ALL_PRIORITIES))
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
            values = (
                f"#{issue.get('id')}",
                (issue.get("project") or {}).get("name", "-"),
                (issue.get("tracker") or {}).get("name", "-"),
                status.get("name", "-"),
                (issue.get("priority") or {}).get("name", "-"),
                issue.get("subject", ""),
                format_date(issue.get("due_date")),
                f"{issue.get('done_ratio', 0)}%",
                format_datetime(issue.get("updated_on")),
            )
            tags = []
            if status.get("is_closed"):
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

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        self.context_menu.tk_popup(event.x_root, event.y_root)
