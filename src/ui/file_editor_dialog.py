import os
import re
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from theme import COLORS
from icons import get_icon, get_tk_image
from sftp_service import SFTPService
from ui.tab_bar import HorizontalScrollableTabBar

try:
    from pygments.lexers import get_lexer_for_filename, get_lexer_by_name, TextLexer
    from pygments.token import Token
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False
    Token = None


# --- VS Code Dark+ Theme Palette ---
VSCODE = {
    "editor_bg": "#1E1E1E",
    "editor_fg": "#D4D4D4",
    "gutter_bg": "#1E1E1E",
    "gutter_fg": "#858585",
    "gutter_active": "#C6C6C6",
    "gutter_border": "#2B2B2B",
    "current_line": "#282828",
    "selection_bg": "#2A5D8F",
    "selection_fg": "#FFFFFF",
    "cursor_color": "#AEAFAD",
    "tab_bar_bg": "#252526",
    "active_tab_bg": "#1E1E1E",
    "active_tab_border": "#007ACC",
    "breadcrumb_bg": "#1F1F1F",
    "breadcrumb_fg": "#8A8A8A",
    "status_bar_bg": "#007ACC",
    "status_bar_sudo": "#8E1E1E",
    "status_bar_fg": "#FFFFFF",
    "find_bg": "#252526",
    "find_border": "#3C3C3C",
    "find_match_all": "#515C6A",
    "find_match_cur": "#F69927",
}

# Mapping ekstensi ke bahasa & lexer name
LANGUAGE_MAP = {
    ".php": ("PHP", "php"),
    ".py": ("Python", "python"),
    ".js": ("JavaScript", "javascript"),
    ".jsx": ("JavaScript React", "jsx"),
    ".ts": ("TypeScript", "typescript"),
    ".tsx": ("TypeScript React", "tsx"),
    ".json": ("JSON", "json"),
    ".html": ("HTML", "html"),
    ".htm": ("HTML", "html"),
    ".css": ("CSS", "css"),
    ".scss": ("SCSS", "scss"),
    ".less": ("LESS", "less"),
    ".sql": ("SQL", "sql"),
    ".sh": ("Shell Script", "bash"),
    ".bash": ("Shell Script", "bash"),
    ".zsh": ("Zsh Script", "zsh"),
    ".yml": ("YAML", "yaml"),
    ".yaml": ("YAML", "yaml"),
    ".xml": ("XML", "xml"),
    ".svg": ("SVG XML", "xml"),
    ".conf": ("Nginx / Config", "nginx"),
    ".ini": ("INI Config", "ini"),
    ".cfg": ("Config", "ini"),
    ".env": ("Dotenv Config", "bash"),
    ".md": ("Markdown", "markdown"),
    ".htaccess": ("Apache Config", "apacheconf"),
}


SYNTAX_TAGS = (
    "tok_keyword", "tok_decl", "tok_constant", "tok_variable",
    "tok_func", "tok_class", "tok_string", "tok_number",
    "tok_comment", "tok_operator", "tok_tag", "tok_attr"
)


class EditorTab:
    """Model data untuk satu file yang terbuka di editor."""

    def __init__(
        self,
        host: Dict[str, Any],
        remote_file_path: str,
        as_sudo: bool = False,
        on_saved_callback: Optional[Callable[[], None]] = None
    ):
        self.host = host
        self.remote_file_path = remote_file_path
        self.as_sudo = as_sudo
        self.on_saved_callback = on_saved_callback
        self.filename = os.path.basename(remote_file_path.rstrip("/")) or remote_file_path

        self.content = ""
        self.original_content = ""
        self.is_modified = False
        self.is_loaded = False
        self.is_loading = False
        self.lexer_instance = None

        self.cursor_pos = "1.0"
        self.scroll_y = 0.0

        ext = os.path.splitext(remote_file_path)[1].lower()
        if not ext and remote_file_path.endswith(".htaccess"):
            ext = ".htaccess"
        self.language_label, self.lexer_name = LANGUAGE_MAP.get(ext, ("Plain Text", "text"))


class FileEditorDialog(ctk.CTkToplevel):
    """
    Editor teks remote in-app bergaya visual VS Code modern dengan:
    - Multi-Tab Support (Membuka banyak file dalam 1 jendela editor yang sama)
    - Line Numbers (Gutter sinkron)
    - Syntax Highlighting (Pygments & Regex Fallback)
    - Quick Find & Replace (Ctrl+F)
    - Persistent Font Zoom
    - Status Bar informatif
    """

    _ACTIVE_INSTANCE: Optional["FileEditorDialog"] = None

    @classmethod
    def open_file(
        cls,
        parent: Any,
        host: Dict[str, Any],
        remote_file_path: str,
        as_sudo: bool = False,
        on_saved_callback: Optional[Callable[[], None]] = None
    ) -> "FileEditorDialog":
        """
        Buka file di jendela editor.
        Jika jendela editor sudah terbuka, tambahkan tab baru ke jendela yang sama.
        """
        if cls._ACTIVE_INSTANCE is not None:
            try:
                if cls._ACTIVE_INSTANCE.winfo_exists():
                    cls._ACTIVE_INSTANCE.add_or_switch_tab(
                        host=host,
                        remote_file_path=remote_file_path,
                        as_sudo=as_sudo,
                        on_saved_callback=on_saved_callback
                    )
                    cls._ACTIVE_INSTANCE.deiconify()
                    cls._ACTIVE_INSTANCE.lift()
                    cls._ACTIVE_INSTANCE.focus_force()
                    return cls._ACTIVE_INSTANCE
            except Exception:
                cls._ACTIVE_INSTANCE = None

        inst = cls(
            parent=parent,
            host=host,
            remote_file_path=remote_file_path,
            as_sudo=as_sudo,
            on_saved_callback=on_saved_callback
        )
        return inst

    @classmethod
    def open_directory(
        cls,
        parent: Any,
        host: Dict[str, Any],
        remote_dir_path: str,
        as_sudo: bool = False
    ) -> "FileEditorDialog":
        """
        Membuka folder remote di File Explorer jendela editor (seperti 'Open in VS Code').
        """
        clean_dir = remote_dir_path.rstrip("/") or "/"
        if cls._ACTIVE_INSTANCE is not None:
            try:
                if cls._ACTIVE_INSTANCE.winfo_exists():
                    inst = cls._ACTIVE_INSTANCE
                    inst.host = host
                    if not inst.sidebar_visible:
                        inst._toggle_explorer_sidebar()
                    inst._load_explorer_dir(clean_dir)
                    inst.deiconify()
                    inst.lift()
                    inst.focus_force()
                    return inst
            except Exception:
                cls._ACTIVE_INSTANCE = None

        # Cari berkas awal yang cocok untuk dibuka di dalam folder (jika ada)
        initial_file = None
        try:
            res = SFTPService.list_dir(host, clean_dir)
            if res.get("success"):
                items = res.get("items", [])
                files = [it for it in items if not it.get("is_dir")]
                preferred = ["index.php", "index.html", "main.py", "app.py", "README.md", "package.json", "docker-compose.yml"]
                for p in preferred:
                    match = next((f for f in files if f.get("name") == p), None)
                    if match:
                        initial_file = match.get("path")
                        break
                if not initial_file and files:
                    initial_file = files[0].get("path")
        except Exception:
            pass

        if not initial_file:
            initial_file = f"{clean_dir}/"

        inst = cls(
            parent=parent,
            host=host,
            remote_file_path=initial_file,
            as_sudo=as_sudo
        )
        inst._load_explorer_dir(clean_dir)
        return inst

    def __init__(
        self,
        parent: Any,
        host: Dict[str, Any],
        remote_file_path: str,
        as_sudo: bool = False,
        on_saved_callback: Optional[Callable[[], None]] = None
    ):
        # Jika instance sudah ada, alihkan ke instance yang ada
        if FileEditorDialog._ACTIVE_INSTANCE is not None:
            try:
                if FileEditorDialog._ACTIVE_INSTANCE.winfo_exists() and FileEditorDialog._ACTIVE_INSTANCE != self:
                    FileEditorDialog._ACTIVE_INSTANCE.add_or_switch_tab(
                        host=host,
                        remote_file_path=remote_file_path,
                        as_sudo=as_sudo,
                        on_saved_callback=on_saved_callback
                    )
                    FileEditorDialog._ACTIVE_INSTANCE.deiconify()
                    FileEditorDialog._ACTIVE_INSTANCE.lift()
                    FileEditorDialog._ACTIVE_INSTANCE.focus_force()
                    super().__init__(parent)
                    self.withdraw()
                    self.after(10, self.destroy)
                    return
            except Exception:
                pass

        super().__init__(parent)
        FileEditorDialog._ACTIVE_INSTANCE = self

        self.parent_app = parent
        self.host = host
        self.remote_file_path = remote_file_path
        self.as_sudo = as_sudo
        self._on_saved = on_saved_callback

        # Multi-Tab List & Active Tab
        self.tabs: List[EditorTab] = []
        self.active_tab: Optional[EditorTab] = None

        first_tab = EditorTab(host, remote_file_path, as_sudo, on_saved_callback)
        self.tabs.append(first_tab)
        self.active_tab = first_tab

        # Resolve DB instance
        self.db = getattr(parent, "db", None)
        if not self.db:
            self.db = getattr(getattr(parent, "app", None), "db", None)
        if not self.db:
            try:
                from database import DatabaseManager
                self.db = DatabaseManager()
            except Exception:
                self.db = None

        # Load font size from config
        default_size = 13 if sys.platform == "darwin" else 12
        saved_size = None
        if self.db:
            try:
                raw_val = self.db.get_setting("editor_font_size")
                if raw_val and raw_val.isdigit():
                    saved_size = int(raw_val)
            except Exception:
                pass
        self.font_size = saved_size if (saved_size and 8 <= saved_size <= 36) else default_size

        self.title(f"Editor - {first_tab.filename} ({host.get('label', '')})")
        self.geometry("1020x700")
        self.minsize(700, 460)
        self.configure(fg_color=VSCODE["editor_bg"])

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._search_matches: List[str] = []
        self._search_current_idx = -1
        self._highlight_timer: Optional[str] = None
        self._scroll_highlight_timer: Optional[str] = None
        self._line_count_cache = 0
        self._last_active_line: Optional[str] = None

        # Explorer sidebar state
        self._explorer_current_dir: Optional[str] = None
        self._explorer_items: List[Dict[str, Any]] = []
        self.sidebar_visible: bool = True

        self._build_ui()
        self._load_tab_content(first_tab)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_keybindings()

    def _setup_keybindings(self):
        """Mendaftarkan shortcut keyboard standar VS Code."""
        # 1. Explorer & Git Graph
        for w in (self, self.code_text):
            w.bind("<Control-b>", lambda e: self._toggle_explorer_sidebar())
            w.bind("<Command-b>", lambda e: self._toggle_explorer_sidebar())
            w.bind("<Control-Shift-G>", lambda e: self._open_git_graph())
            w.bind("<Command-Shift-G>", lambda e: self._open_git_graph())
            w.bind("<Control-Shift-g>", lambda e: self._open_git_graph())
            w.bind("<Command-Shift-g>", lambda e: self._open_git_graph())

            # 2. Quick Open (Ctrl+P / Cmd+P) & Go to Line (Ctrl+G / Cmd+G)
            w.bind("<Control-p>", self._quick_open_dialog)
            w.bind("<Command-p>", self._quick_open_dialog)
            w.bind("<Control-g>", self._goto_line_dialog)
            w.bind("<Command-g>", self._goto_line_dialog)

            # 3. File Actions (Save, Find, Reload, Close Tab)
            w.bind("<Control-s>", lambda e: self._save_content())
            w.bind("<Command-s>", lambda e: self._save_content())
            w.bind("<Control-f>", lambda e: self._toggle_find_bar())
            w.bind("<Command-f>", lambda e: self._toggle_find_bar())
            w.bind("<Control-r>", lambda e: self._reload_active_tab())
            w.bind("<Command-r>", lambda e: self._reload_active_tab())
            w.bind("<Control-w>", lambda e: self._close_active_tab())
            w.bind("<Command-w>", lambda e: self._close_active_tab())

            # 4. Font Zoom Shortcuts
            w.bind("<Control-equal>", lambda e: self._zoom_font(1))
            w.bind("<Control-plus>", lambda e: self._zoom_font(1))
            w.bind("<Control-minus>", lambda e: self._zoom_font(-1))
            w.bind("<Control-0>", lambda e: self._reset_font())
            w.bind("<Command-equal>", lambda e: self._zoom_font(1))
            w.bind("<Command-plus>", lambda e: self._zoom_font(1))
            w.bind("<Command-minus>", lambda e: self._zoom_font(-1))
            w.bind("<Command-0>", lambda e: self._reset_font())

        self.bind("<Escape>", lambda e: self._close_find_bar())

        # 5. Code Editing Shortcuts di Editor (Khusus code_text)
        # Toggle Comment: Ctrl+/ dan Cmd+/
        self.code_text.bind("<Control-slash>", self._toggle_comment)
        self.code_text.bind("<Command-slash>", self._toggle_comment)

        # Move Line Up / Down: Alt+Up / Alt+Down / Option+Up / Option+Down
        self.code_text.bind("<Alt-Up>", self._move_line_up)
        self.code_text.bind("<Alt-Down>", self._move_line_down)
        self.code_text.bind("<Alt-KeyPress-Up>", self._move_line_up)
        self.code_text.bind("<Alt-KeyPress-Down>", self._move_line_down)

        # Duplicate Line Up / Down: Shift+Alt+Up / Shift+Alt+Down
        self.code_text.bind("<Shift-Alt-Up>", self._copy_line_up)
        self.code_text.bind("<Shift-Alt-Down>", self._copy_line_down)
        self.code_text.bind("<Shift-Alt-KeyPress-Up>", self._copy_line_up)
        self.code_text.bind("<Shift-Alt-KeyPress-Down>", self._copy_line_down)

        # Delete Line: Ctrl+Shift+K / Cmd+Shift+K
        self.code_text.bind("<Control-Shift-K>", self._delete_line)
        self.code_text.bind("<Command-Shift-K>", self._delete_line)
        self.code_text.bind("<Control-Shift-k>", self._delete_line)
        self.code_text.bind("<Command-Shift-k>", self._delete_line)

        # Select Word / Add Next Occurrence: Ctrl+D / Cmd+D
        self.code_text.bind("<Control-d>", self._select_word_or_next_match)
        self.code_text.bind("<Command-d>", self._select_word_or_next_match)

        # Indent / Outdent: Ctrl+] dan Ctrl+[
        self.code_text.bind("<Control-bracketright>", lambda e: self._on_tab_press(e))
        self.code_text.bind("<Command-bracketright>", lambda e: self._on_tab_press(e))
        self.code_text.bind("<Control-bracketleft>", lambda e: self._on_shift_tab_press(e))
        self.code_text.bind("<Command-bracketleft>", lambda e: self._on_shift_tab_press(e))

    def _open_git_graph(self, target_dir: Optional[str] = None):
        """Membuka dialog Git Graph interaktif untuk folder yang sedang diakses saat ini."""
        from ui.git_graph_dialog import GitGraphDialog
        if not target_dir:
            target_dir = self._explorer_current_dir
        if not target_dir and self.active_tab and self.active_tab.remote_file_path:
            target_dir = os.path.dirname(self.active_tab.remote_file_path.rstrip("/"))
        if not target_dir:
            target_dir = "/"

        GitGraphDialog(
            parent=self,
            host=self.host,
            target_dir=target_dir,
            is_local=False
        )

    def _toggle_comment(self, event=None):
        """Toggle komentar baris gaya VS Code (Ctrl+/ atau Cmd+/)."""
        if not self.active_tab:
            return "break"

        ext = os.path.splitext(self.active_tab.remote_file_path)[1].lower()
        if ext in (".py", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".rb", ".pl", ".conf", ".ini", ".env", ".toml"):
            comment_token = "# "
        elif ext in (".sql",):
            comment_token = "-- "
        elif ext in (".html", ".xml", ".svg"):
            comment_token = "<!-- "
        else:
            comment_token = "// "

        if self.code_text.tag_ranges("sel"):
            start_idx = self.code_text.index("sel.first linestart")
            end_idx = self.code_text.index("sel.last lineend")
            start_line = int(start_idx.split(".")[0])
            end_line = int(end_idx.split(".")[0])
        else:
            cur_line = int(self.code_text.index("insert").split(".")[0])
            start_line = cur_line
            end_line = cur_line

        lines_text = [self.code_text.get(f"{l}.0", f"{l}.end") for l in range(start_line, end_line + 1)]
        non_empty_lines = [lt for lt in lines_text if lt.strip()]
        token_clean = comment_token.strip()
        all_commented = non_empty_lines and all(lt.strip().startswith(token_clean) for lt in non_empty_lines)

        for l in range(start_line, end_line + 1):
            line_str = self.code_text.get(f"{l}.0", f"{l}.end")
            if not line_str.strip():
                continue

            if all_commented:
                idx = line_str.find(token_clean)
                if idx != -1:
                    del_len = len(comment_token) if line_str[idx:idx + len(comment_token)] == comment_token else len(token_clean)
                    self.code_text.delete(f"{l}.{idx}", f"{l}.{idx + del_len}")
            else:
                indent_len = len(line_str) - len(line_str.lstrip(" \t"))
                self.code_text.insert(f"{l}.{indent_len}", comment_token)

        if self.code_text.tag_ranges("sel"):
            self.code_text.tag_add("sel", f"{start_line}.0", f"{end_line}.end")

        self._on_content_change()
        self._apply_syntax_highlighting()
        return "break"

    def _move_line_up(self, event=None):
        """Memindahkan baris kursor ke atas (Alt+Up / Option+Up)."""
        cursor = self.code_text.index("insert")
        line_no = int(cursor.split(".")[0])
        col = int(cursor.split(".")[1])
        if line_no <= 1:
            return "break"

        prev_line_text = self.code_text.get(f"{line_no - 1}.0", f"{line_no - 1}.end")
        curr_line_text = self.code_text.get(f"{line_no}.0", f"{line_no}.end")

        self.code_text.delete(f"{line_no - 1}.0", f"{line_no}.end")
        self.code_text.insert(f"{line_no - 1}.0", f"{curr_line_text}\n{prev_line_text}")

        self.code_text.mark_set("insert", f"{line_no - 1}.{col}")
        self._on_content_change()
        self._apply_syntax_highlighting()
        return "break"

    def _move_line_down(self, event=None):
        """Memindahkan baris kursor ke bawah (Alt+Down / Option+Down)."""
        cursor = self.code_text.index("insert")
        line_no = int(cursor.split(".")[0])
        col = int(cursor.split(".")[1])
        total_lines = int(self.code_text.index("end-1c").split(".")[0])
        if line_no >= total_lines:
            return "break"

        curr_line_text = self.code_text.get(f"{line_no}.0", f"{line_no}.end")
        next_line_text = self.code_text.get(f"{line_no + 1}.0", f"{line_no + 1}.end")

        self.code_text.delete(f"{line_no}.0", f"{line_no + 1}.end")
        self.code_text.insert(f"{line_no}.0", f"{next_line_text}\n{curr_line_text}")

        self.code_text.mark_set("insert", f"{line_no + 1}.{col}")
        self._on_content_change()
        self._apply_syntax_highlighting()
        return "break"

    def _copy_line_up(self, event=None):
        """Menduplikasi baris kursor ke atas (Shift+Alt+Up / Shift+Option+Up)."""
        line_no = int(self.code_text.index("insert").split(".")[0])
        curr_line_text = self.code_text.get(f"{line_no}.0", f"{line_no}.end")
        self.code_text.insert(f"{line_no}.0", f"{curr_line_text}\n")
        self._on_content_change()
        self._apply_syntax_highlighting()
        return "break"

    def _copy_line_down(self, event=None):
        """Menduplikasi baris kursor ke bawah (Shift+Alt+Down / Shift+Option+Down)."""
        line_no = int(self.code_text.index("insert").split(".")[0])
        curr_line_text = self.code_text.get(f"{line_no}.0", f"{line_no}.end")
        self.code_text.insert(f"{line_no}.end", f"\n{curr_line_text}")
        self._on_content_change()
        self._apply_syntax_highlighting()
        return "break"

    def _delete_line(self, event=None):
        """Menghapus seluruh baris kursor (Ctrl+Shift+K / Cmd+Shift+K)."""
        line_no = int(self.code_text.index("insert").split(".")[0])
        total_lines = int(self.code_text.index("end-1c").split(".")[0])
        if total_lines == 1:
            self.code_text.delete("1.0", "end")
        elif line_no < total_lines:
            self.code_text.delete(f"{line_no}.0", f"{line_no + 1}.0")
        else:
            self.code_text.delete(f"{line_no - 1}.end", f"{line_no}.end")

        self._on_content_change()
        self._apply_syntax_highlighting()
        return "break"

    def _select_word_or_next_match(self, event=None):
        """Seleksi kata saat ini atau kemunculan berikutnya (Ctrl+D / Cmd+D)."""
        if not self.code_text.tag_ranges("sel"):
            start = self.code_text.index("insert wordstart")
            end = self.code_text.index("insert wordend")
            word = self.code_text.get(start, end).strip()
            if word:
                self.code_text.tag_add("sel", start, end)
                self.code_text.mark_set("insert", end)
            return "break"

        query = self.code_text.get("sel.first", "sel.last")
        next_pos = self.code_text.search(query, "sel.last", stopindex="end", exact=True)
        if not next_pos:
            next_pos = self.code_text.search(query, "1.0", stopindex="sel.first", exact=True)

        if next_pos:
            match_end = f"{next_pos}+{len(query)}c"
            self.code_text.tag_remove("sel", "1.0", "end")
            self.code_text.tag_add("sel", next_pos, match_end)
            self.code_text.mark_set("insert", match_end)
            self.code_text.see(next_pos)

        return "break"

    def _goto_line_dialog(self, event=None):
        """Dialog Go to Line ala VS Code (Ctrl+G / Cmd+G)."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Go to Line")
        dialog.geometry("320x130")
        dialog.resizable(False, False)
        dialog.configure(fg_color="#252526")
        dialog.transient(self)
        dialog.grab_set()

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 320) // 2
        y = self.winfo_y() + 80
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

        lbl = ctk.CTkLabel(
            dialog,
            text="Go to Line:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#CCCCCC"
        )
        lbl.pack(pady=(12, 4), padx=16, anchor="w")

        entry = ctk.CTkEntry(
            dialog,
            placeholder_text="e.g. 42",
            height=30,
            fg_color="#1E1E1E",
            border_color="#3C3C3C",
            text_color="#FFFFFF"
        )
        entry.pack(pady=4, padx=16, fill="x")
        entry.focus_set()

        cur_line = self.code_text.index("insert").split(".")[0]
        entry.insert(0, cur_line)
        entry.select_range(0, "end")

        def submit():
            val = entry.get().strip()
            if val.isdigit() and int(val) > 0:
                line_idx = f"{val}.0"
                self.code_text.mark_set("insert", line_idx)
                self.code_text.see(line_idx)
                self._highlight_active_line()
                self._update_cursor_status()
                dialog.destroy()
                self.code_text.focus_set()

        entry.bind("<Return>", lambda e: submit())
        entry.bind("<Escape>", lambda e: dialog.destroy())

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=(6, 10), padx=16, fill="x")

        btn_go = ctk.CTkButton(
            btn_row,
            text="Go",
            width=70,
            height=26,
            fg_color="#0E639C",
            hover_color="#1177BB",
            command=submit
        )
        btn_go.pack(side="right", padx=(6, 0))

        btn_cancel = ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=70,
            height=26,
            fg_color="#333333",
            hover_color="#444444",
            command=dialog.destroy
        )
        btn_cancel.pack(side="right")
        return "break"

    def _quick_open_dialog(self, event=None):
        """Dialog Quick Open / Go to File ala VS Code (Ctrl+P / Cmd+P)."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Quick Open")
        dialog.geometry("500x320")
        dialog.resizable(False, False)
        dialog.configure(fg_color="#252526")
        dialog.transient(self)
        dialog.grab_set()

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 500) // 2
        y = self.winfo_y() + 60
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

        top_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        top_frame.pack(fill="x", padx=12, pady=(12, 6))

        lbl_icon = ctk.CTkLabel(top_frame, text="", image=get_icon("search", (14, 14), "#858585"))
        lbl_icon.pack(side="left", padx=(0, 6))

        search_entry = ctk.CTkEntry(
            top_frame,
            placeholder_text="Type file name to open...",
            height=32,
            fg_color="#1E1E1E",
            border_color="#007ACC",
            border_width=1,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12)
        )
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.focus_set()

        list_container = tk.Frame(dialog, bg="#1E1E1E")
        list_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        file_listbox = tk.Listbox(
            list_container,
            bg="#1E1E1E",
            fg="#CCCCCC",
            selectbackground="#094771",
            selectforeground="#FFFFFF",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI" if sys.platform == "win32" else ("SF Pro Text" if sys.platform == "darwin" else "Helvetica"), 10)
        )
        file_listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        sb = ttk.Scrollbar(list_container, orient="vertical", command=file_listbox.yview)
        file_listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        all_files = [it for it in self._explorer_items if not it.get("is_dir")]
        if not all_files:
            all_files = self._explorer_items

        def filter_items(query=""):
            file_listbox.delete(0, "end")
            q = query.lower()
            filtered = [f for f in all_files if q in f.get("name", "").lower()]
            for f in filtered:
                file_listbox.insert("end", f"  {f.get('name')}  ({f.get('path')})")
            if filtered:
                file_listbox.select_set(0)
            return filtered

        current_filtered = [filter_items()]

        def on_search_change(e=None):
            current_filtered[0] = filter_items(search_entry.get())

        search_entry.bind("<KeyRelease>", on_search_change)

        def open_selected():
            sel = file_listbox.curselection()
            if sel and current_filtered[0]:
                target_item = current_filtered[0][sel[0]]
                dialog.destroy()
                if target_item.get("is_dir"):
                    self._load_explorer_dir(target_item.get("path"))
                else:
                    self.add_or_switch_tab(self.host, target_item.get("path"), as_sudo=self.as_sudo)

        def on_key_nav(e):
            if e.keysym in ("Down", "Up"):
                sel = file_listbox.curselection()
                idx = sel[0] if sel else 0
                if e.keysym == "Down":
                    idx = min(idx + 1, file_listbox.size() - 1)
                else:
                    idx = max(idx - 1, 0)
                file_listbox.select_clear(0, "end")
                file_listbox.select_set(idx)
                file_listbox.see(idx)
                return "break"

        search_entry.bind("<Down>", on_key_nav)
        search_entry.bind("<Up>", on_key_nav)
        search_entry.bind("<Return>", lambda e: open_selected())
        file_listbox.bind("<Double-1>", lambda e: open_selected())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        return "break"

    # -------------------------------------------------------------
    # 1. UI BUILDER
    # -------------------------------------------------------------
    def _build_ui(self):
        # -------------------------------------------------------------
        # 1. TOP TAB BAR & CONTROLS (Style sama persis dengan tab File Manager)
        # -------------------------------------------------------------
        self.tab_bar = ctk.CTkFrame(self, fg_color="transparent", height=38, corner_radius=0)
        self.tab_bar.grid(row=0, column=0, sticky="ew", padx=(8, 8), pady=(4, 2))
        self.tab_bar.grid_columnconfigure(0, weight=1)
        self.tab_bar.grid_columnconfigure(1, weight=0)

        # Tab bar frame containing navigation buttons + scrollable tab items box
        self.tab_bar_frame = ctk.CTkFrame(self.tab_bar, fg_color="transparent", height=36)
        self.tab_bar_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.tab_bar_frame.grid_columnconfigure(0, weight=0)
        self.tab_bar_frame.grid_columnconfigure(1, weight=1)
        self.tab_bar_frame.grid_columnconfigure(2, weight=0)

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
            command=lambda: self.tab_items_box.scroll_left()
        )

        self.tab_items_box = HorizontalScrollableTabBar(
            self.tab_bar_frame,
            height=36,
            fg_color="transparent"
        )
        self.tab_items_box.grid(row=0, column=1, sticky="ew")

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
            command=lambda: self.tab_items_box.scroll_right()
        )

        # Right Action Buttons
        btn_group = ctk.CTkFrame(self.tab_bar, fg_color="transparent")
        btn_group.grid(row=0, column=1, pady=2, sticky="e")

        self.btn_toggle_explorer = ctk.CTkButton(
            btn_group,
            text=" Explorer",
            image=get_icon("folder-tree", (12, 12), VSCODE["editor_fg"]),
            width=80, height=28,
            corner_radius=4,
            fg_color="#0E639C" if self.sidebar_visible else "#333333",
            hover_color="#1177BB" if self.sidebar_visible else "#3E3E3E",
            text_color="#FFFFFF" if self.sidebar_visible else VSCODE["editor_fg"],
            font=ctk.CTkFont(size=11),
            command=self._toggle_explorer_sidebar
        )
        self.btn_toggle_explorer.pack(side="left", padx=2)

        self.btn_git_graph = ctk.CTkButton(
            btn_group,
            text=" Git Graph",
            image=get_icon("activity", (12, 12), VSCODE["editor_fg"]),
            width=86, height=28,
            corner_radius=4,
            fg_color="#333333",
            hover_color="#3E3E3E",
            text_color=VSCODE["editor_fg"],
            font=ctk.CTkFont(size=11),
            command=self._open_git_graph
        )
        self.btn_git_graph.pack(side="left", padx=2)

        btn_find = ctk.CTkButton(
            btn_group,
            text=" Find",
            image=get_icon("search", (12, 12), VSCODE["editor_fg"]),
            width=68, height=28,
            corner_radius=4,
            fg_color="#333333",
            hover_color="#3E3E3E",
            text_color=VSCODE["editor_fg"],
            font=ctk.CTkFont(size=11),
            command=self._toggle_find_bar
        )
        btn_find.pack(side="left", padx=2)

        self.btn_reload = ctk.CTkButton(
            btn_group,
            text=" Reload",
            image=get_icon("refresh-cw", (12, 12), VSCODE["editor_fg"]),
            width=76, height=28,
            corner_radius=4,
            fg_color="#333333",
            hover_color="#3E3E3E",
            text_color=VSCODE["editor_fg"],
            font=ctk.CTkFont(size=11),
            command=self._reload_active_tab
        )
        self.btn_reload.pack(side="left", padx=2)

        self.btn_save = ctk.CTkButton(
            btn_group,
            text=" Save",
            image=get_icon("check", (13, 13), "#FFFFFF"),
            width=80, height=28,
            corner_radius=4,
            fg_color="#0E639C",
            hover_color="#1177BB",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._save_content
        )
        self.btn_save.pack(side="left", padx=2)

        # -------------------------------------------------------------
        # 2. BREADCRUMB BAR (Path Navigation / Host Indicator)
        # -------------------------------------------------------------
        self.breadcrumb_bar = ctk.CTkFrame(self, fg_color=VSCODE["breadcrumb_bg"], height=24, corner_radius=0)
        self.breadcrumb_bar.grid(row=1, column=0, sticky="ew")

        host_label = self.host.get("label") or self.host.get("hostname") or "Remote"
        self.host_badge = ctk.CTkLabel(
            self.breadcrumb_bar,
            text=f" {host_label} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#2D2D2D",
            text_color="#4EC9B0",
            corner_radius=3,
            height=16
        )
        self.host_badge.pack(side="left", padx=(12, 6), pady=3)

        clean_path = self.remote_file_path.strip("/").replace("/", "  ›  ")
        self.lbl_breadcrumb = ctk.CTkLabel(
            self.breadcrumb_bar,
            text=f"›  {clean_path}",
            font=ctk.CTkFont(size=11),
            text_color=VSCODE["breadcrumb_fg"]
        )
        self.lbl_breadcrumb.pack(side="left", pady=3)

        # -------------------------------------------------------------
        # 3. WORKSPACE (Explorer Sidebar + Code Editor Canvas)
        # -------------------------------------------------------------
        self.main_workspace = ctk.CTkFrame(self, fg_color=VSCODE["editor_bg"], corner_radius=0)
        self.main_workspace.grid(row=2, column=0, sticky="nsew")
        self.main_workspace.grid_columnconfigure(0, weight=0)
        self.main_workspace.grid_columnconfigure(1, weight=1)
        self.main_workspace.grid_rowconfigure(0, weight=1)

        # 3a. Sidebar File Explorer
        self._build_explorer_sidebar()

        # 3b. Code Editor Canvas (Gutter + Text + Scrollbars)
        self.editor_wrapper = ctk.CTkFrame(self.main_workspace, fg_color=VSCODE["editor_bg"], corner_radius=0)
        self.editor_wrapper.grid(row=0, column=1, sticky="nsew")
        self.editor_wrapper.grid_columnconfigure(1, weight=1)
        self.editor_wrapper.grid_rowconfigure(0, weight=1)

        editor_font_family = "Menlo" if sys.platform == "darwin" else ("Consolas" if sys.platform == "win32" else "Courier")
        self.code_font = tkfont.Font(family=editor_font_family, size=self.font_size)

        # Gutter (Line Numbers)
        self.gutter = tk.Text(
            self.editor_wrapper,
            width=5,
            bg=VSCODE["gutter_bg"],
            fg=VSCODE["gutter_fg"],
            insertbackground=VSCODE["gutter_bg"],
            font=self.code_font,
            bd=0,
            padx=8,
            pady=4,
            spacing1=2,
            spacing3=2,
            wrap="none",
            takefocus=0,
            cursor="left_ptr",
            highlightthickness=0,
            selectbackground=VSCODE["gutter_bg"],
            selectforeground=VSCODE["gutter_fg"]
        )
        self.gutter.grid(row=0, column=0, sticky="ns")
        self.gutter.tag_configure("right", justify="right")
        self.gutter.tag_configure("active", foreground=VSCODE["gutter_active"])
        self.gutter.configure(state="disabled")

        gutter_line = tk.Frame(self.editor_wrapper, bg=VSCODE["gutter_border"], width=1)
        gutter_line.grid(row=0, column=0, sticky="nse")

        # Main Code Text Widget
        self.code_text = tk.Text(
            self.editor_wrapper,
            bg=VSCODE["editor_bg"],
            fg=VSCODE["editor_fg"],
            insertbackground=VSCODE["cursor_color"],
            insertwidth=2,
            selectbackground=VSCODE["selection_bg"],
            selectforeground=VSCODE["selection_fg"],
            inactiveselectbackground=VSCODE["selection_bg"],
            exportselection=False,
            font=self.code_font,
            bd=0,
            padx=12,
            pady=4,
            spacing1=2,
            spacing3=2,
            wrap="none",
            undo=True,
            maxundo=200,
            highlightthickness=0
        )
        self.code_text.grid(row=0, column=1, sticky="nsew")

        tab_pixels = self.code_font.measure("    ")
        self.code_text.configure(tabs=(tab_pixels,))

        # Vertical Scrollbar
        self.v_scrollbar = ctk.CTkScrollbar(
            self.editor_wrapper,
            orientation="vertical",
            command=self._on_v_scrollbar_drag,
            fg_color=VSCODE["editor_bg"]
        )
        self.v_scrollbar.grid(row=0, column=2, sticky="ns")

        # Horizontal Scrollbar
        self.h_scrollbar = ctk.CTkScrollbar(
            self.editor_wrapper,
            orientation="horizontal",
            command=self.code_text.xview,
            fg_color=VSCODE["editor_bg"]
        )
        self.h_scrollbar.grid(row=1, column=1, sticky="ew")

        self.code_text.configure(
            xscrollcommand=self.h_scrollbar.set,
            yscrollcommand=self._on_code_scroll
        )

        # Bindings
        self.code_text.bind("<KeyRelease>", self._on_key_release)
        self.code_text.bind("<ButtonRelease-1>", self._on_cursor_move)
        self.code_text.bind("<Tab>", self._on_tab_press)
        self.code_text.bind("<ISO_Left_Tab>", self._on_shift_tab_press)
        self.code_text.bind("<Shift-Tab>", self._on_shift_tab_press)
        self.code_text.bind("<Return>", self._on_return_press)
        self.code_text.bind("<Control-a>", self._select_all)
        self.code_text.bind("<Command-a>", self._select_all)
        self.code_text.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.code_text.bind("<Command-MouseWheel>", self._on_ctrl_mousewheel)

        self.gutter.bind("<MouseWheel>", self._on_mousewheel)
        self.gutter.bind("<Button-4>", lambda e: self.code_text.yview_scroll(-1, "units"))
        self.gutter.bind("<Button-5>", lambda e: self.code_text.yview_scroll(1, "units"))

        self._setup_editor_tags()

        # -------------------------------------------------------------
        # 4. FLOATING QUICK FIND BAR (Ctrl+F)
        # -------------------------------------------------------------
        self.find_bar = ctk.CTkFrame(
            self.editor_wrapper,
            fg_color=VSCODE["find_bg"],
            border_width=1,
            border_color=VSCODE["find_border"],
            corner_radius=4,
            height=34
        )
        self.find_bar_visible = False

        self.find_entry = ctk.CTkEntry(
            self.find_bar,
            placeholder_text="Find...",
            width=180,
            height=26,
            font=ctk.CTkFont(size=12),
            fg_color="#1E1E1E",
            border_width=1,
            border_color="#3C3C3C",
            text_color="#FFFFFF"
        )
        self.find_entry.pack(side="left", padx=(6, 4), pady=4)
        self.find_entry.bind("<KeyRelease>", lambda e: self._perform_find())
        self.find_entry.bind("<Return>", lambda e: self._find_next())
        self.find_entry.bind("<Escape>", lambda e: self._close_find_bar())

        self.lbl_find_count = ctk.CTkLabel(
            self.find_bar,
            text="No results",
            font=ctk.CTkFont(size=11),
            text_color="#858585"
        )
        self.lbl_find_count.pack(side="left", padx=4)

        btn_prev = ctk.CTkButton(
            self.find_bar,
            text="▲",
            width=24, height=24,
            corner_radius=3,
            fg_color="transparent",
            hover_color="#3E3E3E",
            text_color="#CCCCCC",
            command=self._find_prev
        )
        btn_prev.pack(side="left", padx=1)

        btn_next = ctk.CTkButton(
            self.find_bar,
            text="▼",
            width=24, height=24,
            corner_radius=3,
            fg_color="transparent",
            hover_color="#3E3E3E",
            text_color="#CCCCCC",
            command=self._find_next
        )
        btn_next.pack(side="left", padx=1)

        btn_close_find = ctk.CTkButton(
            self.find_bar,
            text="✕",
            width=24, height=24,
            corner_radius=3,
            fg_color="transparent",
            hover_color="#3E3E3E",
            text_color="#CCCCCC",
            command=self._close_find_bar
        )
        btn_close_find.pack(side="left", padx=(2, 6))

        # -------------------------------------------------------------
        # 5. BOTTOM STATUS BAR
        # -------------------------------------------------------------
        self.bottom_bar = ctk.CTkFrame(self, fg_color=VSCODE["status_bar_bg"], height=22, corner_radius=0)
        self.bottom_bar.grid(row=3, column=0, sticky="ew")

        left_status = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        left_status.pack(side="left", fill="y", padx=10)

        self.lbl_remote_host = ctk.CTkLabel(
            left_status,
            text=f" ⤿ {host_label}",
            image=get_icon("server", (11, 11), "#FFFFFF"),
            compound="left",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=VSCODE["status_bar_fg"]
        )
        self.lbl_remote_host.pack(side="left", padx=(0, 10))

        self.lbl_save_status = ctk.CTkLabel(
            left_status,
            text="Ready",
            font=ctk.CTkFont(size=11),
            text_color=VSCODE["status_bar_fg"]
        )
        self.lbl_save_status.pack(side="left")

        right_status = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        right_status.pack(side="right", fill="y", padx=12)

        self.lbl_lang = ctk.CTkLabel(
            right_status,
            text="Plain Text",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=VSCODE["status_bar_fg"]
        )
        self.lbl_lang.pack(side="right", padx=(8, 0))

        self.lbl_encoding = ctk.CTkLabel(
            right_status,
            text="UTF-8  |  LF  |  Spaces: 4  |",
            font=ctk.CTkFont(size=11),
            text_color="#E0E0E0"
        )
        self.lbl_encoding.pack(side="right", padx=(8, 0))

        font_box = ctk.CTkFrame(right_status, fg_color="transparent")
        font_box.pack(side="right", padx=(8, 4))

        btn_font_dec = ctk.CTkButton(
            font_box,
            text="-",
            width=18, height=18,
            corner_radius=3,
            fg_color="#333333",
            hover_color="#444444",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._zoom_font(-1)
        )
        btn_font_dec.pack(side="left", padx=1)

        self.lbl_font_size = ctk.CTkLabel(
            font_box,
            text=f"{self.font_size}pt",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=VSCODE["status_bar_fg"],
            width=36
        )
        self.lbl_font_size.pack(side="left", padx=2)

        btn_font_inc = ctk.CTkButton(
            font_box,
            text="+",
            width=18, height=18,
            corner_radius=3,
            fg_color="#333333",
            hover_color="#444444",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._zoom_font(1)
        )
        btn_font_inc.pack(side="left", padx=1)

        sep = ctk.CTkLabel(
            right_status,
            text="|",
            font=ctk.CTkFont(size=11),
            text_color="#A0A0A0"
        )
        sep.pack(side="right", padx=(4, 0))

        self.lbl_cursor = ctk.CTkLabel(
            right_status,
            text="Ln 1, Col 1",
            font=ctk.CTkFont(size=11),
            text_color=VSCODE["status_bar_fg"]
        )
        self.lbl_cursor.pack(side="right")

        self._render_tab_strip()
        self._sync_explorer_with_active_tab()

    # -------------------------------------------------------------
    # 1.5 FILE EXPLORER SIDEBAR
    # -------------------------------------------------------------
    def _build_explorer_sidebar(self):
        """Membangun panel File Explorer di sebelah kiri editor (VS Code style)."""
        self.sidebar_frame = ctk.CTkFrame(
            self.main_workspace,
            fg_color="#181818",
            width=230,
            corner_radius=0
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(2, weight=1)

        # Border separator vertikal di kanan sidebar
        self.sidebar_border = tk.Frame(self.sidebar_frame, bg="#2B2B2B", width=1)
        self.sidebar_border.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")

        # 1. Header Toolbar Sidebar
        header_bar = ctk.CTkFrame(self.sidebar_frame, fg_color="#1F1F1F", height=32, corner_radius=0)
        header_bar.grid(row=0, column=0, sticky="ew")

        lbl_title = ctk.CTkLabel(
            header_bar,
            text="EXPLORER",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#999999"
        )
        lbl_title.pack(side="left", padx=(10, 4), pady=5)

        btn_close_side = ctk.CTkButton(
            header_bar,
            text="",
            image=get_icon("x", (11, 11), "#888888"),
            width=22, height=22,
            corner_radius=3,
            fg_color="transparent",
            hover_color="#333333",
            command=self._toggle_explorer_sidebar
        )
        btn_close_side.pack(side="right", padx=(2, 6), pady=5)

        btn_refresh_side = ctk.CTkButton(
            header_bar,
            text="",
            image=get_icon("refresh-cw", (11, 11), "#888888"),
            width=22, height=22,
            corner_radius=3,
            fg_color="transparent",
            hover_color="#333333",
            command=self._explorer_refresh
        )
        btn_refresh_side.pack(side="right", padx=2, pady=5)

        btn_git_side = ctk.CTkButton(
            header_bar,
            text="",
            image=get_icon("activity", (11, 11), "#888888"),
            width=22, height=22,
            corner_radius=3,
            fg_color="transparent",
            hover_color="#333333",
            command=self._open_git_graph
        )
        btn_git_side.pack(side="right", padx=2, pady=5)

        btn_up_side = ctk.CTkButton(
            header_bar,
            text="",
            image=get_icon("arrow-up", (11, 11), "#888888"),
            width=22, height=22,
            corner_radius=3,
            fg_color="transparent",
            hover_color="#333333",
            command=self._explorer_nav_up
        )
        btn_up_side.pack(side="right", padx=2, pady=5)

        # 2. Folder Banner (Menampilkan folder aktif)
        folder_banner = ctk.CTkFrame(self.sidebar_frame, fg_color="#222222", height=26, corner_radius=0)
        folder_banner.grid(row=1, column=0, sticky="ew")

        self.lbl_folder_icon = ctk.CTkLabel(
            folder_banner,
            text="",
            image=get_icon("folder", (13, 13), "#D7BA7D"),
            width=16
        )
        self.lbl_folder_icon.pack(side="left", padx=(8, 4), pady=4)

        self.lbl_explorer_folder = ctk.CTkLabel(
            folder_banner,
            text="...",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#D4D4D4",
            anchor="w"
        )
        self.lbl_explorer_folder.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=4)

        # 3. Treeview Container
        tree_container = tk.Frame(self.sidebar_frame, bg="#181818")
        tree_container.grid(row=2, column=0, sticky="nsew")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        tree_style = ttk.Style()
        tree_style.configure(
            "VSCodeExplorer.Treeview",
            background="#181818",
            foreground="#CCCCCC",
            fieldbackground="#181818",
            rowheight=25,
            font=("Segoe UI" if sys.platform == "win32" else ("SF Pro Text" if sys.platform == "darwin" else "Helvetica"), 10),
            borderwidth=0
        )
        tree_style.map(
            "VSCodeExplorer.Treeview",
            background=[("selected", "#04395E" if sys.platform != "darwin" else "#264F78")],
            foreground=[("selected", "#FFFFFF")]
        )

        self.explorer_tree = ttk.Treeview(
            tree_container,
            show="tree",
            style="VSCodeExplorer.Treeview",
            selectmode="browse"
        )
        self.explorer_tree.column("#0", stretch=True, width=220)
        self.explorer_tree.grid(row=0, column=0, sticky="nsew")

        tree_vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.explorer_tree.yview)
        self.explorer_tree.configure(yscrollcommand=tree_vsb.set)
        tree_vsb.grid(row=0, column=1, sticky="ns")

        # 4. Status Bar di bagian bawah explorer
        self.lbl_explorer_status = ctk.CTkLabel(
            self.sidebar_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#777777"
        )
        self.lbl_explorer_status.grid(row=3, column=0, sticky="ew", padx=8, pady=2)

        # Cache Icon PhotoImage
        self._tree_icons = {
            "folder": get_tk_image("folder", (15, 15), "#D7BA7D"),
            "file": get_tk_image("file", (15, 15), "#C5C5C5"),
            "file_code": get_tk_image("file-code", (15, 15), "#569CD6"),
            "file_sudo": get_tk_image("shield", (15, 15), "#E51400"),
        }

        # Event bindings
        self.explorer_tree.bind("<Double-1>", self._on_explorer_item_double_click)
        self.explorer_tree.bind("<Return>", lambda e: self._on_explorer_item_double_click(e))
        self.explorer_tree.bind("<Button-2>", self._show_explorer_context_menu)
        self.explorer_tree.bind("<Button-3>", self._show_explorer_context_menu)

    def _toggle_explorer_sidebar(self):
        """Buka atau tutup panel sidebar explorer."""
        if self.sidebar_visible:
            self.sidebar_frame.grid_remove()
            self.sidebar_visible = False
            if hasattr(self, "btn_toggle_explorer"):
                self.btn_toggle_explorer.configure(
                    fg_color="#333333",
                    hover_color="#3E3E3E",
                    text_color=VSCODE["editor_fg"]
                )
        else:
            self.sidebar_frame.grid()
            self.sidebar_visible = True
            if hasattr(self, "btn_toggle_explorer"):
                self.btn_toggle_explorer.configure(
                    fg_color="#0E639C",
                    hover_color="#1177BB",
                    text_color="#FFFFFF"
                )
            self._sync_explorer_with_active_tab()

    def _sync_explorer_with_active_tab(self):
        """Sinkronkan isi file explorer dengan folder dari tab file yang sedang aktif."""
        if not self.active_tab or not self.active_tab.remote_file_path:
            return

        current_file = self.active_tab.remote_file_path
        target_dir = os.path.dirname(current_file) or "/"

        if target_dir != self._explorer_current_dir:
            self._load_explorer_dir(target_dir, highlight_file=current_file)
        else:
            self._highlight_explorer_file(current_file)

    def _load_explorer_dir(self, target_dir: str, highlight_file: Optional[str] = None):
        """Muat daftar file dan subfolder dari direktori remote secara asynchronous."""
        if not target_dir:
            target_dir = "/"

        self._explorer_current_dir = target_dir
        folder_name = os.path.basename(target_dir.rstrip("/")) or "/"
        self.lbl_explorer_folder.configure(text=folder_name)
        self.lbl_explorer_status.configure(text="Loading folder...")

        def worker():
            res = SFTPService.list_dir(self.host, target_dir)

            def on_done():
                if not self.winfo_exists():
                    return
                if res.get("success"):
                    self._populate_explorer_tree(res.get("items", []), res.get("current_path", target_dir))
                    if highlight_file:
                        self._highlight_explorer_file(highlight_file)
                    self.lbl_explorer_status.configure(text=f"{len(res.get('items', []))} items")
                else:
                    self.lbl_explorer_status.configure(text="Failed to load folder")

            if self.winfo_exists():
                self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _populate_explorer_tree(self, items: List[Dict[str, Any]], current_path: str):
        """Isi treeview explorer dengan daftar file dan folder."""
        self.explorer_tree.delete(*self.explorer_tree.get_children())
        self._explorer_items = items
        self._explorer_current_dir = current_path

        folder_name = os.path.basename(current_path.rstrip("/")) or "/"
        self.lbl_explorer_folder.configure(text=folder_name)

        code_exts = {
            ".php", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
            ".json", ".sql", ".sh", ".bash", ".yml", ".yaml", ".xml",
            ".env", ".md", ".txt", ".conf", ".ini"
        }

        for idx, item in enumerate(items):
            is_dir = item.get("is_dir", False)
            ext = item.get("ext", "").lower()
            name = item.get("name", "")

            if is_dir:
                img = self._tree_icons.get("folder")
            elif ext in code_exts:
                img = self._tree_icons.get("file_code")
            else:
                img = self._tree_icons.get("file")

            self.explorer_tree.insert(
                "",
                "end",
                iid=str(idx),
                text=f"  {name}",
                image=img,
                values=(item.get("path", ""), "dir" if is_dir else "file")
            )

    def _highlight_explorer_file(self, target_file_path: str):
        """Sorot dan scroll ke file target di treeview jika ada."""
        if not hasattr(self, "explorer_tree"):
            return
        target_norm = target_file_path.rstrip("/")
        for item_id in self.explorer_tree.get_children():
            vals = self.explorer_tree.item(item_id, "values")
            if vals and vals[0].rstrip("/") == target_norm:
                self.explorer_tree.selection_set(item_id)
                self.explorer_tree.focus(item_id)
                self.explorer_tree.see(item_id)
                break

    def _on_explorer_item_double_click(self, event=None):
        """Handler double click item pada explorer."""
        selected = self.explorer_tree.selection()
        if not selected:
            return
        item_id = selected[0]
        vals = self.explorer_tree.item(item_id, "values")
        if not vals:
            return

        item_path = vals[0]
        item_type = vals[1]

        if item_type == "dir":
            self._load_explorer_dir(item_path)
        else:
            self.add_or_switch_tab(self.host, item_path, as_sudo=self.as_sudo)

    def _show_explorer_context_menu(self, event):
        """Tampilkan context menu untuk item yang diklik kanan."""
        item_id = self.explorer_tree.identify_row(event.y)
        if item_id:
            self.explorer_tree.selection_set(item_id)
            vals = self.explorer_tree.item(item_id, "values")
            if not vals:
                return
            item_path = vals[0]
            item_type = vals[1]

            menu = tk.Menu(self, tearoff=0, bg="#252526", fg="#CCCCCC", activebackground="#094771", activeforeground="#FFFFFF")
            if item_type == "file":
                menu.add_command(label="Open in Tab", command=lambda: self.add_or_switch_tab(self.host, item_path, as_sudo=False))
                menu.add_command(label="Open as Sudo", command=lambda: self.add_or_switch_tab(self.host, item_path, as_sudo=True))
                menu.add_separator()
            elif item_type == "dir":
                menu.add_command(label="Open Directory", command=lambda: self._load_explorer_dir(item_path))
                menu.add_separator()

            def copy_path():
                self.clipboard_clear()
                self.clipboard_append(item_path)

            menu.add_command(label="Copy Remote Path", command=copy_path)
            target_git_dir = item_path if item_type == "dir" else os.path.dirname(item_path)
            menu.add_command(label="Git Graph Here", command=lambda p=target_git_dir: self._open_git_graph(p))
            menu.add_command(label="Refresh", command=self._explorer_refresh)

            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

    def _explorer_nav_up(self):
        """Naik ke parent directory."""
        if not self._explorer_current_dir or self._explorer_current_dir == "/":
            return
        parent_dir = os.path.dirname(self._explorer_current_dir.rstrip("/")) or "/"
        self._load_explorer_dir(parent_dir)

    def _explorer_refresh(self):
        """Muat ulang folder saat ini."""
        target = self._explorer_current_dir
        if not target and self.active_tab:
            target = os.path.dirname(self.active_tab.remote_file_path) or "/"
        if target:
            self._load_explorer_dir(target)

    # -------------------------------------------------------------
    # 2. MULTI-TAB MANAGEMENT & RENDERING
    # -------------------------------------------------------------
    def add_or_switch_tab(
        self,
        host: Dict[str, Any],
        remote_file_path: str,
        as_sudo: bool = False,
        on_saved_callback: Optional[Callable[[], None]] = None
    ):
        """Menambahkan file baru sebagai tab, atau beralih ke tab yang sudah terbuka."""
        # 1. Cari apakah file ini sudah terbuka di salah satu tab
        for tab in self.tabs:
            if tab.remote_file_path == remote_file_path:
                self._switch_to_tab(tab)
                return

        # 2. Jika belum ada, buat EditorTab baru
        new_tab = EditorTab(host, remote_file_path, as_sudo, on_saved_callback)
        self.tabs.append(new_tab)
        self._switch_to_tab(new_tab)
        self._load_tab_content(new_tab)

    def _render_tab_strip(self):
        """Render tab dengan desain modern seperti browser / tab File Manager:
        - Favicon icon file/shield di sebelah kiri
        - Tab card dengan sudut membulat (corner_radius=8)
        - Active tab dengan latar surface dan border elegan
        - Inactive tab dengan subtle divider dan hover effect
        - Tombol close 'x' berbentuk sirkular
        - Support horizontal mousewheel scroll & auto scroll ke tab aktif
        """
        for widget in self.tab_items_box.winfo_children():
            widget.destroy()

        active_tab_widget = None

        for idx, tab in enumerate(self.tabs):
            is_active = (tab == self.active_tab)

            # Inactive divider before tab (jika bukan tab pertama dan tab sebelumnya tidak aktif)
            if idx > 0 and not is_active and (self.tabs[idx - 1] != self.active_tab):
                divider = ctk.CTkFrame(self.tab_items_box, width=1, height=16, fg_color=COLORS["line"])
                divider.pack(side="left", padx=(0, 4), pady=(6, 0))
                self.tab_items_box.bind_child_scroll(divider)

            # Tab Card Container (Browser / File Manager Tab Style)
            tab_frame = ctk.CTkFrame(
                self.tab_items_box,
                fg_color=COLORS["surface"] if is_active else "transparent",
                corner_radius=8,
                border_width=1 if is_active else 0,
                border_color=COLORS["line"],
                cursor="hand2"
            )
            tab_frame.pack(side="left", padx=(0, 4), pady=(2, 0))
            self.tab_items_box.bind_child_scroll(tab_frame)
            if is_active:
                active_tab_widget = tab_frame

            # Inner content
            content_frame = ctk.CTkFrame(tab_frame, fg_color="transparent", cursor="hand2")
            content_frame.pack(side="top", padx=(10, 6), pady=(4, 4))
            self.tab_items_box.bind_child_scroll(content_frame)

            # 1. Favicon / File Icon
            if tab.as_sudo:
                icon_name = "shield"
                icon_color = COLORS["danger_text"]
            else:
                icon_name = "file-code"
                icon_color = COLORS["accent"] if is_active else COLORS["muted"]

            lbl_icon = ctk.CTkLabel(
                content_frame,
                text="",
                image=get_icon(icon_name, (13, 13), icon_color),
                cursor="hand2",
                width=16
            )
            lbl_icon.pack(side="left", padx=(0, 6))
            self.tab_items_box.bind_child_scroll(lbl_icon)

            # 2. Tab Title Label
            lbl_title = ctk.CTkLabel(
                content_frame,
                text=tab.filename,
                text_color=COLORS["text"] if is_active else COLORS["muted"],
                font=ctk.CTkFont(size=12, weight="bold" if is_active else "normal"),
                cursor="hand2"
            )
            lbl_title.pack(side="left", padx=(0, 6))
            self.tab_items_box.bind_child_scroll(lbl_title)

            # 3. Sudo badge (jika file dibuka sebagai sudo)
            if tab.as_sudo:
                sudo_lbl = ctk.CTkLabel(
                    content_frame,
                    text="SUDO",
                    font=ctk.CTkFont(size=8, weight="bold"),
                    fg_color=COLORS["danger_subtle"],
                    text_color=COLORS["danger_text"],
                    corner_radius=3,
                    height=14
                )
                sudo_lbl.pack(side="left", padx=(0, 6))
                self.tab_items_box.bind_child_scroll(sudo_lbl)

            # 4. Modified Dot Indicator
            if tab.is_modified:
                lbl_dot = ctk.CTkLabel(
                    content_frame,
                    text="●",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=COLORS["accent"]
                )
                lbl_dot.pack(side="left", padx=(0, 6))
                self.tab_items_box.bind_child_scroll(lbl_dot)

            # 5. Close 'x' button (Browser / File Manager style circular hover)
            btn_close = ctk.CTkButton(
                content_frame,
                text="",
                image=get_icon("x", (10, 10), COLORS["text"] if is_active else COLORS["muted"]),
                width=18,
                height=18,
                corner_radius=9,
                fg_color="transparent",
                hover_color=COLORS["danger_subtle"],
                command=lambda t=tab: self._close_tab(t)
            )
            btn_close.pack(side="left")
            self.tab_items_box.bind_child_scroll(btn_close)

            # Bind clicks to switch tab
            tab_frame.bind("<Button-1>", lambda e, t=tab: self._switch_to_tab(t))
            content_frame.bind("<Button-1>", lambda e, t=tab: self._switch_to_tab(t))
            lbl_icon.bind("<Button-1>", lambda e, t=tab: self._switch_to_tab(t))
            lbl_title.bind("<Button-1>", lambda e, t=tab: self._switch_to_tab(t))

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
                lbl_icon.bind("<Enter>", on_enter)
                lbl_icon.bind("<Leave>", on_leave)
                lbl_title.bind("<Enter>", on_enter)
                lbl_title.bind("<Leave>", on_leave)

        # Auto scroll to active tab
        if active_tab_widget:
            self.after(50, lambda: self.tab_items_box.scroll_to_child(active_tab_widget))

        # Tampilkan tombol navigasi ‹ dan › jika tab mulai banyak
        if len(self.tabs) >= 3:
            self.btn_tab_left.grid(row=0, column=0, padx=(0, 4), sticky="w")
            self.btn_tab_right.grid(row=0, column=2, padx=(4, 0), sticky="e")
        else:
            self.btn_tab_left.grid_forget()
            self.btn_tab_right.grid_forget()

    def _switch_to_tab(self, target_tab: EditorTab):
        """Beralih ke tab lain dan simpan posisi & teks tab yang ditinggalkan."""
        if not target_tab:
            return

        # 1. Simpan state tab aktif saat ini
        if self.active_tab and self.active_tab != target_tab:
            self.active_tab.content = self.code_text.get("1.0", "end-1c")
            try:
                self.active_tab.cursor_pos = self.code_text.index("insert")
                self.active_tab.scroll_y = self.code_text.yview()[0]
            except Exception:
                pass

        self.active_tab = target_tab
        self.host = target_tab.host
        self.remote_file_path = target_tab.remote_file_path
        self.as_sudo = target_tab.as_sudo
        self._on_saved = target_tab.on_saved_callback

        # 2. Perbarui Window Title, Breadcrumb & Status Bar
        host_label = self.host.get("label") or self.host.get("hostname") or "Remote"
        prefix = "Editor [sudo]" if self.as_sudo else "Editor"
        mod_prefix = "● " if target_tab.is_modified else ""
        self.title(f"{mod_prefix}{prefix} - {target_tab.filename} ({host_label})")

        self.host_badge.configure(text=f" {host_label} ")
        clean_path = target_tab.remote_file_path.strip("/").replace("/", "  ›  ")
        self.lbl_breadcrumb.configure(text=f"›  {clean_path}")
        self.lbl_lang.configure(text=target_tab.language_label)

        status_bg = VSCODE["status_bar_sudo"] if self.as_sudo else VSCODE["status_bar_bg"]
        self.bottom_bar.configure(fg_color=status_bg)
        self.btn_save.configure(
            fg_color=COLORS["danger"] if self.as_sudo else "#0E639C",
            hover_color=COLORS["danger_hover"] if self.as_sudo else "#1177BB"
        )
        remote_icon_name = "shield" if self.as_sudo else "server"
        self.lbl_remote_host.configure(
            text=f" ⤿ {host_label}",
            image=get_icon(remote_icon_name, (11, 11), "#FFFFFF")
        )

        # 3. Masukkan teks tab ke editor
        self.code_text.delete("1.0", "end")
        self.code_text.insert("1.0", target_tab.content)
        self.code_text.edit_reset()
        self.code_text.edit_modified(target_tab.is_modified)

        self._last_active_line = None
        self._line_count_cache = 0

        try:
            self.code_text.mark_set("insert", target_tab.cursor_pos)
            self.code_text.see("insert")
            self.code_text.yview_moveto(target_tab.scroll_y)
        except Exception:
            pass

        self._update_gutter_lines()
        self._highlight_active_line()
        self._apply_syntax_highlighting()
        self._render_tab_strip()
        self._sync_explorer_with_active_tab()

    def _close_active_tab(self):
        if self.active_tab:
            self._close_tab(self.active_tab)

    def _close_tab(self, tab: EditorTab):
        """Menutup satu tab tertentu dengan konfirmasi jika ada perubahan."""
        if tab == self.active_tab:
            tab.content = self.code_text.get("1.0", "end-1c")
            tab.is_modified = (tab.content != tab.original_content)

        if tab.is_modified:
            confirm = messagebox.askyesnocancel(
                "Simpan Perubahan?",
                f"File '{tab.filename}' telah dimodifikasi.\nApakah Anda ingin menyimpan perubahan sebelum menutup tab?",
                parent=self
            )
            if confirm is None:
                return  # Batal tutup tab
            if confirm:
                if tab == self.active_tab:
                    self._save_content()
                else:
                    self._save_tab_content(tab)

        if tab in self.tabs:
            idx = self.tabs.index(tab)
            self.tabs.remove(tab)

            # Jika semua tab telah ditutup, hancurkan jendela editor
            if not self.tabs:
                FileEditorDialog._ACTIVE_INSTANCE = None
                self.destroy()
                return

            # Jika tab aktif yang ditutup, alihkan ke tab sebelahnya
            if self.active_tab == tab:
                new_idx = min(idx, len(self.tabs) - 1)
                self._switch_to_tab(self.tabs[new_idx])
            else:
                self._render_tab_strip()

    # -------------------------------------------------------------
    # 3. FILE LOAD & SAVE LOGIC
    # -------------------------------------------------------------
    def _load_tab_content(self, tab: EditorTab):
        if not tab.remote_file_path or tab.remote_file_path.endswith("/"):
            tab.is_loading = False
            tab.is_loaded = True
            tab.content = f"/* Workspace: {tab.remote_file_path} */\n/* Silakan pilih file dari File Explorer di sebelah kiri untuk mulai mengedit. */\n"
            tab.original_content = tab.content
            tab.is_modified = False
            if tab == self.active_tab:
                self.btn_reload.configure(state="normal")
                self.btn_save.configure(state="normal")
                self.code_text.delete("1.0", "end")
                self.code_text.insert("1.0", tab.content)
                self.code_text.edit_reset()
                self.code_text.edit_modified(False)
                self.lbl_save_status.configure(text="Ready")
                self._update_gutter_lines()
                self._highlight_active_line()
                self._render_tab_strip()
                self._sync_explorer_with_active_tab()
            return

        tab.is_loading = True
        if tab == self.active_tab:
            self.lbl_save_status.configure(text=f"Loading '{tab.filename}' from server...")
            self.btn_save.configure(state="disabled")
            self.btn_reload.configure(state="disabled")

        def worker():
            if tab.as_sudo:
                ok, content, err = SFTPService.read_file_sudo(tab.host, tab.remote_file_path)
            else:
                ok, content, err = SFTPService.read_file_text(tab.host, tab.remote_file_path)

            def on_done():
                if not self.winfo_exists():
                    return
                tab.is_loading = False
                tab.is_loaded = True
                if ok:
                    tab.content = content
                    tab.original_content = content
                    tab.is_modified = False

                    if tab == self.active_tab:
                        self.btn_reload.configure(state="normal")
                        self.btn_save.configure(state="normal")
                        self.code_text.delete("1.0", "end")
                        self.code_text.insert("1.0", content)
                        self.code_text.edit_reset()
                        self.code_text.edit_modified(False)
                        self._last_active_line = None
                        self._line_count_cache = 0
                        self.lbl_save_status.configure(text="Ready")
                        self._update_gutter_lines()
                        self._highlight_active_line()
                        self._apply_syntax_highlighting()
                        self._render_tab_strip()
                        self._sync_explorer_with_active_tab()
                else:
                    if tab == self.active_tab:
                        self.btn_reload.configure(state="normal")
                        self.lbl_save_status.configure(text=f"Failed to load: {err}")
                    messagebox.showerror("Read Error", f"Gagal membaca file '{tab.filename}' dari server:\n\n{err}", parent=self)

            try:
                if self.winfo_exists():
                    self.after(0, on_done)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _reload_active_tab(self):
        if not self.active_tab:
            return
        self.active_tab.is_loaded = False
        self._load_tab_content(self.active_tab)

    def _save_content(self):
        """Menyimpan file pada tab aktif saat ini."""
        if not self.active_tab:
            return
        self.active_tab.content = self.code_text.get("1.0", "end-1c")
        self._save_tab_content(self.active_tab)

    def _save_tab_content(self, tab: EditorTab):
        if tab == self.active_tab:
            self.lbl_save_status.configure(text=f"Saving '{tab.filename}' to server...")
            self.btn_save.configure(state="disabled", text=" Saving...")

        def worker():
            if tab.as_sudo:
                ok, err = SFTPService.write_file_sudo(tab.host, tab.remote_file_path, tab.content)
            else:
                ok, err = SFTPService.write_file_text(tab.host, tab.remote_file_path, tab.content)

            def on_done():
                if not self.winfo_exists():
                    return
                if tab == self.active_tab:
                    self.btn_save.configure(state="normal", text=" Save")
                if ok:
                    tab.is_modified = False
                    tab.original_content = tab.content
                    if tab == self.active_tab:
                        host_label = self.host.get("label") or self.host.get("hostname") or "Remote"
                        prefix = "Editor [sudo]" if self.as_sudo else "Editor"
                        self.title(f"{prefix} - {tab.filename} ({host_label})")
                        self.lbl_save_status.configure(text="Saved successfully ✓")
                        self.code_text.edit_modified(False)

                    self._render_tab_strip()
                    if tab.on_saved_callback:
                        tab.on_saved_callback()
                else:
                    if tab == self.active_tab:
                        self.lbl_save_status.configure(text=f"Save error: {err}")
                    messagebox.showerror("Save Error", f"Gagal menyimpan file '{tab.filename}' ke server:\n\n{err}", parent=self)

            try:
                if self.winfo_exists():
                    self.after(0, on_done)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------------------------------------
    # 4. KEYBOARD & TEXT EDITING EVENTS
    # -------------------------------------------------------------
    IGNORE_NAV_KEYSYMS = {
        "Up", "Down", "Left", "Right", "Shift_L", "Shift_R",
        "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R",
        "Caps_Lock", "Escape", "Prior", "Next", "Home", "End"
    }

    def _on_key_release(self, event=None):
        # 1. Jika tombol navigasi/modifier ditekan, jangan proses edit atau re-highlighting
        if event and event.keysym in self.IGNORE_NAV_KEYSYMS:
            self._update_cursor_pos()
            self._highlight_active_line()
            return

        # 2. Cek status modifikasi file secara super ringan via edit_modified
        if self.active_tab and not self.active_tab.is_modified:
            if self.code_text.edit_modified():
                self.active_tab.is_modified = True
                host_label = self.host.get("label") or self.host.get("hostname") or "Remote"
                prefix = "Editor [sudo]" if self.as_sudo else "Editor"
                self.title(f"● {prefix} - {self.active_tab.filename} ({host_label})")
                self._render_tab_strip()

        # 3. Perbarui posisi kursor, baris gutter (jika baris bertambah/berkurang), & jadwalkan highlight
        self._update_cursor_pos()
        self._update_gutter_lines()
        self._highlight_active_line()
        self._schedule_highlight()

    def _on_cursor_move(self, event=None):
        self._update_cursor_pos()
        self._highlight_active_line()

    def _update_cursor_pos(self):
        try:
            index = self.code_text.index("insert")
            line, col = index.split(".")
            self.lbl_cursor.configure(text=f"Ln {line}, Col {int(col) + 1}")
        except Exception:
            pass

    def _select_all(self, event=None):
        self.code_text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _on_tab_press(self, event):
        if self.code_text.tag_ranges("sel"):
            start = self.code_text.index("sel.first linestart")
            end = self.code_text.index("sel.last lineend")
            start_line = int(start.split(".")[0])
            end_line = int(end.split(".")[0])
            for line_no in range(start_line, end_line + 1):
                self.code_text.insert(f"{line_no}.0", "    ")
            self.code_text.tag_add("sel", f"{start_line}.0", f"{end_line}.end")
            self._on_key_release()
            return "break"

        self.code_text.insert("insert", "    ")
        self._on_key_release()
        return "break"

    def _on_shift_tab_press(self, event):
        if self.code_text.tag_ranges("sel"):
            start = self.code_text.index("sel.first linestart")
            end = self.code_text.index("sel.last lineend")
            start_line = int(start.split(".")[0])
            end_line = int(end.split(".")[0])
        else:
            cur_line = int(self.code_text.index("insert").split(".")[0])
            start_line = cur_line
            end_line = cur_line

        for line_no in range(start_line, end_line + 1):
            line_text = self.code_text.get(f"{line_no}.0", f"{line_no}.end")
            if line_text.startswith("    "):
                self.code_text.delete(f"{line_no}.0", f"{line_no}.4")
            elif line_text.startswith("\t"):
                self.code_text.delete(f"{line_no}.0", f"{line_no}.1")
            elif line_text.startswith(" "):
                strip_len = len(line_text) - len(line_text.lstrip(" "))
                self.code_text.delete(f"{line_no}.0", f"{line_no}.{min(strip_len, 4)}")

        if self.code_text.tag_ranges("sel"):
            self.code_text.tag_add("sel", f"{start_line}.0", f"{end_line}.end")
        self._on_key_release()
        return "break"

    def _on_return_press(self, event):
        cursor_pos = self.code_text.index("insert")
        line_num = cursor_pos.split(".")[0]
        cur_line_text = self.code_text.get(f"{line_num}.0", cursor_pos)

        match = re.match(r"^(\s+)", cur_line_text)
        indent = match.group(1) if match else ""

        if cur_line_text.rstrip().endswith(("{", "[", "(")):
            extra_indent = indent + "    "
            self.code_text.insert("insert", f"\n{extra_indent}")
            self._on_key_release()
            return "break"

        self.code_text.insert("insert", f"\n{indent}")
        self._on_key_release()
        return "break"

    # -------------------------------------------------------------
    # 5. FONT SIZE ZOOM & PERSISTENCE
    # -------------------------------------------------------------
    def _zoom_font(self, delta: int):
        self._set_font_size(self.font_size + delta)
        return "break"

    def _reset_font(self):
        default_size = 13 if sys.platform == "darwin" else 12
        self._set_font_size(default_size)
        return "break"

    def _on_ctrl_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        if delta > 0:
            self._zoom_font(1)
        elif delta < 0:
            self._zoom_font(-1)
        return "break"

    def _set_font_size(self, new_size: int):
        new_size = max(9, min(36, new_size))
        if new_size == self.font_size:
            return
        self.font_size = new_size
        self.code_font.configure(size=self.font_size)
        tab_pixels = self.code_font.measure("    ")
        self.code_text.configure(tabs=(tab_pixels,))
        if hasattr(self, "lbl_font_size"):
            self.lbl_font_size.configure(text=f"{self.font_size}pt")
        self._update_gutter_lines()
        self._highlight_active_line()
        if self.db:
            try:
                self.db.set_setting("editor_font_size", str(self.font_size))
            except Exception:
                pass

    # -------------------------------------------------------------
    # 6. SCROLL & GUTTER SYNCHRONIZATION
    # -------------------------------------------------------------
    def _on_code_scroll(self, *args):
        self.v_scrollbar.set(*args)
        self.gutter.yview_moveto(args[0])
        self._schedule_scroll_highlight()

    def _on_v_scrollbar_drag(self, *args):
        self.code_text.yview(*args)
        self.gutter.yview(*args)
        self._schedule_scroll_highlight()

    def _on_mousewheel(self, event):
        units = -1 if (getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4) else 1
        self.code_text.yview_scroll(units, "units")
        self.gutter.yview_moveto(self.code_text.yview()[0])
        self._schedule_scroll_highlight()
        return "break"

    def _update_gutter_lines(self):
        try:
            line_count = int(self.code_text.index("end-1c").split(".")[0])
        except Exception:
            line_count = 1

        if line_count == self._line_count_cache:
            return

        self._line_count_cache = line_count
        gutter_width = max(4, len(str(line_count)) + 2)
        self.gutter.configure(width=gutter_width)

        lines_text = "\n".join(str(i) for i in range(1, line_count + 1))
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", lines_text, "right")
        self.gutter.configure(state="disabled")
        self.gutter.yview_moveto(self.code_text.yview()[0])
        self._highlight_active_line()

    def _highlight_active_line(self):
        try:
            cursor_pos = self.code_text.index("insert")
            curr_line = cursor_pos.split(".")[0]

            if curr_line == getattr(self, "_last_active_line", None):
                return

            last_line = getattr(self, "_last_active_line", None)
            if last_line:
                self.code_text.tag_remove("current_line", f"{last_line}.0", f"{last_line}.end+1c")
                self.gutter.tag_remove("active", f"{last_line}.0", f"{last_line}.end+1c")
            else:
                self.code_text.tag_remove("current_line", "1.0", "end")
                self.gutter.tag_remove("active", "1.0", "end")

            self._last_active_line = curr_line
            self.code_text.tag_add("current_line", f"{curr_line}.0", f"{curr_line}.end+1c")
            self.code_text.tag_lower("current_line")
            self.gutter.tag_add("active", f"{curr_line}.0", f"{curr_line}.end")
        except Exception:
            pass

    # -------------------------------------------------------------
    # 7. SYNTAX HIGHLIGHTING (Pygments Engine with Viewport Optimization)
    # -------------------------------------------------------------
    def _setup_editor_tags(self):
        self.code_text.tag_configure("current_line", background=VSCODE["current_line"])
        self.code_text.tag_lower("current_line")

        # Konfigurasi tag sel agar kontras dan berada di prioritas tertinggi
        self.code_text.tag_configure(
            "sel",
            background=VSCODE["selection_bg"],
            foreground=VSCODE["selection_fg"]
        )
        self.code_text.tag_raise("sel")

        self.code_text.tag_configure("search_match", background=VSCODE["find_match_all"])
        self.code_text.tag_configure("search_active", background=VSCODE["find_match_cur"], foreground="#000000")

        self.code_text.tag_configure("tok_keyword", foreground="#C586C0")
        self.code_text.tag_configure("tok_decl", foreground="#569CD6")
        self.code_text.tag_configure("tok_constant", foreground="#569CD6")
        self.code_text.tag_configure("tok_variable", foreground="#9CDCFE")
        self.code_text.tag_configure("tok_func", foreground="#DCDCAA")
        self.code_text.tag_configure("tok_class", foreground="#4EC9B0")
        self.code_text.tag_configure("tok_string", foreground="#CE9178")
        self.code_text.tag_configure("tok_number", foreground="#B5CEA8")
        self.code_text.tag_configure("tok_comment", foreground="#6A9955")
        self.code_text.tag_configure("tok_operator", foreground="#D4D4D4")
        self.code_text.tag_configure("tok_tag", foreground="#569CD6")
        self.code_text.tag_configure("tok_attr", foreground="#9CDCFE")

        # Pastikan sel tetap di atas semua tag token
        self.code_text.tag_raise("sel")
        self.code_text.tag_lower("current_line")

    def _schedule_highlight(self):
        if self._highlight_timer:
            self.after_cancel(self._highlight_timer)
        self._highlight_timer = self.after(250, self._apply_syntax_highlighting)

    def _schedule_scroll_highlight(self):
        if getattr(self, "_scroll_highlight_timer", None):
            self.after_cancel(self._scroll_highlight_timer)
        self._scroll_highlight_timer = self.after(100, self._apply_syntax_highlighting)

    def _get_lexer_for_tab(self, tab: EditorTab):
        if not PYGMENTS_AVAILABLE:
            return None
        lexer_name = tab.lexer_name
        try:
            if lexer_name == "php":
                from pygments.lexers.php import PhpLexer
                return PhpLexer(startinline=True)
            elif lexer_name == "text":
                return TextLexer()
            else:
                return get_lexer_by_name(lexer_name)
        except Exception:
            try:
                return get_lexer_for_filename(tab.remote_file_path)
            except Exception:
                return TextLexer()

    def _apply_syntax_highlighting(self):
        self._highlight_timer = None
        self._scroll_highlight_timer = None
        if not self.active_tab:
            return

        try:
            total_lines = int(self.code_text.index("end-1c").split(".")[0])
        except Exception:
            total_lines = 1

        if total_lines <= 0:
            return

        # Viewport optimization:
        # Jika file <= 300 baris, highlight seluruh dokumen sekaligus.
        # Jika file > 300 baris, hanya highlight baris yang berada di layar (viewport + buffer 50 baris).
        if total_lines <= 300:
            start_line = 1
            end_line = total_lines
        else:
            try:
                top = int(self.code_text.index("@0,0").split(".")[0])
                h = self.code_text.winfo_height()
                bottom = int(self.code_text.index(f"@0,{h}").split(".")[0])
                start_line = max(1, top - 50)
                end_line = min(total_lines, bottom + 50)
            except Exception:
                start_line = 1
                end_line = min(total_lines, 200)

        start_idx = f"{start_line}.0"
        end_idx = f"{end_line}.end"
        code_chunk = self.code_text.get(start_idx, end_idx)
        if not code_chunk:
            return

        # Hapus tag lama hanya pada rentang viewport yang diperbarui
        for tag in SYNTAX_TAGS:
            self.code_text.tag_remove(tag, start_idx, end_idx)

        # Lexer instance caching per tab
        if self.active_tab.lexer_instance is None:
            self.active_tab.lexer_instance = self._get_lexer_for_tab(self.active_tab)
        lexer = self.active_tab.lexer_instance

        if PYGMENTS_AVAILABLE and lexer is not None and not isinstance(lexer, TextLexer):
            try:
                tokens = lexer.get_tokens_unprocessed(code_chunk)
                for idx, ttype, val in tokens:
                    if not val.strip():
                        continue

                    tag_name = None
                    if ttype in Token.Keyword.Declaration:
                        tag_name = "tok_decl"
                    elif ttype in Token.Keyword.Constant:
                        tag_name = "tok_constant"
                    elif ttype in Token.Keyword:
                        tag_name = "tok_keyword"
                    elif ttype in Token.Name.Variable:
                        tag_name = "tok_variable"
                    elif ttype in Token.Name.Function:
                        tag_name = "tok_func"
                    elif ttype in Token.Name.Class or ttype in Token.Name.Builtin:
                        tag_name = "tok_class"
                    elif ttype in Token.String:
                        tag_name = "tok_string"
                    elif ttype in Token.Number:
                        tag_name = "tok_number"
                    elif ttype in Token.Comment:
                        tag_name = "tok_comment"
                    elif ttype in Token.Name.Tag:
                        tag_name = "tok_tag"
                    elif ttype in Token.Name.Attribute:
                        tag_name = "tok_attr"
                    elif ttype in Token.Operator.Word:
                        tag_name = "tok_keyword"

                    if tag_name:
                        tok_start = f"{start_line}.0+{idx}c"
                        tok_end = f"{start_line}.0+{idx + len(val)}c"
                        self.code_text.tag_add(tag_name, tok_start, tok_end)
            except Exception:
                self._apply_fallback_highlighting(code_chunk, start_line)
        else:
            self._apply_fallback_highlighting(code_chunk, start_line)

        self.code_text.tag_raise("sel")
        self.code_text.tag_lower("current_line")

    def _apply_fallback_highlighting(self, code: str, start_line: int = 1):
        patterns = [
            ("tok_comment", r"(//[^\n]*|#[^\n]*|/\*[\s\S]*?\*/)"),
            ("tok_string", r'("[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')'),
            ("tok_variable", r"\$[a-zA-Z0-9_]+"),
            ("tok_keyword", r"\b(if|else|elseif|while|for|foreach|return|class|function|new|public|private|protected|static|use|namespace|echo|die|exit|isset|empty|try|catch)\b"),
            ("tok_constant", r"\b(true|false|null|TRUE|FALSE|NULL)\b"),
            ("tok_number", r"\b\d+(\.\d+)?\b"),
            ("tok_operator", r"[=+\-*/%&|!<>:]"),
        ]
        for tag, pattern in patterns:
            for m in re.finditer(pattern, code):
                start = f"{start_line}.0+{m.start()}c"
                end = f"{start_line}.0+{m.end()}c"
                self.code_text.tag_add(tag, start, end)

        self.code_text.tag_raise("sel")
        self.code_text.tag_lower("current_line")

    # -------------------------------------------------------------
    # 8. QUICK FIND / SEARCH BAR
    # -------------------------------------------------------------
    def _toggle_find_bar(self):
        if self.find_bar_visible:
            self._close_find_bar()
        else:
            self._open_find_bar()

    def _open_find_bar(self):
        self.find_bar.place(relx=1.0, y=8, x=-24, anchor="ne")
        self.find_bar.lift()
        self.find_bar_visible = True
        self.find_entry.focus_set()
        if self.code_text.tag_ranges("sel"):
            selected = self.code_text.get("sel.first", "sel.last")
            if selected and "\n" not in selected:
                self.find_entry.delete(0, "end")
                self.find_entry.insert(0, selected)
        self._perform_find()

    def _close_find_bar(self):
        if self.find_bar_visible:
            self.find_bar.place_forget()
            self.find_bar_visible = False
            self.code_text.tag_remove("search_match", "1.0", "end")
            self.code_text.tag_remove("search_active", "1.0", "end")
            self.code_text.focus_set()

    def _perform_find(self):
        query = self.find_entry.get()
        self.code_text.tag_remove("search_match", "1.0", "end")
        self.code_text.tag_remove("search_active", "1.0", "end")
        self._search_matches.clear()
        self._search_current_idx = -1

        if not query:
            self.lbl_find_count.configure(text="No results", text_color="#858585")
            return

        start = "1.0"
        max_matches = 500
        while True:
            pos = self.code_text.search(query, start, stopindex="end", nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self._search_matches.append(pos)
            self.code_text.tag_add("search_match", pos, end)
            start = end
            if len(self._search_matches) >= max_matches:
                break

        total = len(self._search_matches)
        if total == 0:
            self.lbl_find_count.configure(text="No results", text_color="#F48771")
        else:
            self._search_current_idx = 0
            self._activate_search_match()

    def _activate_search_match(self):
        total = len(self._search_matches)
        if total == 0 or self._search_current_idx < 0:
            return

        pos = self._search_matches[self._search_current_idx]
        query = self.find_entry.get()
        end = f"{pos}+{len(query)}c"

        self.code_text.tag_remove("search_active", "1.0", "end")
        self.code_text.tag_add("search_active", pos, end)
        self.code_text.see(pos)
        suffix = "+" if total >= 500 else ""
        self.lbl_find_count.configure(
            text=f"{self._search_current_idx + 1} of {total}{suffix}",
            text_color="#FFFFFF"
        )

    def _find_next(self):
        total = len(self._search_matches)
        if total == 0:
            return
        self._search_current_idx = (self._search_current_idx + 1) % total
        self._activate_search_match()

    def _find_prev(self):
        total = len(self._search_matches)
        if total == 0:
            return
        self._search_current_idx = (self._search_current_idx - 1 + total) % total
        self._activate_search_match()

    # -------------------------------------------------------------
    # 9. WINDOW CLOSE HANDLER
    # -------------------------------------------------------------
    def _on_close(self):
        if self.active_tab:
            self.active_tab.content = self.code_text.get("1.0", "end-1c")
            self.active_tab.is_modified = (self.active_tab.content != self.active_tab.original_content)

        modified_tabs = [t for t in self.tabs if t.is_modified]
        if modified_tabs:
            files_str = "\n".join(f"• {t.filename}" for t in modified_tabs[:5])
            if len(modified_tabs) > 5:
                files_str += f"\n... dan {len(modified_tabs) - 5} file lainnya"

            confirm = messagebox.askyesnocancel(
                "Simpan Perubahan?",
                f"Ada {len(modified_tabs)} file dengan perubahan yang belum disimpan:\n\n{files_str}\n\nApakah Anda ingin menyimpan semua perubahan sebelum keluar?",
                parent=self
            )
            if confirm is None:
                return  # Batal tutup jendela
            if confirm:
                for t in modified_tabs:
                    if t == self.active_tab:
                        self._save_content()
                    else:
                        self._save_tab_content(t)
                FileEditorDialog._ACTIVE_INSTANCE = None
                self.destroy()
                return

        FileEditorDialog._ACTIVE_INSTANCE = None
        self.destroy()
