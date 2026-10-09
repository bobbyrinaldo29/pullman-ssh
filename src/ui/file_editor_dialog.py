import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

from theme import COLORS, get_color
from icons import get_icon
from sftp_service import SFTPService


class FileEditorDialog(ctk.CTkToplevel):
    """Editor teks remote in-app untuk mengedit konfigurasi/file teks langsung di server."""

    def __init__(
        self,
        parent: Any,
        host: Dict[str, Any],
        remote_file_path: str,
        as_sudo: bool = False,
        on_saved_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.host = host
        self.remote_file_path = remote_file_path
        self.as_sudo = as_sudo
        self._on_saved = on_saved_callback
        self.is_modified = False
        self._original_content = ""

        filename = remote_file_path.split("/")[-1]
        prefix = "Editor [sudo]" if as_sudo else "Editor"
        self.title(f"{prefix} - {filename} ({host.get('label', '')})")
        self.geometry("860x600")
        self.minsize(640, 420)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_ui()
        self._load_file_content()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-s>", lambda e: self._save_content())
        self.bind("<Command-s>", lambda e: self._save_content())

    def _build_ui(self):
        # 1. Header Toolbar
        top_bar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=48, corner_radius=0, border_width=1, border_color=COLORS["line"])
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_columnconfigure(1, weight=1)

        icon_name = "shield" if self.as_sudo else "file-code"
        icon_color = COLORS["danger_text"] if self.as_sudo else COLORS["accent_text"]
        icon_lbl = ctk.CTkLabel(top_bar, text="", image=get_icon(icon_name, (18, 18), icon_color))
        icon_lbl.grid(row=0, column=0, padx=(16, 8), pady=8)

        info_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="w", pady=4)

        title_box = ctk.CTkFrame(info_frame, fg_color="transparent")
        title_box.pack(anchor="w")

        self.lbl_path = ctk.CTkLabel(
            title_box,
            text=self.remote_file_path,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text"]
        )
        self.lbl_path.pack(side="left", anchor="w")

        if self.as_sudo:
            sudo_badge = ctk.CTkLabel(
                title_box,
                text=" SUDO MODE ",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=COLORS["danger_subtle"],
                text_color=COLORS["danger_text"],
                corner_radius=4,
                height=18
            )
            sudo_badge.pack(side="left", padx=(8, 0))

        self.lbl_status = ctk.CTkLabel(
            info_frame,
            text="Loading file...",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["muted"]
        )
        self.lbl_status.pack(anchor="w")

        btn_group = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_group.grid(row=0, column=2, padx=14, pady=8)

        self.btn_save = ctk.CTkButton(
            btn_group,
            text=" Save (Ctrl+S)",
            image=get_icon("check", (13, 13), "#FFFFFF"),
            width=110, height=30,
            corner_radius=6,
            fg_color=COLORS["danger_hover"] if self.as_sudo else COLORS["accent"],
            hover_color=COLORS["danger_border"] if self.as_sudo else COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._save_content
        )
        self.btn_save.pack(side="left", padx=4)

        self.btn_reload = ctk.CTkButton(
            btn_group,
            text=" Reload",
            image=get_icon("refresh-cw", (12, 12), COLORS["text"]),
            width=80, height=30,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._load_file_content
        )
        self.btn_reload.pack(side="left", padx=4)

        # 2. Text Editor Area
        editor_container = ctk.CTkFrame(self, fg_color=COLORS["input_bg"], corner_radius=0)
        editor_container.grid(row=1, column=0, sticky="nsew")
        editor_container.grid_columnconfigure(0, weight=1)
        editor_container.grid_rowconfigure(0, weight=1)

        self.txt_editor = ctk.CTkTextbox(
            editor_container,
            font=ctk.CTkFont(family="Consolas" if tk.TkVersion >= 8.6 else "Courier", size=12),
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            corner_radius=0,
            border_width=0,
            wrap="none",
            undo=True
        )
        self.txt_editor.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.txt_editor.bind("<<Modified>>", self._on_text_modified)
        self.txt_editor.bind("<KeyRelease>", self._update_cursor_info)

        # 3. Bottom Status Bar
        bottom_bar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=24, corner_radius=0, border_width=1, border_color=COLORS["line"])
        bottom_bar.grid(row=2, column=0, sticky="ew")

        self.lbl_cursor = ctk.CTkLabel(
            bottom_bar,
            text="Line 1, Col 1 | UTF-8",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["subtle"]
        )
        self.lbl_cursor.pack(side="left", padx=14, pady=2)

    def _load_file_content(self):
        self.lbl_status.configure(text="Loading content from server...", text_color=COLORS["muted"])
        self.btn_save.configure(state="disabled")
        self.btn_reload.configure(state="disabled")

        def worker():
            if self.as_sudo:
                ok, content, err = SFTPService.read_file_sudo(self.host, self.remote_file_path)
            else:
                ok, content, err = SFTPService.read_file_text(self.host, self.remote_file_path)

            def on_done():
                self.btn_reload.configure(state="normal")
                if ok:
                    self._original_content = content
                    self.txt_editor.delete("1.0", "end")
                    self.txt_editor.insert("1.0", content)
                    self.txt_editor.edit_reset()
                    self.is_modified = False
                    status_suffix = " • SUDO" if self.as_sudo else ""
                    self.lbl_status.configure(text=f"Ready • UTF-8{status_suffix}", text_color=COLORS["success_text"])
                    self.btn_save.configure(state="normal")
                else:
                    self.lbl_status.configure(text=f"Failed to load: {err}", text_color=COLORS["danger"])
                    messagebox.showerror("Read Error", f"Gagal membaca file dari server:\n\n{err}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_text_modified(self, event=None):
        if self.txt_editor.edit_modified():
            self.is_modified = True
            filename = self.remote_file_path.split("/")[-1]
            prefix = "Editor [sudo]" if self.as_sudo else "Editor"
            self.title(f"{prefix} - {filename} * (Modified)")
            self.lbl_status.configure(text="Modified *", text_color=COLORS["warning_text"])
            self.txt_editor.edit_modified(False)

    def _update_cursor_info(self, event=None):
        try:
            index = self.txt_editor.index("insert")
            line, col = index.split(".")
            self.lbl_cursor.configure(text=f"Line {line}, Col {int(col)+1} | UTF-8")
        except Exception:
            pass

    def _save_content(self):
        content = self.txt_editor.get("1.0", "end-1c")
        self.lbl_status.configure(text="Saving to server...", text_color=COLORS["accent_text"])
        self.btn_save.configure(state="disabled", text=" Saving...")

        def worker():
            if self.as_sudo:
                ok, err = SFTPService.write_file_sudo(self.host, self.remote_file_path, content)
            else:
                ok, err = SFTPService.write_file_text(self.host, self.remote_file_path, content)

            def on_done():
                self.btn_save.configure(state="normal", text=" Save (Ctrl+S)")
                if ok:
                    self.is_modified = False
                    filename = self.remote_file_path.split("/")[-1]
                    prefix = "Editor [sudo]" if self.as_sudo else "Editor"
                    self.title(f"{prefix} - {filename} ({self.host.get('label', '')})")
                    self.lbl_status.configure(text="Saved successfully ✓", text_color=COLORS["success_text"])
                    if self._on_saved:
                        self._on_saved()
                else:
                    self.lbl_status.configure(text=f"Save error: {err}", text_color=COLORS["danger"])
                    messagebox.showerror("Save Error", f"Gagal menyimpan file ke server:\n\n{err}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self):
        if self.is_modified:
            confirm = messagebox.askyesnocancel(
                "Simpan Perubahan?",
                "File telah dimodifikasi. Apakah Anda ingin menyimpan perubahan sebelum keluar?",
                parent=self
            )
            if confirm is None:
                return  # Cancel
            if confirm:
                self._save_content()
                self.destroy()
                return
        self.destroy()
