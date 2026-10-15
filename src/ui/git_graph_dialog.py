import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional, Tuple

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

try:
    import git
    from git import Repo, InvalidGitRepositoryError, NoSuchPathError, GitCommandError
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False

from theme import COLORS, get_color
from icons import get_icon, get_tk_image, get_file_type_icon, get_file_type_tk_image
from sftp_service import SFTPService
from terminal_launcher import launch_ssh_terminal, launch_local_terminal

# Palet warna cabang Git Graph (bergaya GitHub Desktop & GitKraken)
GRAPH_PALETTE = [
    (88, 166, 255),   # Blue (#58A6FF)
    (63, 185, 80),    # Emerald Green (#3FB950)
    (210, 153, 34),   # Amber/Orange (#D29922)
    (187, 128, 247),  # Purple (#BC8CFF)
    (248, 81, 73),    # Coral Red (#F85149)
    (57, 211, 239),   # Cyan (#39D3EF)
    (247, 120, 186),  # Hot Pink (#F778BA)
    (227, 179, 65),   # Gold Yellow (#E3B341)
]


class GitGraphDialog(ctk.CTkToplevel):
    """
    Dialog Git History, Commit & Sync Manager bergaya GitHub Desktop.
    Menyediakan:
    - Tab "Changes": Daftar file berubah di working directory, staging dengan checkbox, commit box.
    - Tab "History": Visual commit feed, branch graph, file navigator, dan commit diff.
    - Sync Actions: Push origin, Pull origin, Discard changes, Open Terminal.
    - Mendukung Local (via GitPython) & Remote Server (via SSH).
    """

    def __init__(
        self,
        parent: Any,
        host: Optional[Dict[str, Any]],
        target_dir: str,
        is_local: bool = False
    ):
        super().__init__(parent)
        self.host = host or {}
        self.target_dir = target_dir
        self.repo_root = target_dir
        self.is_local = is_local

        if not is_local and self.host:
            db = getattr(parent, "db", None) or getattr(getattr(parent, "app", None), "db", None)
            host_id = self.host.get("id")
            if db and host_id:
                full_h = db.get_host_by_id(host_id)
                if full_h:
                    self.host = dict(full_h)
            if db:
                global_cred = db.get_global_git_credential()
                if global_cred and not (self.host.get("git_user") and self.host.get("git_pass")):
                    self.host["git_user"] = global_cred.get("username")
                    self.host["git_pass"] = global_cred.get("password")

        dir_name = os.path.basename(target_dir.rstrip("/")) or target_dir
        host_label = "Local" if is_local else (self.host.get("label") or self.host.get("hostname") or "Remote")
        title_suffix = "" if is_local else " [sudo]"
        self.title(f"GitHub Desktop - {dir_name} ({host_label}){title_suffix}")
        self.geometry("1200x780")
        self.minsize(920, 560)
        self.configure(fg_color=COLORS["window"])

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # State History
        self._commits: List[Dict[str, Any]] = []
        self._graph_images: List[ImageTk.PhotoImage] = []
        self._current_branch = "main"
        self._is_loading = False

        # State Selected Commit (History Tab)
        self._selected_commit_hash = ""
        self._history_files_data: List[Dict[str, Any]] = []
        self._history_all_diff = ""

        # State Changes (Working Tree Tab)
        self._working_changes: List[Dict[str, Any]] = []  # dict: {path, orig_path, status, type, checked_var, add, del}
        self._selected_working_file: Optional[Dict[str, Any]] = None
        self._active_tab = "Changes"

        self._build_ui()
        self._refresh_all_data()

        try:
            self.state("zoomed")
        except Exception:
            pass
        self._bring_to_front()

    def _bring_to_front(self):
        """Memunculkan window Git Graph di paling depan dan memastikan status full screen / maximized."""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(250, lambda: self.attributes("-topmost", False) if self.winfo_exists() else None)
        except Exception:
            pass
        self.after(60, self._ensure_zoomed)

    def _ensure_zoomed(self):
        try:
            if self.winfo_exists():
                self.state("zoomed")
                self.lift()
                self.focus_force()
        except Exception:
            pass

    def _wrap_remote_sudo(self, cmd: str) -> str:
        """
        Membungkus perintah remote agar dieksekusi dengan hak akses root (sudo) secara otomatis
        tanpa pernah hanging (non-interactive sudo).
        Menyisipkan git safe.directory='*', GIT_PAGER=cat, GIT_TERMINAL_PROMPT=0.
        """
        env_prefix = "export GIT_PAGER=cat PAGER=cat GIT_TERMINAL_PROMPT=0; "
        full_script = f"{env_prefix}git() {{ command git -c safe.directory='*' \"$@\"; }}; {cmd}"
        escaped_script = full_script.replace("'", "'\\''")
        sh_cmd = f"sh -c '{escaped_script}'"

        username = (self.host.get("username") or "").strip().lower()
        if username == "root":
            return sh_cmd

        password = self.host.get("password")
        if password:
            escaped_pass = password.replace("'", "'\\''")
            return f"(printf '%s\\n' '{escaped_pass}' | sudo -S -p '' {sh_cmd} 2>/dev/null) || {sh_cmd}"
        else:
            return f"(sudo -n {sh_cmd} 2>/dev/null) || {sh_cmd}"

    def _exec_remote_cmd(self, cmd: str, timeout: int = 15) -> Tuple[bool, str, str]:
        """Menjalankan perintah arbitrary di remote host via SSH otomatis menggunakan sudo."""
        wrapped = self._wrap_remote_sudo(cmd)
        return SFTPService.exec_command(self.host, wrapped, timeout=timeout)

    def _get_git_credential_flag(self) -> str:
        """Menyusun flag credential helper untuk git push/pull bila kredensial tersedia."""
        git_user = self.host.get("git_user")
        git_pass = self.host.get("git_pass")
        if git_user and git_pass:
            esc_u = str(git_user).replace("'", "'\\''").replace('"', '\\"')
            esc_p = str(git_pass).replace("'", "'\\''").replace('"', '\\"')
            helper_str = f'!f() {{ echo "username={esc_u}"; echo "password={esc_p}"; }}; f'
            return f"-c credential.helper='{helper_str}' "
        return ""

    # -------------------------------------------------------------
    # 1. UI BUILDER (GitHub Desktop Layout)
    # -------------------------------------------------------------
    def _build_ui(self):
        # ---------------------------------------------------------
        # TOP NAVIGATION BAR (Repo, Branch, Sync Buttons, Terminal)
        # ---------------------------------------------------------
        top_bar = ctk.CTkFrame(
            self,
            fg_color=COLORS["surface"],
            height=54,
            corner_radius=0,
            border_width=1,
            border_color=COLORS["line"]
        )
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_columnconfigure(1, weight=1)

        # Left Group: Repository & Branch Pills
        left_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        left_box.grid(row=0, column=0, padx=14, pady=8, sticky="w")

        dir_name = os.path.basename(self.target_dir.rstrip("/")) or self.target_dir
        repo_pill = ctk.CTkFrame(left_box, fg_color=COLORS["input_bg"], corner_radius=6, border_width=1, border_color=COLORS["line"])
        repo_pill.pack(side="left", padx=(0, 8), pady=2)

        icon_repo = ctk.CTkLabel(repo_pill, text="", image=get_icon("folder", (15, 15), COLORS["accent"]))
        icon_repo.pack(side="left", padx=(8, 4), pady=4)

        self.lbl_repo = ctk.CTkLabel(repo_pill, text=dir_name, font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["text"])
        self.lbl_repo.pack(side="left", padx=(0, 6))

        tag_type = "Local" if self.is_local else (self.host.get("label") or self.host.get("hostname") or "Remote")
        lbl_type = ctk.CTkLabel(
            repo_pill,
            text=f" {tag_type} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLORS["accent_subtle"],
            text_color=COLORS["accent_text"],
            corner_radius=4,
            height=18
        )
        lbl_type.pack(side="left", padx=(0, 4 if not self.is_local else 8), pady=4)

        if not self.is_local:
            lbl_sudo = ctk.CTkLabel(
                repo_pill,
                text=" SUDO ",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=COLORS["danger_subtle"],
                text_color=COLORS["danger_text"],
                corner_radius=4,
                height=18
            )
            lbl_sudo.pack(side="left", padx=(0, 8), pady=4)

        # Current Branch Pill
        branch_pill = ctk.CTkFrame(left_box, fg_color=COLORS["input_bg"], corner_radius=6, border_width=1, border_color=COLORS["line"])
        branch_pill.pack(side="left", padx=(0, 8), pady=2)

        icon_branch = ctk.CTkLabel(branch_pill, text="", image=get_icon("activity", (14, 14), COLORS["text_secondary"]))
        icon_branch.pack(side="left", padx=(8, 4), pady=4)

        self.lbl_branch_name = ctk.CTkLabel(
            branch_pill,
            text="Branch: ...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text"]
        )
        self.lbl_branch_name.pack(side="left", padx=(0, 8), pady=4)

        # Right Group: Pull, Push, Terminal, Refresh
        controls_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        controls_box.grid(row=0, column=2, padx=14, pady=8, sticky="e")

        # Pull origin button
        self.btn_pull = ctk.CTkButton(
            controls_box,
            text=" Pull origin",
            image=get_icon("download", (12, 12), COLORS["text"]),
            width=95, height=30,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._do_pull
        )
        self.btn_pull.pack(side="left", padx=(0, 6))
        self.btn_pull.bind("<Button-3>", self._show_pull_menu)

        # Push origin button
        self.btn_push = ctk.CTkButton(
            controls_box,
            text=" Push origin",
            image=get_icon("upload", (12, 12), COLORS["accent_text"]),
            width=95, height=30,
            corner_radius=6,
            fg_color=COLORS["accent_subtle"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["accent_text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._do_push
        )
        self.btn_push.pack(side="left", padx=(0, 6))

        # Open Terminal
        btn_terminal = ctk.CTkButton(
            controls_box,
            text=" Terminal",
            image=get_icon("terminal", (12, 12), COLORS["text_secondary"]),
            width=85, height=30,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._open_terminal_here
        )
        btn_terminal.pack(side="left", padx=(0, 6))

        # Refresh button
        self.btn_refresh = ctk.CTkButton(
            controls_box,
            text=" Refresh",
            image=get_icon("refresh-cw", (12, 12), COLORS["text"]),
            width=80, height=30,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._refresh_all_data
        )
        self.btn_refresh.pack(side="left")

        # ---------------------------------------------------------
        # MAIN BODY (2-Column Horizontal Split)
        # ---------------------------------------------------------
        main_paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=get_color("line"),
            bd=0,
            sashwidth=4,
            sashrelief=tk.FLAT
        )
        main_paned.grid(row=1, column=0, sticky="nsew", padx=10, pady=(8, 4))

        # ---------------------------------------------------------
        # LEFT PANE: TABS (Changes vs History)
        # ---------------------------------------------------------
        left_pane = ctk.CTkFrame(main_paned, fg_color=COLORS["surface"], corner_radius=6)
        main_paned.add(left_pane, minsize=350, width=440)
        left_pane.grid_columnconfigure(0, weight=1)
        left_pane.grid_rowconfigure(1, weight=1)

        # Tab Segmented Switcher (Changes / History)
        tab_box = ctk.CTkFrame(left_pane, fg_color="transparent", height=36)
        tab_box.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        tab_box.grid_columnconfigure(0, weight=1)

        self.seg_tabs = ctk.CTkSegmentedButton(
            tab_box,
            values=["Changes", "History"],
            font=ctk.CTkFont(size=12, weight="bold"),
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["input_bg"],
            unselected_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            command=self._on_tab_changed
        )
        self.seg_tabs.grid(row=0, column=0, sticky="ew")
        self.seg_tabs.set("Changes")

        # Container for Tab Views
        self.tab_container = ctk.CTkFrame(left_pane, fg_color="transparent")
        self.tab_container.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.tab_container.grid_columnconfigure(0, weight=1)
        self.tab_container.grid_rowconfigure(0, weight=1)

        # TAB 1: CHANGES VIEW (Working Tree & Commit Box)
        self._build_changes_view()

        # TAB 2: HISTORY VIEW (Commits & Filter)
        self._build_history_view()

        # ---------------------------------------------------------
        # RIGHT PANE: DIFF VIEWER / COMMIT OVERVIEW
        # ---------------------------------------------------------
        self.right_pane = ctk.CTkFrame(main_paned, fg_color=COLORS["surface"], corner_radius=6)
        main_paned.add(self.right_pane, minsize=460, width=740)
        self.right_pane.grid_columnconfigure(0, weight=1)
        self.right_pane.grid_rowconfigure(1, weight=1)

        self._build_right_pane()

        # Inisialisasi tampilan tab default (Changes) agar langsung tampil seketika saat dialog dibuka
        self.frame_history.grid_forget()
        self.frame_changes.grid(row=0, column=0, sticky="nsew")
        if hasattr(self, "action_btn_box"):
            self.action_btn_box.grid_remove()
        self.lbl_sha_full.configure(text="")
        self.lbl_date_info.configure(text="")
        self.lbl_commit_body.configure(text="")
        self.lbl_author_info.configure(text="Local Working Tree" if self.is_local else "Remote Working Tree")
        self.lbl_commit_title.configure(text="Changes in Working Directory")
        try:
            self.diff_paned.forget(self.history_files_frame)
        except Exception:
            pass

        # ---------------------------------------------------------
        # BOTTOM STATUS BAR
        # ---------------------------------------------------------
        bottom_bar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=26, corner_radius=0, border_width=1, border_color=COLORS["line"])
        bottom_bar.grid(row=2, column=0, sticky="ew")

        self.lbl_status = ctk.CTkLabel(
            bottom_bar,
            text="Ready",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"]
        )
        self.lbl_status.pack(side="left", padx=14, pady=2)

        lbl_footer_path = ctk.CTkLabel(
            bottom_bar,
            text=self.target_dir,
            font=ctk.CTkFont(size=10),
            text_color=COLORS["subtle"]
        )
        lbl_footer_path.pack(side="right", padx=14, pady=2)

    # -------------------------------------------------------------
    # 2. LEFT PANE - TAB 1: CHANGES VIEW
    # -------------------------------------------------------------
    def _build_changes_view(self):
        self.frame_changes = ctk.CTkFrame(self.tab_container, fg_color="transparent")
        self.frame_changes.grid_columnconfigure(0, weight=1)
        self.frame_changes.grid_rowconfigure(1, weight=1)

        # Header: Select All CheckBox & Discard Action
        changes_header = ctk.CTkFrame(self.frame_changes, fg_color=COLORS["input_bg"], height=32, corner_radius=4)
        changes_header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        changes_header.grid_columnconfigure(0, weight=1)

        self.var_select_all = ctk.BooleanVar(value=True)
        self.chk_select_all = ctk.CTkCheckBox(
            changes_header,
            text="Select All (0 files)",
            variable=self.var_select_all,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text"],
            checkbox_width=16, checkbox_height=16,
            command=self._toggle_select_all_changes
        )
        self.chk_select_all.grid(row=0, column=0, sticky="w", padx=10, pady=6)

        btn_discard_all = ctk.CTkButton(
            changes_header,
            text="Discard all...",
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["danger_text"],
            width=70, height=22,
            command=self._do_discard_all
        )
        btn_discard_all.grid(row=0, column=1, sticky="e", padx=8, pady=4)

        # Scrollable List of Changed Files
        self.scroll_changes = ctk.CTkScrollableFrame(
            self.frame_changes,
            fg_color=COLORS["input_bg"],
            corner_radius=4,
            border_width=1,
            border_color=COLORS["line"]
        )
        self.scroll_changes.grid(row=1, column=0, sticky="nsew")
        self.scroll_changes.grid_columnconfigure(0, weight=1)

        # Context Menu for Changed File
        self.menu_changes = tk.Menu(self, tearoff=False, bg=get_color("surface"), fg=get_color("text"), activebackground=get_color("accent"))
        self.menu_changes.add_command(label="Discard Changes...", command=self._do_discard_selected_file)
        self.menu_changes.add_command(label="Copy Relative Path", command=self._copy_selected_file_path)

        # ---------------------------------------------------------
        # COMMIT BOX (GitHub Desktop Style)
        # ---------------------------------------------------------
        commit_box = ctk.CTkFrame(
            self.frame_changes,
            fg_color=COLORS["input_bg"],
            corner_radius=6,
            border_width=1,
            border_color=COLORS["line"]
        )
        commit_box.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        commit_box.grid_columnconfigure(0, weight=1)

        lbl_commit_box_title = ctk.CTkLabel(
            commit_box,
            text="Commit message",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        lbl_commit_box_title.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        # Summary entry (Required)
        self.entry_commit_summary = ctk.CTkEntry(
            commit_box,
            placeholder_text="Summary (required)",
            height=30,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["line"]
        )
        self.entry_commit_summary.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self.entry_commit_summary.bind("<KeyRelease>", lambda e: self._update_commit_button_state())

        # Description textbox (Optional)
        self.txt_commit_desc = ctk.CTkTextbox(
            commit_box,
            height=54,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["line"],
            wrap="word"
        )
        self.txt_commit_desc.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

        # Commit Action Button
        self.btn_commit = ctk.CTkButton(
            commit_box,
            text="Commit to main",
            height=32,
            corner_radius=6,
            fg_color="#238636",              # GitHub Green
            hover_color="#2EA043",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            state="disabled",
            command=self._do_commit
        )
        self.btn_commit.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

    # -------------------------------------------------------------
    # 3. LEFT PANE - TAB 2: HISTORY VIEW
    # -------------------------------------------------------------
    def _build_history_view(self):
        self.frame_history = ctk.CTkFrame(self.tab_container, fg_color="transparent")
        self.frame_history.grid_columnconfigure(0, weight=1)
        self.frame_history.grid_rowconfigure(1, weight=1)

        # Controls: Search, Switch All, Limit
        filter_box = ctk.CTkFrame(self.frame_history, fg_color=COLORS["input_bg"], height=36, corner_radius=4)
        filter_box.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        filter_box.grid_columnconfigure(0, weight=1)

        self.entry_filter = ctk.CTkEntry(
            filter_box,
            placeholder_text="Filter history (message, author, SHA)...",
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["line"]
        )
        self.entry_filter.grid(row=0, column=0, sticky="ew", padx=(8, 6), pady=4)
        self.entry_filter.bind("<KeyRelease>", lambda e: self._filter_displayed_commits())

        self.switch_all = ctk.CTkSwitch(
            filter_box,
            text="All",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_secondary"],
            command=self._load_git_log
        )
        self.switch_all.grid(row=0, column=1, padx=(0, 6), pady=4)
        self.switch_all.select()

        # Cherry-pick button di toolbar History
        self.btn_hist_cherry_pick = ctk.CTkButton(
            filter_box,
            text=" Cherry-pick",
            image=get_icon("git-branch", (12, 12), COLORS["accent_text"]),
            width=96, height=28,
            corner_radius=4,
            fg_color=COLORS["accent_subtle"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["accent_text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._do_cherry_pick
        )
        self.btn_hist_cherry_pick.grid(row=0, column=2, padx=(0, 4), pady=4)

        self.btn_hist_cherry_pick_hash = ctk.CTkButton(
            filter_box,
            text=" SHA...",
            image=get_icon("copy", (11, 11), COLORS["text"]),
            width=65, height=28,
            corner_radius=4,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=10),
            command=self._open_cherry_pick_by_hash_dialog
        )
        self.btn_hist_cherry_pick_hash.grid(row=0, column=3, padx=(0, 6), pady=4)

        # Treeview History
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "GitHub.History.Treeview",
            background=get_color("input_bg"),
            foreground=get_color("text"),
            fieldbackground=get_color("input_bg"),
            borderwidth=0,
            rowheight=32,
            indent=0,
            font=("Segoe UI" if os.name == "nt" else "SF Pro", 11)
        )
        style.configure(
            "GitHub.History.Treeview.Heading",
            background=get_color("surface"),
            foreground=get_color("text_secondary"),
            borderwidth=1,
            relief="flat",
            font=("Segoe UI" if os.name == "nt" else "SF Pro", 10, "bold")
        )
        style.map(
            "GitHub.History.Treeview",
            background=[("selected", get_color("accent_subtle"))],
            foreground=[("selected", get_color("accent_text"))]
        )

        tree_container = ctk.CTkFrame(self.frame_history, fg_color="transparent")
        tree_container.grid(row=1, column=0, sticky="nsew")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        columns = ("commit", "author_date", "hash")
        self.tree_history = ttk.Treeview(
            tree_container,
            columns=columns,
            show="tree headings",
            style="GitHub.History.Treeview",
            selectmode="browse"
        )
        self.tree_history.grid(row=0, column=0, sticky="nsew")

        self.tree_history.heading("#0", text="Graph", anchor="w")
        self.tree_history.heading("commit", text="Commit Message", anchor="w")
        self.tree_history.heading("author_date", text="Author & Date", anchor="w")
        self.tree_history.heading("hash", text="SHA", anchor="w")

        self.tree_history.column("#0", width=65, minwidth=50, stretch=False)
        self.tree_history.column("commit", width=220, minwidth=140, stretch=True)
        self.tree_history.column("author_date", width=120, minwidth=90, stretch=False)
        self.tree_history.column("hash", width=65, minwidth=55, stretch=False)

        hist_scroll = ctk.CTkScrollbar(tree_container, orientation="vertical", command=self.tree_history.yview)
        hist_scroll.grid(row=0, column=1, sticky="ns")
        self.tree_history.configure(yscrollcommand=hist_scroll.set)

        self._build_history_context_menu()
        self.tree_history.bind("<<TreeviewSelect>>", self._on_history_commit_selected)
        self.tree_history.bind("<Double-Button-1>", lambda e: self._copy_selected_hash())
        self.tree_history.bind("<Button-2>", self._show_history_context_menu)
        self.tree_history.bind("<Button-3>", self._show_history_context_menu)

    # -------------------------------------------------------------
    # 4. RIGHT PANE: COMMIT CARD & DIFF VIEWER
    # -------------------------------------------------------------
    def _build_right_pane(self):
        # 1. Commit Overview Card (Terlihat saat di tab History)
        self.card_overview = ctk.CTkFrame(
            self.right_pane,
            fg_color=COLORS["input_bg"],
            corner_radius=6,
            border_width=1,
            border_color=COLORS["line"]
        )
        self.card_overview.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 8))
        self.card_overview.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(self.card_overview, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        title_row.grid_columnconfigure(0, weight=1)

        self.lbl_commit_title = ctk.CTkLabel(
            title_row,
            text="Working Directory Changes",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
            wraplength=520,
            justify="left"
        )
        self.lbl_commit_title.grid(row=0, column=0, sticky="w")

        self.action_btn_box = ctk.CTkFrame(title_row, fg_color="transparent")
        self.action_btn_box.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.btn_cherry_pick = ctk.CTkButton(
            self.action_btn_box,
            text=" Cherry-pick",
            image=get_icon("git-branch", (12, 12), COLORS["accent_text"]),
            width=95, height=26,
            corner_radius=4,
            fg_color=COLORS["accent_subtle"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["accent_text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._do_cherry_pick
        )
        self.btn_cherry_pick.pack(side="left", padx=(0, 4))

        self.btn_card_cherry_pick_hash = ctk.CTkButton(
            self.action_btn_box,
            text="Cherry-pick SHA...",
            image=get_icon("git-branch", (11, 11), COLORS["text"]),
            width=120, height=26,
            corner_radius=4,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=10),
            command=self._open_cherry_pick_by_hash_dialog
        )
        self.btn_card_cherry_pick_hash.pack(side="left", padx=(0, 4))

        self.btn_copy_sha = ctk.CTkButton(
            self.action_btn_box,
            text="Copy SHA",
            image=get_icon("copy", (11, 11), COLORS["text_secondary"]),
            width=85, height=26,
            corner_radius=4,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=10),
            command=self._copy_selected_hash
        )
        self.btn_copy_sha.pack(side="left")

        self.lbl_commit_body = ctk.CTkLabel(
            self.card_overview,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"],
            anchor="w",
            justify="left",
            wraplength=600
        )
        self.lbl_commit_body.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

        meta_row = ctk.CTkFrame(self.card_overview, fg_color="transparent")
        meta_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 6))

        self.lbl_author_info = ctk.CTkLabel(
            meta_row,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        )
        self.lbl_author_info.pack(side="left", padx=(0, 14))

        self.lbl_date_info = ctk.CTkLabel(
            meta_row,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"]
        )
        self.lbl_date_info.pack(side="left", padx=(0, 14))

        self.lbl_sha_full = ctk.CTkLabel(
            meta_row,
            text="",
            font=ctk.CTkFont(family="Menlo" if os.name != "nt" else "Consolas", size=10),
            text_color=COLORS["muted"]
        )
        self.lbl_sha_full.pack(side="left")

        summary_bar = ctk.CTkFrame(self.card_overview, fg_color=COLORS["surface"], height=28, corner_radius=4)
        summary_bar.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))

        self.lbl_summary_stats = ctk.CTkLabel(
            summary_bar,
            text="0 files changed",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text"]
        )
        self.lbl_summary_stats.pack(side="left", padx=10, pady=2)

        self.lbl_additions_badge = ctk.CTkLabel(
            summary_bar,
            text="+0",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#12261E",
            text_color="#3FB950",
            corner_radius=4,
            height=18
        )
        self.lbl_additions_badge.pack(side="left", padx=(0, 6))

        self.lbl_deletions_badge = ctk.CTkLabel(
            summary_bar,
            text="-0",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#2E1518",
            text_color="#F85149",
            corner_radius=4,
            height=18
        )
        self.lbl_deletions_badge.pack(side="left")

        # 2. Sub-Split: Files Changed (History only) + Diff Viewer
        self.diff_paned = tk.PanedWindow(
            self.right_pane,
            orient=tk.HORIZONTAL,
            bg=get_color("line"),
            bd=0,
            sashwidth=4,
            sashrelief=tk.FLAT
        )
        self.diff_paned.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))

        # Files Frame (Khusus History)
        self.history_files_frame = ctk.CTkFrame(self.diff_paned, fg_color=COLORS["input_bg"], corner_radius=6)
        self.diff_paned.add(self.history_files_frame, minsize=180, width=220)
        self.history_files_frame.grid_columnconfigure(0, weight=1)
        self.history_files_frame.grid_rowconfigure(1, weight=1)

        files_top = ctk.CTkFrame(self.history_files_frame, fg_color="transparent", height=28)
        files_top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        files_top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            files_top,
            text="Changed Files",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"]
        ).grid(row=0, column=0, sticky="w")

        files_tree_box = ctk.CTkFrame(self.history_files_frame, fg_color="transparent")
        files_tree_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
        files_tree_box.grid_columnconfigure(0, weight=1)
        files_tree_box.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.configure(
            "GitHub.Files.Treeview",
            background=get_color("input_bg"),
            foreground=get_color("text"),
            fieldbackground=get_color("input_bg"),
            borderwidth=0,
            rowheight=26,
            font=("Segoe UI" if os.name == "nt" else "SF Pro", 10)
        )
        style.map(
            "GitHub.Files.Treeview",
            background=[("selected", get_color("accent_subtle"))],
            foreground=[("selected", get_color("accent_text"))]
        )

        self.tree_files = ttk.Treeview(
            files_tree_box,
            columns=("type", "file", "stat"),
            show="headings",
            style="GitHub.Files.Treeview",
            selectmode="browse"
        )
        self.tree_files.grid(row=0, column=0, sticky="nsew")

        self.tree_files.heading("type", text="Type", anchor="center")
        self.tree_files.heading("file", text="File Path", anchor="w")
        self.tree_files.heading("stat", text="+ / -", anchor="e")

        self.tree_files.column("type", width=42, minwidth=35, stretch=False, anchor="center")
        self.tree_files.column("file", width=120, minwidth=90, stretch=True)
        self.tree_files.column("stat", width=55, minwidth=45, stretch=False, anchor="e")

        files_scroll = ctk.CTkScrollbar(files_tree_box, orientation="vertical", command=self.tree_files.yview)
        files_scroll.grid(row=0, column=1, sticky="ns")
        self.tree_files.configure(yscrollcommand=files_scroll.set)
        self.tree_files.bind("<<TreeviewSelect>>", self._on_history_file_selected)

        # Diff View Frame
        self.diff_view_frame = ctk.CTkFrame(self.diff_paned, fg_color=COLORS["input_bg"], corner_radius=6)
        self.diff_paned.add(self.diff_view_frame, minsize=280, width=540)
        self.diff_view_frame.grid_columnconfigure(0, weight=1)
        self.diff_view_frame.grid_rowconfigure(1, weight=1)

        diff_top = ctk.CTkFrame(self.diff_view_frame, fg_color=COLORS["surface"], height=30, corner_radius=0)
        diff_top.grid(row=0, column=0, sticky="ew")

        self.lbl_diff_title = ctk.CTkLabel(
            diff_top,
            text="Diff Viewer",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text"]
        )
        self.lbl_diff_title.pack(side="left", padx=12, pady=4)

        self.txt_diff = ctk.CTkTextbox(
            self.diff_view_frame,
            font=ctk.CTkFont(family="Menlo" if os.name != "nt" else "Consolas", size=11),
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            corner_radius=0,
            border_width=0,
            wrap="none"
        )
        self.txt_diff.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

    # -------------------------------------------------------------
    # 5. TAB SWITCHING (Changes vs History)
    # -------------------------------------------------------------
    def _on_tab_changed(self, selected_tab: str):
        prev_tab = self._active_tab
        self._active_tab = selected_tab
        if selected_tab == "Changes":
            self.frame_history.grid_forget()
            self.frame_changes.grid(row=0, column=0, sticky="nsew")

            # Atur Right Pane untuk Changes
            if hasattr(self, "action_btn_box"):
                self.action_btn_box.grid_remove()
            self.lbl_sha_full.configure(text="")
            self.lbl_date_info.configure(text="")
            self.lbl_commit_body.configure(text="")
            self.lbl_author_info.configure(text="Local Working Tree" if self.is_local else "Remote Working Tree")
            self.lbl_commit_title.configure(text=f"Changes in Working Directory ({len(self._working_changes)} files)")

            # Sembunyikan files frame history di diff_paned
            try:
                self.diff_paned.forget(self.history_files_frame)
            except Exception:
                pass

            if prev_tab != "Changes":
                self._load_working_changes()
        else:
            self.frame_changes.grid_forget()
            self.frame_history.grid(row=0, column=0, sticky="nsew")

            if hasattr(self, "action_btn_box"):
                self.action_btn_box.grid()
            # Tampilkan kembali files frame history di diff_paned
            try:
                self.diff_paned.add(self.history_files_frame, minsize=180, width=220, before=self.diff_view_frame)
            except Exception:
                pass

            self._load_git_log()

    def _refresh_all_data(self):
        """Memperbarui branch, working changes, dan git history dalam 1 operasi cepat non-blocking."""
        if self._is_loading:
            return
        self._is_loading = True
        self.btn_refresh.configure(state="disabled")
        self.lbl_status.configure(text="Memuat status repositori Git...", text_color=COLORS["muted"])

        def worker():
            branch = "main"
            repo_root = getattr(self, "repo_root", self.target_dir) or self.target_dir
            status_raw = ""
            files_data = []

            try:
                if self.is_local:
                    # 1. Lokal: Gunakan git -C langsung tanpa cd command (aman di Windows)
                    try:
                        res_top = subprocess.run(
                            ["git", "-C", self.target_dir, "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True
                        )
                        if res_top.returncode == 0 and res_top.stdout.strip():
                            repo_root = res_top.stdout.strip()
                    except Exception:
                        pass

                    try:
                        res_br = subprocess.run(
                            ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True
                        )
                        if res_br.returncode == 0 and res_br.stdout.strip():
                            branch = res_br.stdout.strip()
                    except Exception:
                        pass

                    try:
                        res_st = subprocess.run(
                            ["git", "-C", repo_root, "-c", "core.quotepath=false", "status", "--porcelain=v1"],
                            capture_output=True, text=True
                        )
                        if res_st.returncode == 0:
                            status_raw = res_st.stdout
                    except Exception as e:
                        status_raw = str(e)
                else:
                    # 2. Remote: Jalankan dalam SATU round-trip SSH untuk kecepatan maksimal (<1 detik)
                    esc_target = self.target_dir.replace("'", "'\\''")
                    combined_cmd = (
                        f"TARGET='{esc_target}'; "
                        f"cd \"$TARGET\" 2>/dev/null || cd /; "
                        f"TOP=$(git -c safe.directory='*' rev-parse --show-toplevel 2>/dev/null || pwd); "
                        f"BR=$(git -C \"$TOP\" -c safe.directory='*' rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'main'); "
                        f"echo '===PULLMAN_META==='; "
                        f"echo \"$TOP\"; "
                        f"echo \"$BR\"; "
                        f"echo '===PULLMAN_STATUS==='; "
                        f"git -C \"$TOP\" -c safe.directory='*' -c core.quotepath=false status --porcelain=v1 2>/dev/null"
                    )
                    ok, out, err = self._exec_remote_cmd(combined_cmd)
                    if "===PULLMAN_META===" in out and "===PULLMAN_STATUS===" in out:
                        try:
                            meta_part, status_part = out.split("===PULLMAN_STATUS===", 1)
                            meta_lines = [l.strip() for l in meta_part.splitlines() if l.strip()]
                            m_idx = meta_lines.index("===PULLMAN_META===")
                            if len(meta_lines) > m_idx + 1 and meta_lines[m_idx + 1]:
                                repo_root = meta_lines[m_idx + 1]
                            if len(meta_lines) > m_idx + 2 and meta_lines[m_idx + 2]:
                                branch = meta_lines[m_idx + 2]
                            status_raw = status_part
                        except Exception:
                            status_raw = out
                    else:
                        status_raw = out or err

                # Parse baris status porcelain
                if status_raw:
                    for line in status_raw.splitlines():
                        if len(line) < 3:
                            continue
                        st = line[:2]
                        raw_path = line[3:].strip()
                        if raw_path.startswith('"') and raw_path.endswith('"'):
                            raw_path = raw_path[1:-1]

                        orig_path = None
                        if " -> " in raw_path:
                            parts = raw_path.split(" -> ", 1)
                            orig_path = parts[0].strip().strip('"')
                            path_str = parts[1].strip().strip('"')
                        else:
                            path_str = raw_path

                        ctype = "M"
                        if "?" in st:
                            ctype = "A"
                        elif "D" in st:
                            ctype = "D"
                        elif "R" in st:
                            ctype = "R"
                        elif "A" in st:
                            ctype = "A"

                        files_data.append({
                            "path": path_str,
                            "orig_path": orig_path,
                            "status": st,
                            "type": ctype,
                        })
            except Exception as e:
                status_raw = f"Error: {e}"
            finally:
                def on_done():
                    if not self.winfo_exists():
                        return
                    self._is_loading = False
                    self.btn_refresh.configure(state="normal")
                    self.repo_root = repo_root
                    self._current_branch = branch
                    self.lbl_branch_name.configure(text=f"Branch: {branch}")
                    self.btn_commit.configure(text=f"Commit to {branch}")
                    dir_name = os.path.basename(repo_root.rstrip("/")) or repo_root
                    if hasattr(self, "lbl_repo") and self.lbl_repo:
                        self.lbl_repo.configure(text=dir_name)

                    if self._active_tab == "Changes":
                        self._populate_working_changes_ui(files_data)
                    else:
                        self._load_git_log()

                try:
                    self.after(0, on_done)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _detect_branch(self, on_ready=None):
        self._refresh_all_data()

    def _load_working_changes(self):
        self._refresh_all_data()

    def _populate_working_changes_ui(self, files_data: List[Dict[str, Any]]):
        self._working_changes.clear()
        for w in self.scroll_changes.winfo_children():
            w.destroy()

        count = len(files_data)
        self.seg_tabs.set(f"Changes")
        self.chk_select_all.configure(text=f"Select All ({count} changed files)")
        self.lbl_summary_stats.configure(text=f"{count} files changed")
        self.lbl_commit_title.configure(text=f"Changes in Working Directory ({count} files)")

        if count == 0:
            lbl_empty = ctk.CTkLabel(
                self.scroll_changes,
                text="No local changes in working directory.\nYour working tree is clean! ✓",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["success_text"],
                justify="center"
            )
            lbl_empty.pack(pady=40)
            self._render_diff_text("Working Tree Clean", "No changes detected in working directory.")
            self.lbl_status.configure(text="Working tree bersih — tidak ada file yang berubah ✓", text_color=COLORS["success_text"])
            self._update_commit_button_state()
            return

        for f in files_data:
            var_chk = ctk.BooleanVar(value=True)
            row_frame = ctk.CTkFrame(self.scroll_changes, fg_color="transparent", height=30)
            row_frame.pack(fill="x", padx=4, pady=2)
            row_frame.grid_columnconfigure(3, weight=1)

            # Checkbox
            chk = ctk.CTkCheckBox(
                row_frame,
                text="",
                variable=var_chk,
                width=16, height=16,
                checkbox_width=16, checkbox_height=16,
                command=self._update_commit_button_state
            )
            chk.grid(row=0, column=0, padx=(4, 6), pady=4)

            # Status Badge Pill
            type_color = "#3FB950" if f["type"] == "A" else ("#F85149" if f["type"] == "D" else "#58A6FF")
            lbl_badge = ctk.CTkLabel(
                row_frame,
                text=f" {f['type']} ",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=COLORS["surface"],
                text_color=type_color,
                corner_radius=4,
                height=18
            )
            lbl_badge.grid(row=0, column=1, padx=(0, 4), pady=4)

            # File Type Icon
            f_icon = get_file_type_icon(f["path"], size=(14, 14))
            lbl_f_icon = ctk.CTkLabel(row_frame, text="", image=f_icon, width=16)
            lbl_f_icon.grid(row=0, column=2, padx=(0, 6), pady=4)

            # File Path Label
            fname = os.path.basename(f["path"])
            fdir = os.path.dirname(f["path"])
            display_text = fname + (f"  ({fdir})" if fdir else "")
            lbl_name = ctk.CTkLabel(
                row_frame,
                text=display_text,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text"],
                anchor="w",
                cursor="hand2"
            )
            lbl_name.grid(row=0, column=3, sticky="w", pady=4)

            item_data = {
                "path": f["path"],
                "status": f["status"],
                "type": f["type"],
                "checked_var": var_chk,
                "frame": row_frame
            }
            self._working_changes.append(item_data)

            # Click & Right-click events
            for widget in (row_frame, lbl_name, lbl_badge, lbl_f_icon):
                widget.bind("<Button-1>", lambda e, item=item_data: self._on_working_file_clicked(item))
                widget.bind("<Button-2>", lambda e, item=item_data: self._show_changes_context_menu(e, item))
                widget.bind("<Button-3>", lambda e, item=item_data: self._show_changes_context_menu(e, item))

        # Pilih file pertama
        if self._working_changes:
            self._on_working_file_clicked(self._working_changes[0])

        self._update_commit_button_state()
        self.lbl_status.configure(text=f"Ditemukan {count} file yang berubah di working directory", text_color=COLORS["text"])

    def _on_working_file_clicked(self, item_data: Dict[str, Any]):
        self._selected_working_file = item_data
        for it in self._working_changes:
            it["frame"].configure(fg_color="transparent")
        item_data["frame"].configure(fg_color=COLORS["surface_hover"])

        self._load_working_file_diff(item_data["path"], item_data["type"])

    def _show_changes_context_menu(self, event, item_data: Dict[str, Any]):
        self._selected_working_file = item_data
        try:
            self.menu_changes.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_changes.grab_release()

    def _load_working_file_diff(self, filepath: str, ftype: str):
        self.lbl_diff_title.configure(text=f"Diff: {filepath}")
        self.txt_diff.delete("1.0", "end")
        self.txt_diff.insert("1.0", f"Memuat diff untuk {filepath}...\n")

        def worker():
            diff_text = ""
            root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir
            clean_p = filepath.strip().lstrip("/").replace("'", "'\\''")

            try:
                if self.is_local:
                    if HAS_GITPYTHON:
                        try:
                            repo = Repo(root_dir, search_parent_directories=True)
                            if ftype == "A":
                                full_p = os.path.join(root_dir, filepath)
                                diff_text = self._generate_untracked_diff(filepath, full_p)
                            else:
                                try:
                                    diff_text = repo.git.diff("HEAD", "--", filepath)
                                except Exception:
                                    diff_text = repo.git.diff("--", filepath)
                        except Exception as e:
                            diff_text = str(e)
                    else:
                        if ftype == "A":
                            full_p = os.path.join(root_dir, filepath)
                            diff_text = self._generate_untracked_diff(filepath, full_p)
                        else:
                            res = subprocess.run(
                                ["git", "-C", root_dir, "diff", "HEAD", "--", f":/{clean_p}"],
                                capture_output=True, text=True
                            )
                            diff_text = res.stdout or res.stderr
                            if not diff_text or "fatal" in diff_text or "error" in diff_text:
                                res_fb = subprocess.run(
                                    ["git", "-C", root_dir, "diff", "--", f":/{clean_p}"],
                                    capture_output=True, text=True
                                )
                                diff_text = res_fb.stdout or res_fb.stderr
                else:
                    if ftype == "A":
                        cmd = f"head -n 300 '{root_dir}/{clean_p}' 2>/dev/null || cat '{root_dir}/{clean_p}' 2>/dev/null"
                        ok, out, _ = self._exec_remote_cmd(cmd)
                        lines = out.splitlines() if ok else []
                        diff_text = f"diff --git a/{filepath} b/{filepath}\nnew file mode 100644\n--- /dev/null\n+++ b/{filepath}\n@@ -0,0 +1,{len(lines)} @@\n" + "\n".join("+" + l for l in lines)
                    else:
                        cmd = f"git -C '{root_dir}' -c safe.directory='*' diff HEAD -- ':/{clean_p}'"
                        ok, out, err = self._exec_remote_cmd(cmd)
                        if not out and not ok:
                            cmd_fb = f"git -C '{root_dir}' -c safe.directory='*' diff -- ':/{clean_p}'"
                            ok, out, err = self._exec_remote_cmd(cmd_fb)
                        diff_text = out or err

                # Batasi diff jika terlalu besar agar Tkinter tidak freeze
                if diff_text and len(diff_text) > 80000:
                    diff_text = diff_text[:80000] + "\n\n... [Diff dipersingkat: file terlalu besar untuk dipratinjau lengkap]"
            except Exception as e:
                diff_text = f"Error loading diff: {e}"
            finally:
                def on_done():
                    if not self.winfo_exists():
                        return
                    self._render_diff_text(filepath, diff_text or "No diff lines (file binary or empty).")

                try:
                    self.after(0, on_done)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _generate_untracked_diff(self, filepath: str, abs_path: str) -> str:
        try:
            if not os.path.isfile(abs_path):
                return f"diff --git a/{filepath} b/{filepath}\n(File not found locally)"
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fp:
                lines = fp.read().splitlines()
            header = f"diff --git a/{filepath} b/{filepath}\nnew file mode 100644\n--- /dev/null\n+++ b/{filepath}\n@@ -0,0 +1,{len(lines)} @@\n"
            return header + "\n".join("+" + l for l in lines)
        except Exception as e:
            return f"Error reading file {filepath}: {e}"

    def _toggle_select_all_changes(self):
        val = self.var_select_all.get()
        for f in self._working_changes:
            f["checked_var"].set(val)
        self._update_commit_button_state()

    def _update_commit_button_state(self):
        checked_count = sum(1 for f in self._working_changes if f["checked_var"].get())
        has_summary = bool(self.entry_commit_summary.get().strip())

        branch_text = f"Commit to {self._current_branch}"
        if checked_count > 0:
            branch_text = f"Commit {checked_count} file(s) to {self._current_branch}"

        self.btn_commit.configure(text=branch_text)
        if has_summary and checked_count > 0:
            self.btn_commit.configure(state="normal", fg_color="#238636")
        else:
            self.btn_commit.configure(state="disabled", fg_color=COLORS["surface"])

    def _do_commit(self):
        summary = self.entry_commit_summary.get().strip()
        if not summary:
            messagebox.showwarning("Peringatan", "Harap isi ringkasan commit (Summary) terlebih dahulu.", parent=self)
            return

        selected_items = [f for f in self._working_changes if f["checked_var"].get()]
        if not selected_items:
            messagebox.showwarning("Peringatan", "Pilih minimal satu file yang ingin di-commit.", parent=self)
            return

        desc = self.txt_commit_desc.get("1.0", "end-1c").strip()
        full_msg = summary if not desc else f"{summary}\n\n{desc}"

        self.btn_commit.configure(state="disabled", text="Committing...")
        self.lbl_status.configure(text=f"Melakukan commit {len(selected_items)} file...", text_color=COLORS["accent"])

        def worker():
            ok = False
            msg_res = ""
            root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir

            # Re-verify true toplevel repo root
            if not self.is_local:
                ok_top, out_top, _ = self._exec_remote_cmd(f"cd '{self.target_dir}' && git rev-parse --show-toplevel")
                if ok_top and out_top.strip():
                    root_dir = out_top.strip()
                    self.repo_root = root_dir
            else:
                try:
                    res = subprocess.run(f"cd '{self.target_dir}' && git rev-parse --show-toplevel", shell=True, capture_output=True, text=True)
                    if res.returncode == 0 and res.stdout.strip():
                        root_dir = res.stdout.strip()
                        self.repo_root = root_dir
                except Exception:
                    pass

            author_name = self.host.get("git_user") or self.host.get("username") or "PullManager"
            author_email = self.host.get("git_email") or f"{author_name}@pullmanager.local"
            ident_flag = f"-c user.name='{author_name}' -c user.email='{author_email}' "

            if self.is_local:
                res_u = subprocess.run("git config user.name", shell=True, capture_output=True, text=True)
                if res_u.returncode == 0 and res_u.stdout.strip():
                    ident_flag = ""

            all_checked = (len(selected_items) == len(self._working_changes))

            if self.is_local:
                if HAS_GITPYTHON:
                    try:
                        repo = Repo(root_dir, search_parent_directories=True)
                        if all_checked:
                            repo.git.add("-A")
                        else:
                            for item in selected_items:
                                p = item["path"]
                                repo.git.add("-A", "--", p)
                                if item.get("orig_path"):
                                    repo.git.add("-A", "--", item["orig_path"])
                        commit_res = repo.git.commit("-m", full_msg)
                        ok = True
                        msg_res = commit_res
                    except Exception as e:
                        msg_res = str(e)
                else:
                    try:
                        if all_checked:
                            subprocess.run(["git", "-C", root_dir, "add", "-A"], capture_output=True, check=True)
                        else:
                            paths_to_stage = []
                            for item in selected_items:
                                paths_to_stage.append(item["path"].strip().lstrip("/"))
                                if item.get("orig_path"):
                                    paths_to_stage.append(item["orig_path"].strip().lstrip("/"))
                            subprocess.run(["git", "-C", root_dir, "add", "-A", "--"] + paths_to_stage, capture_output=True, check=True)

                        commit_args = ["git", "-C", root_dir]
                        if ident_flag:
                            commit_args.extend(["-c", f"user.name={author_name}", "-c", f"user.email={author_email}"])
                        commit_args.extend(["commit", "-m", full_msg])
                        res = subprocess.run(commit_args, capture_output=True, text=True)
                        ok = (res.returncode == 0)
                        msg_res = res.stdout or res.stderr
                    except Exception as e:
                        msg_res = str(e)
            else:
                if all_checked:
                    add_cmd = f"git -C '{root_dir}' -c safe.directory='*' add -A"
                else:
                    paths_to_stage = []
                    for item in selected_items:
                        p = item["path"].strip().lstrip("/").replace("'", "'\\''")
                        paths_to_stage.append(f"':/{p}'")
                        if item.get("orig_path"):
                            orig = item["orig_path"].strip().lstrip("/").replace("'", "'\\''")
                            paths_to_stage.append(f"':/{orig}'")
                    add_cmd = f"git -C '{root_dir}' -c safe.directory='*' add -A -- {' '.join(paths_to_stage)}"

                esc_msg = full_msg.replace("'", "'\\''")
                cmd = f"{add_cmd} && git -C '{root_dir}' -c safe.directory='*' {ident_flag}commit -m '{esc_msg}'"
                ok, out, err = self._exec_remote_cmd(cmd)
                msg_res = out or err

            def on_done():
                if not self.winfo_exists():
                    return
                if ok:
                    self.entry_commit_summary.delete(0, "end")
                    self.txt_commit_desc.delete("1.0", "end")
                    self.lbl_status.configure(
                        text=f"Commit berhasil dibuat ke branch {self._current_branch} ✓",
                        text_color=COLORS["success_text"]
                    )
                    self._refresh_all_data()
                else:
                    self.btn_commit.configure(state="normal", text=f"Commit to {self._current_branch}")
                    self.lbl_status.configure(text="Gagal melakukan commit!", text_color=COLORS["danger"])
                    messagebox.showerror("Commit Error", f"Gagal melakukan commit:\n{msg_res}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _do_discard_selected_file(self):
        if not self._selected_working_file:
            return
        f = self._selected_working_file
        confirm = messagebox.askyesno(
            "Konfirmasi Discard Changes",
            f"Apakah Anda yakin ingin membatalkan semua perubahan pada file:\n'{f['path']}'?\n\nPerubahan yang belum di-commit akan hilang!",
            parent=self
        )
        if not confirm:
            return

        self._execute_discard([f])

    def _do_discard_all(self):
        if not self._working_changes:
            return
        confirm = messagebox.askyesno(
            "Konfirmasi Discard All Changes",
            f"Apakah Anda yakin ingin membatalkan semua perubahan pada {len(self._working_changes)} file?\n\nTindakan ini tidak dapat dibatalkan!",
            parent=self
        )
        if not confirm:
            return

        self._execute_discard(self._working_changes)

    def _execute_discard(self, files_to_discard: List[Dict[str, Any]]):
        self.lbl_status.configure(text="Membatalkan perubahan file...", text_color=COLORS["danger"])

        def worker():
            root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir
            for f in files_to_discard:
                path = f["path"].strip().lstrip("/")
                st = f.get("status", "")
                esc_p = path.replace("'", "'\\''")
                is_untracked = ("?" in st)

                if self.is_local:
                    if is_untracked:
                        full_p = os.path.join(root_dir, path)
                        if os.path.exists(full_p):
                            try:
                                if os.path.isdir(full_p):
                                    import shutil
                                    shutil.rmtree(full_p, ignore_errors=True)
                                else:
                                    os.remove(full_p)
                            except Exception:
                                pass
                    else:
                        subprocess.run(["git", "-C", root_dir, "checkout", "HEAD", "--", f":/{path}"], capture_output=True)
                        subprocess.run(["git", "-C", root_dir, "checkout", "--", f":/{path}"], capture_output=True)
                else:
                    if is_untracked:
                        self._exec_remote_cmd(f"rm -rf '{root_dir}/{esc_p}'")
                    else:
                        self._exec_remote_cmd(
                            f"git -C '{root_dir}' -c safe.directory='*' rm -f --cached ':/{esc_p}' 2>/dev/null; "
                            f"(git -C '{root_dir}' -c safe.directory='*' checkout HEAD -- ':/{esc_p}' 2>/dev/null || "
                            f"git -C '{root_dir}' -c safe.directory='*' checkout -- ':/{esc_p}' 2>/dev/null)"
                        )

            def on_done():
                if not self.winfo_exists():
                    return
                self.lbl_status.configure(text=f"Perubahan pada {len(files_to_discard)} file berhasil dibatalkan ✓", text_color=COLORS["success_text"])
                self._load_working_changes()

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _copy_selected_file_path(self):
        if not self._selected_working_file:
            return
        p = self._selected_working_file["path"]
        self.clipboard_clear()
        self.clipboard_append(p)
        self.lbl_status.configure(text=f"Copied path: {p} ✓", text_color=COLORS["success_text"])

    # -------------------------------------------------------------
    # 7. SYNC ACTIONS (Push & Pull)
    # -------------------------------------------------------------
    def _do_push(self):
        self.btn_push.configure(state="disabled", text="Pushing...")
        self.lbl_status.configure(text=f"Mendorong commit ke remote origin/{self._current_branch}...", text_color=COLORS["accent"])

        def worker():
            ok = False
            out_res = ""
            root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir
            cred_flag = self._get_git_credential_flag()

            if self.is_local:
                if HAS_GITPYTHON:
                    try:
                        repo = Repo(root_dir, search_parent_directories=True)
                        push_info = repo.git.push("origin", self._current_branch)
                        ok = True
                        out_res = push_info or "Push completed."
                    except Exception as e:
                        out_res = str(e)
                else:
                    res = subprocess.run(f"git {cred_flag}push origin {self._current_branch}", cwd=root_dir, shell=True, capture_output=True, text=True)
                    ok = (res.returncode == 0)
                    out_res = res.stdout or res.stderr
            else:
                ok, out, err = self._exec_remote_cmd(f"git -C '{root_dir}' {cred_flag}push origin {self._current_branch}")
                out_res = out or err

            def on_done():
                if not self.winfo_exists():
                    return
                self.btn_push.configure(state="normal", text=" Push origin")
                if ok:
                    self.lbl_status.configure(text=f"Berhasil push ke origin/{self._current_branch} ✓", text_color=COLORS["success_text"])
                    self._refresh_all_data()
                    messagebox.showinfo("Push Success", f"Commit berhasil di-push ke remote origin/{self._current_branch}!", parent=self)
                else:
                    self.btn_push.configure(state="normal", text=" Push origin")
                    self.lbl_status.configure(text="Gagal push ke remote origin!", text_color=COLORS["danger"])
                    messagebox.showerror("Push Error", f"Gagal push ke origin:\n{out_res}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _do_pull(self, fetch_all: bool = True):
        self.btn_pull.configure(state="disabled", text="Pulling...")
        self.lbl_status.configure(text=f"Menarik perubahan & fetch branch dari origin...", text_color=COLORS["accent"])

        def worker():
            ok = False
            out_res = ""
            root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir
            cred_flag = self._get_git_credential_flag()

            if self.is_local:
                if HAS_GITPYTHON:
                    try:
                        repo = Repo(root_dir, search_parent_directories=True)
                        if fetch_all:
                            try:
                                repo.git.fetch("--all", "--prune")
                            except Exception:
                                pass
                        pull_info = repo.git.pull("origin", self._current_branch)
                        ok = True
                        out_res = pull_info or "Pull completed."
                    except Exception as e:
                        out_res = str(e)
                else:
                    if fetch_all:
                        subprocess.run(f"git {cred_flag}fetch --all --prune", cwd=root_dir, shell=True, capture_output=True)
                    res = subprocess.run(f"git {cred_flag}pull origin {self._current_branch}", cwd=root_dir, shell=True, capture_output=True, text=True)
                    ok = (res.returncode == 0)
                    out_res = res.stdout or res.stderr
            else:
                if fetch_all:
                    cmd = f"git -C '{root_dir}' {cred_flag}fetch --all --prune 2>/dev/null; git -C '{root_dir}' {cred_flag}pull origin {self._current_branch}"
                else:
                    cmd = f"git -C '{root_dir}' {cred_flag}pull origin {self._current_branch}"
                ok, out, err = self._exec_remote_cmd(cmd, timeout=30)
                out_res = out or err

            def on_done():
                if not self.winfo_exists():
                    return
                self.btn_pull.configure(state="normal", text=" Pull origin")
                if ok:
                    self.lbl_status.configure(text=f"Berhasil pull & fetch all dari origin ✓", text_color=COLORS["success_text"])
                    self._refresh_all_data()
                    messagebox.showinfo("Pull Success", f"Berhasil menarik perubahan dan fetch semua branch dari origin:\n{out_res}", parent=self)
                else:
                    self.btn_pull.configure(state="normal", text=" Pull origin")
                    self.lbl_status.configure(text="Gagal pull dari remote origin!", text_color=COLORS["danger"])
                    messagebox.showerror("Pull Error", f"Gagal pull dari origin:\n{out_res}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _show_pull_menu(self, event=None):
        menu = tk.Menu(self, tearoff=False, bg=get_color("surface"), fg=get_color("text"), activebackground=get_color("accent"))
        menu.add_command(label=f"Pull origin/{self._current_branch} & Fetch All (Default)", command=lambda: self._do_pull(fetch_all=True))
        menu.add_command(label=f"Pull origin/{self._current_branch} saja", command=lambda: self._do_pull(fetch_all=False))
        menu.add_command(label="Fetch All from Origin (Semua Branch)", command=self._do_fetch_all_only)
        try:
            x = event.x_root if event else self.btn_pull.winfo_rootx()
            y = event.y_root if event else (self.btn_pull.winfo_rooty() + self.btn_pull.winfo_height())
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _do_fetch_all_only(self):
        self.lbl_status.configure(text="Menjalankan git fetch --all --prune...", text_color=COLORS["accent"])
        root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir
        cred_flag = self._get_git_credential_flag()

        def worker():
            if self.is_local:
                subprocess.run(f"git {cred_flag}fetch --all --prune", cwd=root_dir, shell=True, capture_output=True)
            else:
                self._exec_remote_cmd(f"git -C '{root_dir}' {cred_flag}fetch --all --prune", timeout=25)

            def on_done():
                if not self.winfo_exists():
                    return
                self.lbl_status.configure(text="Fetch all branch berhasil ✓", text_color=COLORS["success_text"])
                self._refresh_all_data()

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------------------------------------
    # 8. HISTORY VIEW LOGIC (Commits, Log & Diff)
    # -------------------------------------------------------------
    def _load_git_log(self):
        if self._is_loading:
            return
        self._is_loading = True
        self.lbl_status.configure(text="Memuat commit history dari repository...", text_color=COLORS["muted"])
        self.btn_refresh.configure(state="disabled")
        if hasattr(self, "btn_cherry_pick"):
            self.btn_cherry_pick.configure(state="disabled")
        if hasattr(self, "btn_hist_cherry_pick"):
            self.btn_hist_cherry_pick.configure(state="disabled")

        use_all = self.switch_all.get() == 1

        def worker():
            current_branch = self._current_branch
            ok_log = False
            log_stdout = ""
            log_stderr = ""
            root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir

            try:
                if self.is_local:
                    if HAS_GITPYTHON:
                        try:
                            repo = Repo(root_dir, search_parent_directories=True)
                            args = [
                                "--topo-order",
                                "--date=relative",
                                f"--format=format:COMMIT_DELIM\t%h\t%p\t%d\t%s\t%an\t%ar\t%H",
                                "-n", "100"
                            ]
                            if use_all:
                                args.insert(1, "--all")
                            log_stdout = repo.git.log(*args)
                            ok_log = True
                        except Exception as e:
                            log_stderr = str(e)
                    else:
                        try:
                            args = ["git", "-C", root_dir, "log", "--topo-order"]
                            if use_all:
                                args.append("--all")
                            args.extend([
                                "--date=relative",
                                "--format=format:COMMIT_DELIM\t%h\t%p\t%d\t%s\t%an\t%ar\t%H",
                                "-n", "100"
                            ])
                            res_l = subprocess.run(args, capture_output=True, text=True)
                            ok_log = (res_l.returncode == 0)
                            log_stdout = res_l.stdout
                            log_stderr = res_l.stderr
                        except Exception as e:
                            log_stderr = str(e)
                else:
                    all_flag = "--all" if use_all else ""
                    cmd = f"git -C '{root_dir}' -c safe.directory='*' log --topo-order {all_flag} --date=relative --format=format:'COMMIT_DELIM%x09%h%x09%p%x09%d%x09%s%x09%an%x09%ar%x09%H' -n 100"
                    ok_log, log_stdout, log_stderr = self._exec_remote_cmd(cmd)
            except Exception as e:
                log_stderr = str(e)
            finally:
                def on_done():
                    if not self.winfo_exists():
                        return
                    self._is_loading = False
                    self.btn_refresh.configure(state="normal")

                    if not ok_log:
                        self.lbl_status.configure(text=f"Gagal membaca history: {log_stderr.strip() or 'Error'}", text_color=COLORS["danger"])
                        return

                    self._parse_and_populate_commits(log_stdout)

                try:
                    self.after(0, on_done)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _parse_and_populate_commits(self, raw_output: str):
        self._commits.clear()
        lines = raw_output.splitlines()

        for line in lines:
            if "COMMIT_DELIM\t" in line:
                meta_part = line.split("COMMIT_DELIM\t", 1)[1]
                parts = meta_part.split("\t")
                if len(parts) >= 7:
                    short_h, parents_raw, refs, subject, author, rel_date, full_h = parts[:7]
                    parents_list = [p.strip() for p in parents_raw.strip().split() if p.strip()]
                elif len(parts) >= 6:
                    short_h, refs, subject, author, rel_date, full_h = parts[:6]
                    parents_list = []
                else:
                    continue

                clean_refs = refs.strip()
                if clean_refs.startswith("(") and clean_refs.endswith(")"):
                    clean_refs = clean_refs[1:-1].strip()

                self._commits.append({
                    "hash": short_h.strip(),
                    "parents": parents_list,
                    "refs": clean_refs,
                    "message": subject.strip(),
                    "author": author.strip(),
                    "date": rel_date.strip(),
                    "full_hash": full_h.strip()
                })

        self._compute_and_render_graph()
        self._filter_displayed_commits()

    def _compute_and_render_graph(self):
        """
        Menghitung topologi git graph (jalur branch, commit node, merge/fork connections)
        dan merender gambar berkualitas tinggi untuk setiap baris commit.
        """
        self._graph_images.clear()
        if not self._commits:
            return

        lanes: List[Optional[str]] = []
        rows_info = []

        for idx, c in enumerate(self._commits):
            chash = c["hash"]
            parents = c.get("parents", [])
            entering_lanes = list(lanes)

            if chash in lanes:
                commit_lane = lanes.index(chash)
            else:
                if None in lanes:
                    commit_lane = lanes.index(None)
                    lanes[commit_lane] = chash
                else:
                    commit_lane = len(lanes)
                    lanes.append(chash)

            has_above = (commit_lane < len(entering_lanes) and entering_lanes[commit_lane] == chash)

            down_connections = []
            if not parents:
                lanes[commit_lane] = None
            else:
                p0 = parents[0]
                if p0 in lanes and lanes.index(p0) != commit_lane:
                    down_connections.append((commit_lane, lanes.index(p0)))
                    lanes[commit_lane] = None
                else:
                    lanes[commit_lane] = p0
                    down_connections.append((commit_lane, commit_lane))

                for pk in parents[1:]:
                    if pk in lanes:
                        down_connections.append((commit_lane, lanes.index(pk)))
                    else:
                        if None in lanes:
                            pk_lane = lanes.index(None)
                            lanes[pk_lane] = pk
                        else:
                            pk_lane = len(lanes)
                            lanes.append(pk)
                        down_connections.append((commit_lane, pk_lane))

            exiting_lanes = list(lanes)
            passing_lanes = []
            max_active = max(len(entering_lanes), len(exiting_lanes), commit_lane + 1)
            for l in range(max_active):
                if l == commit_lane:
                    continue
                ent = entering_lanes[l] if l < len(entering_lanes) else None
                ext = exiting_lanes[l] if l < len(exiting_lanes) else None
                if ent is not None and ext is not None and ent == ext:
                    passing_lanes.append(l)

            while lanes and lanes[-1] is None:
                lanes.pop()

            rows_info.append({
                "commit_lane": commit_lane,
                "has_above": has_above,
                "down_connections": down_connections,
                "passing_lanes": passing_lanes,
                "max_lanes": max_active
            })

        max_all_lanes = max((r["max_lanes"] for r in rows_info), default=1)
        lane_width = 16
        left_pad = 14
        row_height = 32
        col_width = max(55, min(260, left_pad + max_all_lanes * lane_width + 12))

        try:
            self.tree_history.column("#0", width=col_width, minwidth=col_width)
        except Exception:
            pass

        scale = 2  # Supersampling 2x untuk antialiasing kristal jernih
        W = col_width * scale
        H = row_height * scale

        for idx, (c, r) in enumerate(zip(self._commits, rows_info)):
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(im)

            c_lane = r["commit_lane"]
            c_color = GRAPH_PALETTE[c_lane % len(GRAPH_PALETTE)]

            # 1. Jalur passing lanes (garis lurus menerus dari atas ke bawah)
            for p_lane in r["passing_lanes"]:
                px = int((left_pad + p_lane * lane_width) * scale)
                p_col = GRAPH_PALETTE[p_lane % len(GRAPH_PALETTE)]
                draw.line([(px, 0), (px, H)], fill=p_col, width=int(2.2 * scale))

            # 2. Garis masuk dari atas menuju node commit
            cx = int((left_pad + c_lane * lane_width) * scale)
            cy = int((row_height / 2) * scale)

            if r["has_above"]:
                draw.line([(cx, 0), (cx, cy)], fill=c_color, width=int(2.2 * scale))

            # 3. Koneksi ke bawah (parent lanes)
            for from_l, to_l in r["down_connections"]:
                fx = int((left_pad + from_l * lane_width) * scale)
                tx = int((left_pad + to_l * lane_width) * scale)
                l_col = GRAPH_PALETTE[to_l % len(GRAPH_PALETTE)] if from_l != to_l else c_color

                if fx == tx:
                    draw.line([(fx, cy), (fx, H)], fill=c_color, width=int(2.2 * scale))
                else:
                    pts = []
                    steps = 16
                    for s in range(steps + 1):
                        t = s / steps
                        bx = (1 - t)**3 * fx + 3 * (1 - t)**2 * t * fx + 3 * (1 - t) * t**2 * tx + t**3 * tx
                        by = (1 - t)**3 * cy + 3 * (1 - t)**2 * t * ((cy + H) / 2) + 3 * (1 - t) * t**2 * ((cy + H) / 2) + t**3 * H
                        pts.append((bx, by))
                    draw.line(pts, fill=l_col, width=int(2.2 * scale))

            # 4. Simpul Node Commit (lingkaran elegan dengan cincin kontras)
            radius = int(5.5 * scale)
            draw.ellipse(
                [(cx - radius, cy - radius), (cx + radius, cy + radius)],
                fill=c_color,
                outline=(240, 246, 252, 230),
                width=int(1.6 * scale)
            )
            # Inti dot putih kecil di tengah
            core_r = int(2.2 * scale)
            draw.ellipse(
                [(cx - core_r, cy - core_r), (cx + core_r, cy + core_r)],
                fill=(255, 255, 255, 255)
            )

            # Downsample ke ukuran target
            im_final = im.resize((col_width, row_height), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(im_final)
            self._graph_images.append(tk_img)
            c["graph_img"] = tk_img

    def _filter_displayed_commits(self):
        query = self.entry_filter.get().strip().lower()
        for item in self.tree_history.get_children():
            self.tree_history.delete(item)

        first_selectable = None
        for idx, c in enumerate(self._commits):
            if not c.get("hash"):
                continue

            if query:
                text_to_search = f"{c['hash']} {c['refs']} {c['message']} {c['author']}".lower()
                if query not in text_to_search:
                    continue

            commit_text = c["message"]
            if c["refs"]:
                commit_text = f"[{c['refs']}] {commit_text}"

            author_date = f"{c['author']} • {c['date']}"
            iid = str(idx)
            g_img = c.get("graph_img")
            if g_img:
                self.tree_history.insert("", "end", iid=iid, image=g_img, values=(commit_text, author_date, c["hash"]))
            else:
                self.tree_history.insert("", "end", iid=iid, values=(commit_text, author_date, c["hash"]))

            if first_selectable is None:
                first_selectable = iid

        if first_selectable and self._active_tab == "History":
            self.tree_history.selection_set(first_selectable)
            idx = int(first_selectable) if first_selectable.isdigit() else -1
            if 0 <= idx < len(self._commits) and self._commits[idx].get("hash"):
                self._load_history_commit_details(self._commits[idx]["hash"])

    def _on_history_commit_selected(self, event=None):
        sel = self.tree_history.selection()
        if not sel:
            return
        idx = int(sel[0]) if sel[0].isdigit() else -1
        commit_hash = ""
        if 0 <= idx < len(self._commits):
            commit_hash = self._commits[idx].get("hash") or ""
        else:
            vals = self.tree_history.item(sel[0], "values")
            if vals:
                commit_hash = vals[-1]
        if commit_hash:
            self._load_history_commit_details(commit_hash)

    def _load_history_commit_details(self, commit_hash: str):
        self._selected_commit_hash = commit_hash
        self.btn_copy_sha.configure(text=f"{commit_hash} Copy")
        if hasattr(self, "btn_cherry_pick"):
            self.btn_cherry_pick.configure(state="normal", text=" Cherry-pick")
        if hasattr(self, "btn_hist_cherry_pick"):
            self.btn_hist_cherry_pick.configure(state="normal", text=" Cherry-pick")

        def worker():
            raw_show = ""
            commit_obj = None
            root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir

            try:
                if self.is_local and HAS_GITPYTHON:
                    try:
                        repo = Repo(root_dir, search_parent_directories=True)
                        try:
                            commit_obj = repo.commit(commit_hash)
                        except Exception:
                            pass
                        raw_show = repo.git.show(commit_hash, "--stat", "--patch", "--color=never")
                    except Exception as e:
                        raw_show = str(e)
                elif self.is_local:
                    res = subprocess.run(
                        ["git", "-C", root_dir, "show", "--stat", "--patch", "--color=never", commit_hash],
                        capture_output=True, text=True
                    )
                    raw_show = res.stdout or res.stderr
                else:
                    ok, out, err = self._exec_remote_cmd(f"git -C '{root_dir}' -c safe.directory='*' show --stat --patch --color=never {commit_hash}")
                    raw_show = out or err

                if raw_show and len(raw_show) > 120000:
                    raw_show = raw_show[:120000] + "\n\n... [Commit diff dipersingkat: output terlalu besar]"
            except Exception as e:
                raw_show = f"Error loading commit: {e}"
            finally:
                def on_done():
                    if not self.winfo_exists():
                        return
                    self._render_history_commit_card(raw_show, commit_obj)

                try:
                    self.after(0, on_done)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _render_history_commit_card(self, raw_show: str, commit_obj: Any = None):
        sections = re.split(r'(?=diff --git a/)', raw_show)
        header_sec = sections[0] if sections else ""
        diff_secs = sections[1:] if len(sections) > 1 else []

        subject = ""
        body_lines = []
        author_name = "Unknown"
        author_email = ""
        commit_date = ""

        if commit_obj:
            subject = commit_obj.summary
            body_lines = [l for l in commit_obj.message.splitlines()[1:] if l.strip()]
            author_name = commit_obj.author.name
            author_email = commit_obj.author.email
            commit_date = str(commit_obj.authored_datetime)
            full_sha = commit_obj.hexsha
        else:
            full_sha = self._selected_commit_hash
            in_msg = False
            for line in header_sec.splitlines():
                if line.startswith("Author:"):
                    m = re.match(r"Author:\s*(.*?)(?:<(.*?)>)?$", line)
                    if m:
                        author_name = m.group(1).strip()
                        author_email = (m.group(2) or "").strip()
                elif line.startswith("Date:"):
                    commit_date = line.replace("Date:", "").strip()
                    in_msg = True
                elif in_msg:
                    stripped = line.strip()
                    if stripped == "---":
                        break
                    if stripped:
                        if not subject:
                            subject = stripped
                        else:
                            body_lines.append(stripped)

        self.lbl_commit_title.configure(text=subject or f"Commit {self._selected_commit_hash}")
        self.lbl_commit_body.configure(text="\n".join(body_lines[:3]))
        self.lbl_author_info.configure(text=f"By {author_name}" + (f" <{author_email}>" if author_email else ""))
        self.lbl_date_info.configure(text=f"• {commit_date}")
        self.lbl_sha_full.configure(text=f"SHA: {full_sha[:10]}")

        # Files changed list
        self._history_files_data.clear()
        total_adds = 0
        total_dels = 0

        for sec in diff_secs:
            lines = sec.splitlines()
            first_line = lines[0] if lines else ""
            m_f = re.search(r"diff --git a/(.*?) b/(.*)", first_line)
            fname = m_f.group(1) if m_f else "Unknown"

            ftype = "M"
            if "new file mode" in sec:
                ftype = "A"
            elif "deleted file mode" in sec:
                ftype = "D"
            elif "similarity index" in sec or "rename from" in sec:
                ftype = "R"

            adds = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
            dels = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
            total_adds += adds
            total_dels += dels

            self._history_files_data.append({
                "name": fname,
                "type": ftype,
                "add": adds,
                "del": dels,
                "diff": sec
            })

        self._history_all_diff = "\n".join(diff_secs) if diff_secs else raw_show
        num_files = len(self._history_files_data)
        self.lbl_summary_stats.configure(text=f"{num_files} changed files")
        self.lbl_additions_badge.configure(text=f"+{total_adds}")
        self.lbl_deletions_badge.configure(text=f"-{total_dels}")

        for item in self.tree_files.get_children():
            self.tree_files.delete(item)

        self.tree_files.insert("", "end", iid="all", image=get_tk_image("file-code", (14, 14), COLORS["accent"]), values=("ALL", f"All Files ({num_files})", f"+{total_adds} -{total_dels}"))
        for idx, f in enumerate(self._history_files_data):
            f_img = get_file_type_tk_image(f["name"], size=(14, 14))
            self.tree_files.insert("", "end", iid=str(idx), image=f_img, values=(f"[{f['type']}]", f["name"], f"+{f['add']} -{f['del']}"))

        self.tree_files.selection_set("all")
        self._render_diff_text("All Files", self._history_all_diff)

    def _on_history_file_selected(self, event=None):
        sel = self.tree_files.selection()
        if not sel:
            return
        sel_id = sel[0]
        if sel_id == "all":
            self._render_diff_text("All Files", self._history_all_diff)
        else:
            idx = int(sel_id) if sel_id.isdigit() else -1
            if 0 <= idx < len(self._history_files_data):
                f = self._history_files_data[idx]
                self._render_diff_text(f["name"], f["diff"])

    # -------------------------------------------------------------
    # 9. DIFF RENDERER & SYNTAX HIGHLIGHTING
    # -------------------------------------------------------------
    def _render_diff_text(self, title: str, diff_content: str):
        self.lbl_diff_title.configure(text=f"Diff: {title}")
        self.txt_diff.delete("1.0", "end")
        self.txt_diff.insert("1.0", diff_content)
        self._format_diff_tags()

    def _format_diff_tags(self):
        tb = getattr(self.txt_diff, "_textbox", self.txt_diff)
        tb.tag_configure("diff_add", foreground="#3FB950", background="#12261E")        # Hijau GitHub
        tb.tag_configure("diff_del", foreground="#F85149", background="#2E1518")        # Merah GitHub
        tb.tag_configure("diff_hunk", foreground="#58A6FF", background="#161B22")       # Cyan/Blue Hunk
        tb.tag_configure("diff_file", foreground="#E6EDF3", background="#21262D", font=("Menlo" if os.name != "nt" else "Consolas", 11, "bold"))
        tb.tag_configure("diff_header", foreground="#8B949E")

        lines = self.txt_diff.get("1.0", "end-1c").splitlines()
        # Batasi pewarnaan sintaks maksimal 300 baris agar antarmuka tidak freeze
        for idx, line in enumerate(lines[:300], start=1):
            line_start = f"{idx}.0"
            line_end = f"{idx}.end"

            if line.startswith("diff --git"):
                tb.tag_add("diff_file", line_start, line_end)
            elif line.startswith("@@"):
                tb.tag_add("diff_hunk", line_start, line_end)
            elif line.startswith("+++") or line.startswith("---"):
                tb.tag_add("diff_header", line_start, line_end)
            elif line.startswith("+"):
                tb.tag_add("diff_add", line_start, line_end)
            elif line.startswith("-"):
                tb.tag_add("diff_del", line_start, line_end)
            elif line.startswith("index ") or line.startswith("new file ") or line.startswith("deleted file "):
                tb.tag_add("diff_header", line_start, line_end)

    def _copy_selected_hash(self):
        sel = self.tree_history.selection()
        if not sel:
            return
        idx = int(sel[0]) if sel[0].isdigit() else -1
        copy_val = ""
        if 0 <= idx < len(self._commits):
            copy_val = self._commits[idx].get("full_hash") or self._commits[idx].get("hash") or ""
        else:
            vals = self.tree_history.item(sel[0], "values")
            if vals:
                copy_val = vals[-1]

        if copy_val:
            self.clipboard_clear()
            self.clipboard_append(copy_val)
            self.lbl_status.configure(text=f"Copied SHA: {copy_val} ✓", text_color=COLORS["success_text"])

    def _open_terminal_here(self):
        """Membuka terminal langsung pada folder repositori."""
        root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir
        if self.is_local:
            res = launch_local_terminal(initial_dir=root_dir)
            if not res.get("success"):
                messagebox.showerror("Terminal Error", res.get("error", "Gagal membuka terminal lokal"), parent=self)
        else:
            if not self.host:
                messagebox.showwarning("Peringatan", "Informasi host remote tidak tersedia.", parent=self)
                return
            res = launch_ssh_terminal(host=self.host, initial_dir=root_dir)
            if not res.get("success"):
                messagebox.showerror("Terminal Error", res.get("error", "Gagal membuka terminal SSH"), parent=self)

    # -------------------------------------------------------------
    # 10. CHERRY-PICK ACTIONS & CONFLICT HANDLING
    # -------------------------------------------------------------
    def _build_history_context_menu(self):
        self.menu_history = tk.Menu(self, tearoff=False, bg=get_color("surface"), fg=get_color("text"), activebackground=get_color("accent"))
        self.menu_history.add_command(label="Cherry-pick Commit Terpilih...", command=self._do_cherry_pick)
        self.menu_history.add_command(label="Cherry-pick dari Commit Hash (Input/Paste)...", command=self._open_cherry_pick_by_hash_dialog)
        self.menu_history.add_separator()
        self.menu_history.add_command(label="Salin Commit SHA", command=self._copy_selected_hash)
        self.menu_history.add_command(label="Buka Terminal di Sini", command=self._open_terminal_here)
        self.menu_history.add_command(label="Refresh Git Graph", command=self._refresh_all_data)

    def _show_history_context_menu(self, event):
        item = self.tree_history.identify_row(event.y)
        if item:
            self.tree_history.selection_set(item)
            self._on_history_commit_selected()
        try:
            self.menu_history.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_history.grab_release()

    def _do_cherry_pick(self):
        """Memulai proses Cherry-pick dari commit yang sedang terpilih ke branch aktif."""
        commit_hash = self._selected_commit_hash
        if not commit_hash:
            sel = self.tree_history.selection()
            if sel:
                idx = int(sel[0]) if sel[0].isdigit() else -1
                if 0 <= idx < len(self._commits):
                    commit_hash = self._commits[idx].get("full_hash") or self._commits[idx].get("hash")
                else:
                    vals = self.tree_history.item(sel[0], "values")
                    if vals:
                        commit_hash = vals[-1]

        if not commit_hash:
            # Jika belum ada commit yang terpilih di list, langsung buka dialog input hash
            self._open_cherry_pick_by_hash_dialog()
            return

        commit_info = next(
            (c for c in self._commits if c.get("hash") == commit_hash or c.get("full_hash") == commit_hash),
            None
        )
        short_hash = commit_hash[:8]
        msg = commit_info.get("message", "") if commit_info else f"Commit {short_hash}"
        author = commit_info.get("author", "") if commit_info else ""
        target_branch = self._current_branch or "HEAD"

        # Peringatan bila ada perubahan lokal belum di-commit
        if self._working_changes:
            dirty_count = len(self._working_changes)
            confirm_dirty = messagebox.askyesno(
                "Working Directory Tidak Bersih",
                f"Terdapat {dirty_count} file yang berubah dan belum di-commit di working tree.\n\n"
                f"Git menyarankan untuk melakukan commit atau discard perubahan lokal "
                f"sebelum melakukan Cherry-pick guna menghindari konflik.\n\n"
                f"Apakah Anda ingin tetap melanjutkan Cherry-pick?",
                icon="warning",
                parent=self
            )
            if not confirm_dirty:
                return

        # Konfirmasi pengguna
        author_line = f"\n• Author: {author}" if author else ""
        confirm = messagebox.askyesno(
            "Konfirmasi Cherry-pick",
            f"Terapkan (cherry-pick) commit berikut ke branch aktif '{target_branch}'?\n\n"
            f"• Commit: {short_hash}\n"
            f"• Pesan: {msg}{author_line}\n"
            f"• Target Branch: {target_branch}\n\n"
            f"Lanjutkan proses Cherry-pick?",
            parent=self
        )
        if not confirm:
            return

        self._execute_cherry_pick(commit_hash, short_hash, msg, target_branch)

    def _execute_cherry_pick(self, commit_hash: str, short_hash: str, msg: str, target_branch: str, append_x: bool = False):
        if hasattr(self, "btn_cherry_pick"):
            self.btn_cherry_pick.configure(state="disabled", text=" Cherry-picking...")
        if hasattr(self, "btn_hist_cherry_pick"):
            self.btn_hist_cherry_pick.configure(state="disabled", text=" Working...")

        self.lbl_status.configure(
            text=f"Menjalankan cherry-pick commit {short_hash} ke {target_branch}...",
            text_color=COLORS["accent"]
        )

        def worker():
            ok = False
            output = ""
            root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir
            x_flag = "-x" if append_x else ""

            try:
                if self.is_local:
                    args = ["git", "-C", root_dir, "cherry-pick"]
                    if append_x:
                        args.append("-x")
                    args.append(commit_hash)
                    res = subprocess.run(
                        args,
                        capture_output=True,
                        text=True
                    )
                    ok = (res.returncode == 0)
                    output = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
                else:
                    cmd = f"git -C '{root_dir}' -c safe.directory='*' cherry-pick {x_flag} {commit_hash}".strip()
                    ok_remote, out, err = self._exec_remote_cmd(cmd)
                    ok = ok_remote
                    output = (out or "") + ("\n" + err if err else "")
            except Exception as e:
                output = str(e)
                ok = False

            def on_done():
                if not self.winfo_exists():
                    return

                if hasattr(self, "btn_cherry_pick"):
                    self.btn_cherry_pick.configure(state="normal", text=" Cherry-pick")
                if hasattr(self, "btn_hist_cherry_pick"):
                    self.btn_hist_cherry_pick.configure(state="normal", text=" Cherry-pick")

                out_lower = output.lower()
                is_conflict = ("conflict" in out_lower or "could not apply" in out_lower or "after resolving the conflicts" in out_lower)
                is_empty = ("empty" in out_lower or "nothing to commit" in out_lower or "already" in out_lower)

                if ok and not is_conflict:
                    self.lbl_status.configure(
                        text=f"Cherry-pick commit {short_hash} berhasil diterapkan ke {target_branch} ✓",
                        text_color=COLORS["success_text"]
                    )
                    messagebox.showinfo(
                        "Cherry-pick Berhasil",
                        f"Commit {short_hash} ('{msg}') berhasil diterapkan ke branch '{target_branch}'!",
                        parent=self
                    )
                    self._refresh_all_data()
                elif is_conflict:
                    self.lbl_status.configure(
                        text=f"Cherry-pick {short_hash} mengalami Merge Conflict!",
                        text_color=COLORS["danger"]
                    )
                    self._handle_cherry_pick_conflict(short_hash, output)
                    self._refresh_all_data()
                elif is_empty:
                    self.lbl_status.configure(
                        text=f"Commit {short_hash} kosong atau sudah diterapkan.",
                        text_color=COLORS["warning"]
                    )
                    messagebox.showinfo(
                        "Cherry-pick Selesai",
                        f"Perubahan dari commit {short_hash} tampaknya sudah ada pada branch '{target_branch}' "
                        f"atau tidak menghasilkan perubahan baru.\n\nDetail:\n{output.strip()}",
                        parent=self
                    )
                    self._refresh_all_data()
                else:
                    self.lbl_status.configure(
                        text="Gagal melakukan cherry-pick!",
                        text_color=COLORS["danger"]
                    )
                    messagebox.showerror(
                        "Cherry-pick Gagal",
                        f"Gagal melakukan cherry-pick commit {short_hash}:\n\n{output.strip()}",
                        parent=self
                    )

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _handle_cherry_pick_conflict(self, short_hash: str, output: str):
        """Menampilkan modal penanganan merge conflict akibat cherry-pick."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Cherry-pick Merge Conflict")
        dialog.geometry("540x370")
        dialog.minsize(480, 310)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["window"])

        pad = 16
        lbl_icon = ctk.CTkLabel(
            dialog,
            text="",
            image=get_icon("git-branch", (24, 24), COLORS["danger"])
        )
        lbl_icon.pack(pady=(pad, 4))

        lbl_head = ctk.CTkLabel(
            dialog,
            text=f"Konflik Penggabungan pada Commit {short_hash}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["danger"]
        )
        lbl_head.pack(pady=(0, 6))

        lbl_desc = ctk.CTkLabel(
            dialog,
            text=(
                "Git mendeteksi konflik (merge conflict) saat menerapkan commit ini.\n"
                "Anda dapat menyelesaikan konflik di tab 'Changes' / Editor lalu jalankan 'git cherry-pick --continue',\n"
                "atau batalkan seluruh proses cherry-pick ini sekarang (git cherry-pick --abort)."
            ),
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text"],
            justify="center",
            wraplength=480
        )
        lbl_desc.pack(pady=(0, 10), padx=pad)

        txt_out = ctk.CTkTextbox(
            dialog,
            height=110,
            font=ctk.CTkFont(family="Consolas" if os.name == "nt" else "Menlo", size=10),
            fg_color=COLORS["input_bg"],
            text_color=COLORS["muted"],
            wrap="word"
        )
        txt_out.pack(fill="both", expand=True, padx=pad, pady=(0, 12))
        txt_out.insert("1.0", output.strip())
        txt_out.configure(state="disabled")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=pad, pady=(0, pad))

        def on_abort():
            dialog.destroy()
            self._abort_cherry_pick()

        def on_open_terminal():
            dialog.destroy()
            self._open_terminal_here()

        def on_close():
            dialog.destroy()
            self.seg_tabs.set("Changes")
            self._on_tab_changed("Changes")

        btn_abort = ctk.CTkButton(
            btn_row,
            text="Batalkan (Abort)",
            fg_color=COLORS["danger_subtle"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["danger_text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=on_abort
        )
        btn_abort.pack(side="left", padx=(0, 6))

        btn_term = ctk.CTkButton(
            btn_row,
            text="Buka Terminal",
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=11),
            command=on_open_terminal
        )
        btn_term.pack(side="left", padx=(0, 6))

        btn_solve = ctk.CTkButton(
            btn_row,
            text="Lihat di Tab Changes",
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=on_close
        )
        btn_solve.pack(side="right")

    def _abort_cherry_pick(self):
        """Membatalkan cherry-pick yang sedang berjalan."""
        self.lbl_status.configure(text="Membatalkan cherry-pick (git cherry-pick --abort)...", text_color=COLORS["danger"])
        root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir

        def worker():
            if self.is_local:
                subprocess.run(["git", "-C", root_dir, "cherry-pick", "--abort"], capture_output=True)
            else:
                self._exec_remote_cmd(f"git -C '{root_dir}' -c safe.directory='*' cherry-pick --abort")

            def on_done():
                if not self.winfo_exists():
                    return
                self.lbl_status.configure(text="Cherry-pick berhasil dibatalkan ✓", text_color=COLORS["success_text"])
                self._refresh_all_data()

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _open_cherry_pick_by_hash_dialog(self, initial_hash: str = ""):
        """
        Membuka dialog interaktif untuk melakukan cherry-pick dari commit hash/SHA tertentu.
        Mendukung auto-paste clipboard, preview commit, dan tombol fetch all dari origin.
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("Cherry-pick Commit by Hash")
        dialog.geometry("560x430")
        dialog.minsize(500, 390)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["window"])

        target_branch = self._current_branch or "HEAD"
        host_label = "Local" if self.is_local else (self.host.get("label") or self.host.get("hostname") or "Remote")

        pad = 16

        # Header Info
        header_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        header_frame.pack(fill="x", padx=pad, pady=(pad, 6))

        ctk.CTkLabel(
            header_frame,
            text=f"Cherry-pick ke Branch: {target_branch}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        ).pack(side="left")

        lbl_badge = ctk.CTkLabel(
            header_frame,
            text=f" {host_label} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLORS["accent_subtle"],
            text_color=COLORS["accent_text"],
            corner_radius=4,
            height=20
        )
        lbl_badge.pack(side="right")

        ctk.CTkLabel(
            dialog,
            text=(
                f"Masukkan atau tempel (paste) Commit Hash dari branch/host lain untuk diterapkan ke branch aktif '{target_branch}'.\n"
                f"Contoh: Commit yang di-push ke staging dari Host lain."
            ),
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"],
            justify="left",
            wraplength=520
        ).pack(anchor="w", padx=pad, pady=(0, 10))

        # Input Box + Paste Button
        input_frame = ctk.CTkFrame(dialog, fg_color=COLORS["input_bg"], corner_radius=6, border_width=1, border_color=COLORS["line"])
        input_frame.pack(fill="x", padx=pad, pady=(0, 10))
        input_frame.grid_columnconfigure(0, weight=1)

        entry_hash = ctk.CTkEntry(
            input_frame,
            placeholder_text="Tempel Commit Hash di sini (misal: a1b2c3d atau 40 karakter SHA)...",
            height=34,
            font=ctk.CTkFont(family="Consolas" if os.name == "nt" else "Menlo", size=11),
            fg_color="transparent",
            border_width=0
        )
        entry_hash.grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=4)

        btn_paste = ctk.CTkButton(
            input_frame,
            text=" Paste",
            image=get_icon("copy", (12, 12), COLORS["text"]),
            width=75, height=26,
            corner_radius=4,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=10),
            command=lambda: _paste_from_clipboard()
        )
        btn_paste.grid(row=0, column=1, padx=(0, 6), pady=4)

        # Card Preview Info Commit
        card_preview = ctk.CTkFrame(dialog, fg_color=COLORS["surface"], corner_radius=6, border_width=1, border_color=COLORS["line"])
        card_preview.pack(fill="both", expand=True, padx=pad, pady=(0, 10))

        lbl_preview_title = ctk.CTkLabel(
            card_preview,
            text="Status Commit:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        lbl_preview_title.pack(anchor="w", padx=12, pady=(8, 4))

        lbl_preview_details = ctk.CTkLabel(
            card_preview,
            text="Ketik atau tempel hash di atas untuk memeriksa commit.",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"],
            anchor="w",
            justify="left",
            wraplength=510
        )
        lbl_preview_details.pack(anchor="w", padx=12, pady=(0, 8))

        btn_fetch_all = ctk.CTkButton(
            card_preview,
            text=" Fetch All from Origin",
            image=get_icon("download", (11, 11), COLORS["text"]),
            width=160, height=26,
            corner_radius=4,
            fg_color=COLORS["input_bg"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=10),
            command=lambda: _do_fetch_remote()
        )

        def _do_fetch_remote():
            btn_fetch_all.configure(state="disabled", text=" Fetching...")
            lbl_preview_details.configure(text="Menjalankan 'git fetch --all --prune' dari remote origin...", text_color=COLORS["accent"])

            def worker_fetch():
                root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir
                cred_flag = self._get_git_credential_flag()
                if self.is_local:
                    subprocess.run(f"git {cred_flag}fetch --all --prune", cwd=root_dir, shell=True, capture_output=True)
                else:
                    self._exec_remote_cmd(f"git -C '{root_dir}' {cred_flag}fetch --all --prune", timeout=30)

                def on_fetch_done():
                    if not dialog.winfo_exists():
                        return
                    btn_fetch_all.configure(state="normal", text=" Fetch All from Origin")
                    _check_commit_preview()

                self.after(0, on_fetch_done)

            threading.Thread(target=worker_fetch, daemon=True).start()

        def _check_commit_preview():
            raw_hash = entry_hash.get().strip()
            if not raw_hash or len(raw_hash) < 4:
                lbl_preview_title.configure(text="Status Commit:", text_color=COLORS["text_secondary"])
                lbl_preview_details.configure(text="Ketik atau tempel hash di atas untuk memeriksa commit.", text_color=COLORS["muted"])
                btn_fetch_all.pack_forget()
                return

            def worker_preview():
                root_dir = getattr(self, "repo_root", self.target_dir) or self.target_dir
                info = None
                clean_hash = raw_hash.replace("'", "").replace('"', '').strip()
                if self.is_local:
                    res = subprocess.run(
                        ["git", "-C", root_dir, "log", "-1", "--format=%h\t%s\t%an\t%ar", clean_hash],
                        capture_output=True, text=True
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        info = res.stdout.strip().split("\t")
                else:
                    cmd = f"git -C '{root_dir}' -c safe.directory='*' log -1 --format='%h%x09%s%x09%an%x09%ar' '{clean_hash}' 2>/dev/null"
                    ok, out, _ = self._exec_remote_cmd(cmd, timeout=8)
                    if ok and out.strip():
                        info = out.strip().split("\t")

                def on_preview_done():
                    if not dialog.winfo_exists():
                        return
                    if info and len(info) >= 2:
                        sh, subj = info[0], info[1]
                        author = info[2] if len(info) > 2 else ""
                        rel_date = info[3] if len(info) > 3 else ""
                        lbl_preview_title.configure(text=f"✅ Commit Ditemukan ({sh})", text_color="#3FB950")
                        lbl_preview_details.configure(
                            text=f"• Pesan: {subj}\n• Author: {author} ({rel_date})",
                            text_color=COLORS["text"]
                        )
                        btn_fetch_all.pack_forget()
                    else:
                        lbl_preview_title.configure(text="⚠️ Commit Belum Ditemukan di Repo Lokal", text_color="#D29922")
                        lbl_preview_details.configure(
                            text="Commit ini belum ada di repositori lokal host ini.\n"
                                 "Jika baru saja di-push ke staging dari host lain, klik tombol di bawah untuk fetch dari origin:",
                            text_color=COLORS["muted"]
                        )
                        btn_fetch_all.pack(anchor="w", padx=12, pady=(0, 8))

                self.after(0, on_preview_done)

            threading.Thread(target=worker_preview, daemon=True).start()

        def _paste_from_clipboard():
            try:
                txt = self.clipboard_get().strip()
                if txt:
                    entry_hash.delete(0, "end")
                    entry_hash.insert(0, txt)
                    _check_commit_preview()
            except Exception:
                pass

        # Cek clipboard otomatis saat dialog dibuka
        cb_text = ""
        try:
            cb_text = self.clipboard_get().strip()
        except Exception:
            pass

        if initial_hash:
            entry_hash.insert(0, initial_hash.strip())
            _check_commit_preview()
        elif cb_text and len(cb_text) >= 6 and len(cb_text) <= 40 and re.match(r'^[0-9a-fA-F]+$', cb_text):
            entry_hash.insert(0, cb_text)
            _check_commit_preview()

        entry_hash.bind("<KeyRelease>", lambda e: _check_commit_preview())

        # Options: -x flag
        var_x = ctk.BooleanVar(value=True)
        chk_x = ctk.CTkCheckBox(
            dialog,
            text="Tambahkan baris keterangan sumber (-x: '(cherry picked from commit ...)')",
            variable=var_x,
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text"],
            checkbox_width=16, checkbox_height=16
        )
        chk_x.pack(anchor="w", padx=pad, pady=(0, 10))

        # Bottom buttons
        btn_bar = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_bar.pack(fill="x", padx=pad, pady=(0, pad))

        btn_cancel = ctk.CTkButton(
            btn_bar,
            text="Batal",
            width=80, height=32,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=11),
            command=dialog.destroy
        )
        btn_cancel.pack(side="left")

        def _confirm_and_run():
            target_hash = entry_hash.get().strip()
            if not target_hash:
                messagebox.showwarning("Peringatan", "Harap masukkan commit hash terlebih dahulu.", parent=dialog)
                return

            if self._working_changes:
                dirty_count = len(self._working_changes)
                confirm_dirty = messagebox.askyesno(
                    "Working Directory Tidak Bersih",
                    f"Terdapat {dirty_count} file yang berubah di working tree.\n\n"
                    f"Apakah Anda ingin tetap melanjutkan Cherry-pick?",
                    icon="warning",
                    parent=dialog
                )
                if not confirm_dirty:
                    return

            short_h = target_hash[:8]
            dialog.destroy()
            self._execute_cherry_pick(
                target_hash,
                short_h,
                f"Commit {short_h}",
                target_branch,
                append_x=var_x.get()
            )

        btn_exec = ctk.CTkButton(
            btn_bar,
            text=" Jalankan Cherry-pick",
            image=get_icon("git-branch", (13, 13), "#FFFFFF"),
            height=32,
            corner_radius=6,
            fg_color="#238636",
            hover_color="#2EA043",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=_confirm_and_run
        )
        btn_exec.pack(side="right")
