import asyncio
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Set

import customtkinter as ctk

import pull_service
from theme import COLORS
from icons import get_icon
from ui.bulk_host_dialog import BulkHostDialog
from ui.db_tool_import_dialog import DbToolImportDialog
from ui.export_dialog import ExportDialog
from ui.host_dialog import HostDialog
from ui.import_dialog import ImportDialog
from ui.import_source_dialog import ImportSourceDialog
from ui.terminal_window import TerminalWindow


class HostsView(ctk.CTkFrame):
    """Tampilan 'Pull Blast': daftar host berkecepatan tinggi (<5ms),
    pencarian ter-debounce, filter grup, aksi git pull massal dan manajemen server.
    """

    def __init__(self, parent: ctk.CTk, db_manager: Any, on_data_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color=COLORS["window"])
        self.app = parent
        self.db = db_manager
        self._on_data_changed = on_data_changed

        self.selected_host_ids: Set[int] = set()
        self._all_hosts: List[Dict[str, Any]] = []
        self._current_filtered_hosts: List[Dict[str, Any]] = []
        self.search_debounce_id = None
        self._needs_refresh = False
        self._is_loaded = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=3)  # Tabel Server
        self.grid_rowconfigure(4, weight=2)  # Log Output

        self._setup_ui()
        self.refresh()

    def mark_needs_refresh(self):
        """Tandai bahwa data host berubah; refresh langsung jika tab sedang aktif terlihat."""
        if self.winfo_ismapped():
            self.refresh()
        else:
            self._needs_refresh = True

    def refresh(self):
        """Memuat ulang data dari SQLite tanpa dekripsi password (<2ms) dan populate tabel."""
        self._needs_refresh = False
        self._all_hosts = self.db.get_all_hosts(decrypt_passwords=False)
        self._refresh_filter_options()
        self._apply_filter()
        self._is_loaded = True

    def _notify_data_changed(self):
        """Beritahu view lain (DB Blast) bahwa data host berubah karena berbagi tabel yang sama."""
        if self._on_data_changed:
            self._on_data_changed()

    def _refresh_and_notify(self):
        self.refresh()
        self._notify_data_changed()

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def open_import_dialog(self):
        ImportSourceDialog(parent=self.app, on_select=self._handle_import_source_selected)

    def _handle_import_source_selected(self, source: str):
        if source == "pullman":
            ImportDialog(
                parent=self.app,
                db_manager=self.db,
                on_import_callback=self._refresh_and_notify
            )
        else:
            DbToolImportDialog(
                parent=self.app,
                db_manager=self.db,
                source=source,
                on_import_callback=self._refresh_and_notify
            )

    def open_export_dialog(self):
        ExportDialog(parent=self.app, db_manager=self.db)

    def _add_host_dialog(self):
        HostDialog(
            parent=self.app,
            db_manager=self.db,
            on_save_callback=self._refresh_and_notify
        )

    def _edit_host_dialog(self, host: dict):
        full_host = self.db.get_host_by_id(host['id']) or host
        HostDialog(
            parent=self.app,
            db_manager=self.db,
            host_data=full_host,
            on_save_callback=self._refresh_and_notify
        )

    def _delete_host(self, host_id: int, host_label: str = ""):
        name = host_label or f"Host #{host_id}"
        if messagebox.askyesno(
            "Hapus Host",
            f"Yakin ingin menghapus server '{name}'?\n\nJika server ini terhubung ke DB Blast, koneksi database terkait juga akan terhapus."
        ):
            self.db.delete_host(host_id)
            self.selected_host_ids.discard(host_id)
            self._refresh_and_notify()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        # 1. HEADER
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure((1, 2, 3, 4), weight=0)

        self.lbl_title = ctk.CTkLabel(
            header,
            text="Servers",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.lbl_title.grid(row=0, column=0, sticky="w")

        # Filter Group & Check All
        filter_frame = ctk.CTkFrame(header, fg_color="transparent")
        filter_frame.grid(row=0, column=1, sticky="e", padx=(0, 10))

        lbl_filter = ctk.CTkLabel(filter_frame, text="Group:", text_color=COLORS["muted"], font=ctk.CTkFont(size=12))
        lbl_filter.pack(side="left", padx=(0, 6))

        self.filter_group_opt = ctk.CTkOptionMenu(
            filter_frame,
            values=["All Groups"],
            width=140,
            height=34,
            corner_radius=8,
            fg_color=COLORS["surface"],
            text_color=COLORS["text"],
            button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"],
            command=lambda _: self._apply_filter()
        )
        self.filter_group_opt.pack(side="left")

        btn_refresh = ctk.CTkButton(
            header,
            text="",
            image=get_icon("refresh-cw", (14, 14), COLORS["text"]),
            width=34,
            height=34,
            corner_radius=8,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            border_width=1,
            border_color=COLORS["line"],
            command=self.refresh
        )
        btn_refresh.grid(row=0, column=2, sticky="e", padx=(5, 0))

        btn_new_host = ctk.CTkButton(
            header,
            text=" New Host",
            image=get_icon("plus", (14, 14), COLORS["text"]),
            compound="left",
            width=112,
            height=34,
            corner_radius=8,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._add_host_dialog
        )
        btn_new_host.grid(row=0, column=3, sticky="e", padx=(5, 0))

        self.btn_run_all = ctk.CTkButton(
            header,
            text=" Run All",
            image=get_icon("zap", (14, 14), "#FFFFFF"),
            compound="left",
            width=120,
            height=34,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._run_all_hosts
        )
        self.btn_run_all.grid(row=0, column=4, sticky="e", padx=(5, 0))

        # 2. SEARCH BAR
        search_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        search_frame.grid_columnconfigure(1, weight=1)

        lbl_search = ctk.CTkLabel(search_frame, text="", image=get_icon("search", (15, 15), COLORS["muted"]))
        lbl_search.grid(row=0, column=0, padx=(12, 6))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Cari host berdasarkan nama, IP, username, branch, atau repo path...",
            textvariable=self.search_var,
            height=36,
            corner_radius=8,
            border_width=0,
            fg_color="transparent",
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["muted"]
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        # 3. HIGH-PERFORMANCE SERVERS TABLE (TTK TREEVIEW - SUB-5MS)
        table_container = tk.Frame(self, bg=COLORS["input_bg"], highlightthickness=1, highlightbackground=COLORS["line"])
        table_container.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Pullman.Treeview",
            background=COLORS["input_bg"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["input_bg"],
            rowheight=29,
            font=("Segoe UI", 9),
            borderwidth=0
        )
        style.configure(
            "Pullman.Treeview.Heading",
            background=COLORS["surface"],
            foreground=COLORS["muted"],
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            borderwidth=0
        )
        style.map(
            "Pullman.Treeview",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", "#FFFFFF")]
        )

        self.tree = ttk.Treeview(
            table_container,
            columns=("chk", "label", "group", "target", "branch", "repo", "status"),
            show="headings",
            style="Pullman.Treeview",
            selectmode="browse"
        )
        self.tree.heading("chk", text="[✓]", anchor="center", command=self._toggle_check_all)
        self.tree.heading("label", text="Server Name", anchor="w")
        self.tree.heading("group", text="Group", anchor="center")
        self.tree.heading("target", text="SSH Target", anchor="w")
        self.tree.heading("branch", text="Git Branch", anchor="center")
        self.tree.heading("repo", text="Repo Path", anchor="w")
        self.tree.heading("status", text="Status", anchor="center")

        self.tree.column("chk", width=36, anchor="center", stretch=False)
        self.tree.column("label", width=180, anchor="w")
        self.tree.column("group", width=110, anchor="center", stretch=False)
        self.tree.column("target", width=170, anchor="w")
        self.tree.column("branch", width=95, anchor="center", stretch=False)
        self.tree.column("repo", width=190, anchor="w")
        self.tree.column("status", width=90, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Treeview event bindings
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)
        self.tree.bind("<space>", self._on_tree_space)
        self.tree.bind("<Button-3>", self._show_tree_context_menu)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select_change)

        self._create_tree_context_menu()

        # 4. ACTION TOOLBAR & CONSOLE CONTROLS
        action_bar = ctk.CTkFrame(self, fg_color="transparent")
        action_bar.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        action_bar.grid_columnconfigure(0, weight=1)

        left_actions = ctk.CTkFrame(action_bar, fg_color="transparent")
        left_actions.pack(side="left")

        self.btn_action_pull = ctk.CTkButton(
            left_actions,
            text=" Pull Single",
            image=get_icon("play", (13, 13), "#FFFFFF"),
            compound="left",
            width=105,
            height=30,
            corner_radius=7,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._run_single_host
        )
        self.btn_action_pull.pack(side="left", padx=(0, 6))

        self.btn_action_test = ctk.CTkButton(
            left_actions,
            text=" Test Connection",
            image=get_icon("activity", (13, 13), COLORS["accent_text"]),
            compound="left",
            width=135,
            height=30,
            corner_radius=7,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._test_selected_host
        )
        self.btn_action_test.pack(side="left", padx=(0, 6))

        self.btn_action_term = ctk.CTkButton(
            left_actions,
            text=" Terminal",
            image=get_icon("terminal", (13, 13), COLORS["text_secondary"]),
            compound="left",
            width=92,
            height=30,
            corner_radius=7,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._terminal_selected_host
        )
        self.btn_action_term.pack(side="left", padx=(0, 6))

        self.btn_action_edit = ctk.CTkButton(
            left_actions,
            text=" Edit",
            image=get_icon("pencil", (13, 13), COLORS["text_secondary"]),
            compound="left",
            width=72,
            height=30,
            corner_radius=7,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._edit_selected_host
        )
        self.btn_action_edit.pack(side="left", padx=(0, 6))

        self.btn_action_del = ctk.CTkButton(
            left_actions,
            text=" Delete",
            image=get_icon("trash", (13, 13), COLORS["danger_text"]),
            compound="left",
            width=80,
            height=30,
            corner_radius=7,
            fg_color=COLORS["danger_subtle"],
            border_width=1,
            border_color=COLORS["danger_border"],
            text_color=COLORS["danger_text"],
            hover_color=COLORS["danger_hover"],
            font=ctk.CTkFont(size=11),
            command=self._delete_selected_host
        )
        self.btn_action_del.pack(side="left")

        right_actions = ctk.CTkFrame(action_bar, fg_color="transparent")
        right_actions.pack(side="right")

        btn_clear_log = ctk.CTkButton(
            right_actions,
            text=" Clear Log",
            image=get_icon("trash", (12, 12), COLORS["muted"]),
            compound="left",
            width=88,
            height=30,
            corner_radius=7,
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["line"],
            text_color=COLORS["muted"],
            hover_color=COLORS["surface_hover"],
            font=ctk.CTkFont(size=11),
            command=self._clear_output
        )
        btn_clear_log.pack(side="right")

        self._on_tree_select_change()

        # 5. EXECUTION OUTPUT CONSOLE
        output_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        output_frame.grid(row=4, column=0, sticky="nsew", pady=0)
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(1, weight=1)

        output_header = ctk.CTkFrame(output_frame, fg_color="transparent")
        output_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            output_header,
            text=" Execution Output",
            image=get_icon("terminal", (14, 14), COLORS["text"]),
            compound="left",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text"]
        ).pack(side="left")

        self.lbl_selected_hint = ctk.CTkLabel(
            output_header,
            text="Pilih baris host untuk mengaktifkan aksi individual",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"]
        )
        self.lbl_selected_hint.pack(side="right")

        self.output_textbox = ctk.CTkTextbox(
            output_frame,
            font=("Menlo", 12),
            wrap="none",
            corner_radius=8,
            border_width=0,
            fg_color=COLORS["console_bg"],
            text_color=COLORS["console_text"]
        )
        self.output_textbox.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))

    # ------------------------------------------------------------------
    # Filtering & Debounce
    # ------------------------------------------------------------------

    def _refresh_filter_options(self):
        groups = sorted(list({h.get("group_name") or "Default" for h in self._all_hosts}))
        group_names = ["All Groups"] + groups
        current_val = self.filter_group_opt.get()
        self.filter_group_opt.configure(values=group_names)
        if current_val in group_names:
            self.filter_group_opt.set(current_val)
        else:
            self.filter_group_opt.set("All Groups")

    def _on_search_changed(self, *_):
        """Debounce pencarian 20ms agar pengetikan instan dan responsif."""
        if self.search_debounce_id:
            self.after_cancel(self.search_debounce_id)
        self.search_debounce_id = self.after(20, self._apply_filter)

    def _apply_filter(self):
        """Menyaring host dari cache memori secara instan (<2ms) lalu mengisi Treeview."""
        query = self.search_var.get().strip().lower()
        selected_grp = self.filter_group_opt.get()

        matching = []
        for h in self._all_hosts:
            if selected_grp != "All Groups" and (h.get("group_name") or "Default") != selected_grp:
                continue
            if query:
                lbl = (h.get("label") or "").lower()
                hostname = (h.get("hostname") or "").lower()
                user = (h.get("username") or "").lower()
                branch = (h.get("git_branch") or "").lower()
                repo = (h.get("repo_path") or "").lower()
                if (query not in lbl and query not in hostname and 
                    query not in user and query not in branch and query not in repo):
                    continue
            matching.append(h)

        self._current_filtered_hosts = matching

        # Clear treeview items (<1ms)
        self.tree.delete(*self.tree.get_children())

        # Populate treeview items (<2ms)
        for h in matching:
            h_id = h["id"]
            chk_str = "[✓]" if h_id in self.selected_host_ids else "[ ]"
            target_str = f"{h.get('username', 'root')}@{h.get('hostname', '')}:{h.get('port', 22)}"
            branch_str = h.get("git_branch") or "-"
            repo_str = h.get("repo_path") or "/var/www/html"
            grp_str = h.get("group_name") or "Default"
            status_str = h.get("_status") or "Ready"

            self.tree.insert(
                "", "end",
                iid=str(h_id),
                values=(
                    chk_str,
                    h.get("label") or f"Host-{h_id}",
                    grp_str,
                    target_str,
                    branch_str,
                    repo_str,
                    status_str
                )
            )

        self.lbl_title.configure(text=f"Servers ({len(self._all_hosts)})")
        self._sync_check_all_state()
        self._update_run_button_text()
        self._on_tree_select_change()

    # ------------------------------------------------------------------
    # Context Menu & Selection
    # ------------------------------------------------------------------

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

        # Tentukan target host yang akan dipindahkan
        clicked_id = int(item)
        if clicked_id in self.selected_host_ids and len(self.selected_host_ids) > 1:
            target_ids = list(self.selected_host_ids)
            label_suffix = f" ({len(target_ids)} checked)"
        else:
            target_ids = [clicked_id]
            label_suffix = ""

        # Rebuild context menu dinamis
        self.context_menu.delete(0, "end")
        self.context_menu.add_command(label="⚡ Run Git Pull (Terminal)", command=self._run_single_host)
        self.context_menu.add_command(label="🧪 Test SSH Connection", command=self._test_selected_host)
        self.context_menu.add_command(label="💻 Open SSH Terminal (PuTTY/CMD)", command=self._terminal_selected_host)
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
                command=lambda gid=g["id"]: self._move_target_hosts_to_group(target_ids, gid)
            )
        if groups:
            group_menu.add_separator()
        group_menu.add_command(
            label="🚫  (None / Default)",
            command=lambda: self._move_target_hosts_to_group(target_ids, None)
        )
        group_menu.add_command(
            label="➕  Create New Group...",
            command=lambda: self._prompt_new_group_and_move(target_ids)
        )

        self.context_menu.add_cascade(label=f"📁 Move to Group{label_suffix}", menu=group_menu)
        self.context_menu.add_separator()
        if len(target_ids) > 1:
            self.context_menu.add_command(
                label=f"✏️ Bulk Edit ({len(target_ids)} Hosts)...",
                command=lambda: self._open_bulk_edit_dialog(target_ids)
            )
        else:
            self.context_menu.add_command(label="✏️ Edit Host", command=self._edit_selected_host)
        self.context_menu.add_command(label="🗑️ Delete Host", command=self._delete_selected_host)

        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _move_target_hosts_to_group(self, target_ids: List[int], group_id: Optional[int]):
        """Pindahkan daftar host target ke group tertentu."""
        self.db.move_hosts_to_group(target_ids, group_id)
        self._refresh_and_notify()

    def _prompt_new_group_and_move(self, target_ids: List[int]):
        """Minta input nama group baru, buat group, lalu pindahkan host target."""
        dialog = ctk.CTkInputDialog(text="Enter new group name:", title="New Group")
        group_name = dialog.get_input()
        if group_name and group_name.strip():
            new_group_id = self.db.add_group(group_name.strip())
            self._move_target_hosts_to_group(target_ids, new_group_id)

    def _on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        col = self.tree.identify_column(event.x)
        if col == "#1":  # Klik kolom checkbox
            self._toggle_row_check(item_id)
        self._on_tree_select_change()

    def _on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self._run_single_host()

    def _on_tree_space(self, event):
        sel = self.tree.selection()
        if sel:
            for item_id in sel:
                self._toggle_row_check(item_id)

    def _toggle_row_check(self, item_id: str):
        h_id = int(item_id)
        if h_id in self.selected_host_ids:
            self.selected_host_ids.remove(h_id)
            chk_str = "[ ]"
        else:
            self.selected_host_ids.add(h_id)
            chk_str = "[✓]"
        if self.tree.exists(item_id):
            curr_vals = list(self.tree.item(item_id, "values"))
            if curr_vals:
                curr_vals[0] = chk_str
                self.tree.item(item_id, values=curr_vals)
        self._sync_check_all_state()
        self._update_run_button_text()

    def _toggle_check_all(self):
        if not self._current_filtered_hosts:
            return
        all_chk = all(h["id"] in self.selected_host_ids for h in self._current_filtered_hosts)
        should_check = not all_chk

        for h in self._current_filtered_hosts:
            h_id = h["id"]
            str_id = str(h_id)
            if should_check:
                self.selected_host_ids.add(h_id)
                chk_str = "[✓]"
            else:
                self.selected_host_ids.discard(h_id)
                chk_str = "[ ]"
            if self.tree.exists(str_id):
                vals = list(self.tree.item(str_id, "values"))
                if vals:
                    vals[0] = chk_str
                    self.tree.item(str_id, values=vals)

        self._sync_check_all_state()
        self._update_run_button_text()

    def _sync_check_all_state(self):
        if self._current_filtered_hosts:
            all_chk = all(h["id"] in self.selected_host_ids for h in self._current_filtered_hosts)
            chk_icon = "[✓]" if all_chk else "[ ]"
        else:
            chk_icon = "[ ]"
        self.tree.heading("chk", text=chk_icon)

    def _update_run_button_text(self):
        count = len([h["id"] for h in self._current_filtered_hosts if h["id"] in self.selected_host_ids])
        selected_filter = self.filter_group_opt.get()
        if count > 0:
            self.btn_run_all.configure(text=f" Pull Selected ({count})", image=get_icon("zap", (14, 14), "#FFFFFF"))
        else:
            if selected_filter == "All Groups":
                self.btn_run_all.configure(text=" Run All", image=get_icon("zap", (14, 14), "#FFFFFF"))
            else:
                self.btn_run_all.configure(text=f" Run All ({selected_filter})", image=get_icon("zap", (14, 14), "#FFFFFF"))

    def _on_tree_select_change(self, event=None):
        sel = self.tree.selection()
        has_sel = bool(sel)

        if has_sel:
            self.btn_action_pull.configure(
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
            self.btn_action_term.configure(
                state="normal",
                fg_color=COLORS["surface"],
                hover_color=COLORS["surface_hover"],
                text_color=COLORS["text_secondary"],
                border_width=1,
                border_color=COLORS["line"],
                image=get_icon("terminal", (13, 13), COLORS["text_secondary"])
            )
            edit_text = f" Bulk Edit ({len(self.selected_host_ids)})" if len(self.selected_host_ids) > 1 else " Edit"
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
            if hasattr(self, "lbl_selected_hint"):
                h = self._get_selected_host()
                name = h.get("label", "") if h else ""
                self.lbl_selected_hint.configure(text=f"Server: {name}" if name else "")
        else:
            self.btn_action_pull.configure(
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
            self.btn_action_term.configure(
                state="disabled",
                fg_color=COLORS["surface"],
                border_width=1,
                border_color=COLORS["line"],
                text_color_disabled=COLORS["subtle"],
                image=get_icon("terminal", (13, 13), COLORS["subtle"])
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
            if hasattr(self, "lbl_selected_hint"):
                self.lbl_selected_hint.configure(text="Pilih server pada tabel untuk aksi single")

    def _update_tree_status(self, host_id: int, text: str):
        str_id = str(host_id)
        if self.tree.exists(str_id):
            self.tree.set(str_id, "status", text)
        for h in self._all_hosts:
            if h["id"] == host_id:
                h["_status"] = text
                break

    def _get_selected_host(self) -> Optional[Dict[str, Any]]:
        sel = self.tree.selection()
        if not sel:
            return None
        h_id = int(sel[0])
        return next((h for h in self._all_hosts if h["id"] == h_id), None)

    # ------------------------------------------------------------------
    # Selected Row Actions
    # ------------------------------------------------------------------

    def _run_single_host(self):
        host = self._get_selected_host()
        if host:
            self._open_terminal(host)

    def _test_selected_host(self):
        host = self._get_selected_host()
        if host:
            self._test_host_connection(host)

    def _terminal_selected_host(self):
        host = self._get_selected_host()
        if host:
            self._open_manual_terminal(host)

    def _edit_selected_host(self):
        checked_ids = list(self.selected_host_ids)
        if len(checked_ids) > 1:
            self._open_bulk_edit_dialog(checked_ids)
            return
        host = self._get_selected_host()
        if host:
            self._edit_host_dialog(host)

    def _open_bulk_edit_dialog(self, host_ids: List[int]):
        """Buka dialog bulk edit untuk daftar host_ids yang dipilih."""
        if not host_ids:
            return
        BulkHostDialog(
            parent=self.app,
            db_manager=self.db,
            host_ids=host_ids,
            on_save_callback=self._refresh_and_notify
        )

    def _delete_selected_host(self):
        host = self._get_selected_host()
        if host:
            self._delete_host(host["id"], host.get("label", ""))

    # ------------------------------------------------------------------
    # Terminal, Test & Bulk Pull
    # ------------------------------------------------------------------

    def _open_terminal(self, host: dict):
        """Buka in-app terminal dan terapkan credential Git global bila tersedia."""
        full_host = self.db.get_host_by_id(host["id"]) or dict(host)
        terminal_host = dict(full_host)
        global_credential = self.db.get_global_git_credential()
        if global_credential:
            terminal_host["git_user"] = global_credential["username"]
            terminal_host["git_pass"] = global_credential["password"]
        TerminalWindow(self.app, terminal_host)

    def _test_host_connection(self, host: dict):
        """Tes koneksi SSH ke remote host tanpa menjalankan perintah git pull."""
        self._update_tree_status(host["id"], "Testing...")
        self._append_output(f"🧪 [{host['label']}] Mengetes koneksi SSH ke {host['hostname']}:{host.get('port', 22)}...\n")

        def worker():
            full_host = self.db.get_host_by_id(host["id"]) or host
            result = pull_service.test_connection(full_host)
            self.after(0, lambda: self._on_test_result(host, result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_result(self, host: dict, result: Dict[str, Any]):
        elapsed = result["elapsed_ms"]
        host_id = host["id"]
        if result["success"]:
            self._update_tree_status(host_id, "✓ Online")
            self._append_output(f"✓ [{host['label']}] Connection SUCCESSFUL ({elapsed} ms) -> {host['hostname']}:{host.get('port', 22)}\n")
            messagebox.showinfo(
                "Connection Successful",
                f"Koneksi SSH ke '{host['label']}' BERHASIL!\n\n"
                f"Host: {host['hostname']}:{host.get('port', 22)}\n"
                f"User: {host['username']}\n"
                f"Waktu respon: {elapsed} ms"
            )
        else:
            self._update_tree_status(host_id, "✗ Offline")
            error_msg = result["error"]
            self._append_output(f"✗ [{host['label']}] Connection FAILED: {error_msg}\n")
            messagebox.showerror(
                "Connection Failed",
                f"Koneksi SSH ke '{host['label']}' GAGAL!\n\n"
                f"Host: {host['hostname']}:{host.get('port', 22)}\n"
                f"Error: {error_msg}"
            )

    def _open_manual_terminal(self, host: dict):
        """Membuka sesi terminal interaktif (macOS Terminal/sshpass, PuTTY, atau Windows CMD) untuk akses manual."""
        full_host = self.db.get_host_by_id(host["id"]) or host
        hostname = full_host.get("hostname", "")
        port = str(full_host.get("port", 22))
        username = full_host.get("username", "")
        password = full_host.get("password", "")
        key_file = full_host.get("key_filename", "")
        auth_type = full_host.get("auth_type", "password")

        if password:
            try:
                self.app.clipboard_clear()
                self.app.clipboard_append(password)
                self._append_output(f"ℹ [{host['label']}] Password SSH telah disalin ke clipboard.\n")
            except Exception:
                pass

        if sys.platform == "darwin":
            extra_opts = "-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa"
            sshpass_bin = shutil.which("sshpass")

            if auth_type == "key" and key_file:
                ssh_cmd = f"ssh -i '{key_file}' {extra_opts} -p {port} {username}@{hostname}"
                applescript = f'tell application "Terminal" to do script "{ssh_cmd}"'
            elif auth_type == "password" and password and sshpass_bin:
                ssh_cmd = f"{sshpass_bin} -p '{password}' ssh {extra_opts} -p {port} {username}@{hostname}"
                applescript = f'tell application "Terminal" to do script "{ssh_cmd}"'
            elif auth_type == "password" and password:
                ssh_cmd = f"ssh {extra_opts} -p {port} {username}@{hostname}"
                applescript = f'''
                tell application "Terminal"
                    activate
                    set newTab to do script "{ssh_cmd}"
                    delay 1.5
                    do script "{password}" in newTab
                end tell
                '''
            else:
                ssh_cmd = f"ssh {extra_opts} -p {port} {username}@{hostname}"
                applescript = f'tell application "Terminal" to do script "{ssh_cmd}"'

            try:
                subprocess.Popen(["osascript", "-e", applescript])
                self._append_output(f"🚀 [{host['label']}] Membuka Terminal macOS ({hostname}:{port})...\n")
                return
            except Exception as e:
                self._append_output(f"Gagal membuka Terminal macOS ({e}), mencoba fallback...\n")

        # Windows PuTTY / CMD
        putty_exe = shutil.which("putty")
        if not putty_exe:
            for candidate in [
                r"C:\Program Files\PuTTY\putty.exe",
                r"C:\Program Files (x86)\PuTTY\putty.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\PuTTY\putty.exe")
            ]:
                if os.path.exists(candidate):
                    putty_exe = candidate
                    break

        if putty_exe:
            cmd = [putty_exe, "-ssh", "-P", port, "-l", username]
            if auth_type == "password" and password:
                cmd.extend(["-pw", password])
            elif auth_type == "key" and key_file and key_file.lower().endswith(".ppk"):
                cmd.extend(["-i", key_file])
            cmd.append(hostname)

            try:
                subprocess.Popen(cmd)
                self._append_output(f"🚀 [{host['label']}] Membuka sesi SSH via PuTTY ({hostname}:{port})...\n")
                return
            except Exception as e:
                self._append_output(f"Gagal membuka PuTTY ({e}), beralih ke Command Prompt...\n")

        # Fallback ke Command Prompt Windows
        title = f"SSH - {host['label']} ({hostname})"
        if auth_type == "key" and key_file:
            ssh_target = f'ssh -i "{key_file}" -p {port} {username}@{hostname}'
        else:
            ssh_target = f'ssh -p {port} {username}@{hostname}'

        full_cmd = f'start "{title}" cmd /k "{ssh_target}"'
        try:
            subprocess.Popen(full_cmd, shell=True)
            self._append_output(f"🚀 [{host['label']}] Membuka Command Prompt SSH: {ssh_target}\n")
        except Exception as e:
            messagebox.showerror("Terminal Error", f"Gagal membuka terminal: {e}")

    def _run_all_hosts(self):
        """Menjalankan git pull pada seluruh host yang dipilih di background thread tanpa freeze UI."""
        self._clear_output()

        if self.selected_host_ids:
            hosts = [h for h in self._current_filtered_hosts if h["id"] in self.selected_host_ids]
        else:
            hosts = self._current_filtered_hosts

        selected_filter = self.filter_group_opt.get()
        if not hosts:
            self._append_output(f"Tidak ada host yang dipilih di grup '{selected_filter}'.\n")
            return

        self.btn_run_all.configure(state="disabled")
        global_credential = self.db.get_global_git_credential()

        # Update status di treeview
        for h in hosts:
            self._update_tree_status(h["id"], "Pulling...")

        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Decrypt credentials in worker thread, keeping UI 100% fluid
                full_hosts = [self.db.get_host_by_id(h["id"]) or h for h in hosts]
                loop.run_until_complete(
                    pull_service.run_pull_on_hosts(full_hosts, global_credential, self._append_output)
                )
            finally:
                loop.close()

            def finish():
                self.btn_run_all.configure(state="normal")
                for h in hosts:
                    self._update_tree_status(h["id"], "Done")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _append_output(self, text: str):
        """Callback thread-safe untuk menulis log ke textbox."""
        def write():
            self.output_textbox.insert("end", text)
            self.output_textbox.see("end")
        self.after(0, write)

    def _clear_output(self):
        self.output_textbox.delete("1.0", "end")

