import os
from pathlib import Path
import tempfile
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from theme import COLORS
from icons import get_icon
from editor_service import EditorInfo, EditorService


class FileEditorSettingsDialog(ctk.CTkToplevel):
    """
    Dialog modern untuk konfigurasi teks editor di File Manager.
    Memungkinkan pengguna memilih editor default (Built-in, VS Code, Notepad++, Sublime, dll.),
    menentukan executable kustom, dan mengatur perilaku auto-sync remote.
    """

    def __init__(
        self,
        parent: Any,
        db: Optional[Any] = None,
        on_saved: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.parent_app = parent
        self.db = db
        self.on_saved = on_saved

        self.title("Pengaturan Teks Editor - File Manager")
        self.geometry("640x720")
        self.minsize(560, 600)
        self.configure(fg_color=COLORS["window"])

        # Modal behavior
        self.transient(parent)
        self.grab_set()

        # Load settings
        self.settings = EditorService.get_settings(self.db)
        self.selected_editor_id = ctk.StringVar(value=self.settings.get("default_editor", "builtin"))
        self.custom_path_var = ctk.StringVar(value=self.settings.get("custom_path", ""))
        self.auto_sync_var = ctk.BooleanVar(value=self.settings.get("auto_sync", True))
        self.show_notif_var = ctk.BooleanVar(value=self.settings.get("show_notifications", True))

        # Detect editors
        self.editors: List[EditorInfo] = EditorService.get_detected_editors(
            custom_path=self.custom_path_var.get(),
            force_refresh=True
        )

        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        try:
            pw = self.parent_app.winfo_width()
            ph = self.parent_app.winfo_height()
            px = self.parent_app.winfo_rootx()
            py = self.parent_app.winfo_rooty()

            w = 640
            h = 720
            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------
        # 1. Header Box
        # ---------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, border_width=1, border_color=COLORS["line"])
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        icon_lbl = ctk.CTkLabel(
            header,
            text="",
            image=get_icon("settings", (24, 24), COLORS["accent"]),
            width=36
        )
        icon_lbl.grid(row=0, column=0, rowspan=2, padx=(20, 12), pady=16)

        title_lbl = ctk.CTkLabel(
            header,
            text="Pengaturan Teks Editor",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_lbl.grid(row=0, column=1, sticky="w", pady=(14, 2))

        sub_lbl = ctk.CTkLabel(
            header,
            text="Pilih aplikasi untuk membuka dan mengedit file di File Manager (Remote & Lokal).",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12)
        )
        sub_lbl.grid(row=1, column=1, sticky="w", pady=(0, 14))

        # ---------------------------------------------------------
        # 2. Main Scrollable Container
        # ---------------------------------------------------------
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        scroll.grid_columnconfigure(0, weight=1)

        # SECTION A: Editor Selection
        sec_a_lbl = ctk.CTkLabel(
            scroll,
            text="PILIH DEFAULT EDITOR",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11, weight="bold")
        )
        sec_a_lbl.pack(anchor="w", pady=(0, 8))

        self.editor_cards_container = ctk.CTkFrame(scroll, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        self.editor_cards_container.pack(fill="x", pady=(0, 16))
        self.editor_cards_container.grid_columnconfigure(0, weight=1)

        # Render list of editors
        self.card_widgets = []
        for idx, editor in enumerate(self.editors):
            self._render_editor_row(self.editor_cards_container, editor, idx)

        # Custom Path Input (Shown when custom editor is active)
        self.custom_path_frame = ctk.CTkFrame(scroll, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        self.custom_path_frame.pack(fill="x", pady=(0, 16))
        self.custom_path_frame.grid_columnconfigure(1, weight=1)

        lbl_custom_title = ctk.CTkLabel(
            self.custom_path_frame,
            text="Path File Executable Editor Kustom:",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_custom_title.grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(12, 6))

        self.ent_custom_path = ctk.CTkEntry(
            self.custom_path_frame,
            textvariable=self.custom_path_var,
            placeholder_text=r"Contoh: C:\Program Files\MyEditor\editor.exe",
            height=32,
            corner_radius=6,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["line"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=11)
        )
        self.ent_custom_path.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(14, 8), pady=(0, 12))
        self.ent_custom_path.bind("<KeyRelease>", lambda e: self._on_custom_path_changed())

        btn_browse = ctk.CTkButton(
            self.custom_path_frame,
            text=" Browse...",
            image=get_icon("folder-input", (13, 13), COLORS["text"]),
            compound="left",
            width=90,
            height=32,
            corner_radius=6,
            fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=11),
            command=self._browse_custom_path
        )
        btn_browse.grid(row=1, column=2, padx=(0, 14), pady=(0, 12))

        # SECTION B: Auto-Sync & Preferences
        sec_b_lbl = ctk.CTkLabel(
            scroll,
            text="PENGATURAN SINKRONISASI FILE REMOTE",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11, weight="bold")
        )
        sec_b_lbl.pack(anchor="w", pady=(0, 8))

        sync_card = ctk.CTkFrame(scroll, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        sync_card.pack(fill="x", pady=(0, 16))
        sync_card.grid_columnconfigure(0, weight=1)

        # 1. Auto Sync Switch
        sync_row = ctk.CTkFrame(sync_card, fg_color="transparent")
        sync_row.pack(fill="x", padx=14, pady=(12, 8))
        sync_row.grid_columnconfigure(0, weight=1)

        sync_title_box = ctk.CTkFrame(sync_row, fg_color="transparent")
        sync_title_box.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            sync_title_box,
            text="Auto-Sync Saat Disimpan (Auto-upload on Save)",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            sync_title_box,
            text="Otomatis mengunggah perubahan ke server remote setiap kali Anda menekan Ctrl+S di editor eksternal.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w")

        switch_sync = ctk.CTkSwitch(
            sync_row,
            text="",
            variable=self.auto_sync_var,
            progress_color=COLORS["accent"],
            width=46
        )
        switch_sync.grid(row=0, column=1, sticky="e")

        # Divider
        ctk.CTkFrame(sync_card, height=1, fg_color=COLORS["line_subtle"]).pack(fill="x", padx=14, pady=4)

        # 2. Notification Switch
        notif_row = ctk.CTkFrame(sync_card, fg_color="transparent")
        notif_row.pack(fill="x", padx=14, pady=(8, 12))
        notif_row.grid_columnconfigure(0, weight=1)

        notif_title_box = ctk.CTkFrame(notif_row, fg_color="transparent")
        notif_title_box.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            notif_title_box,
            text="Notifikasi Berhasil Sinkronisasi",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            notif_title_box,
            text="Tampilkan pemberitahuan saat file remote berhasil tersinkronkan kembali ke server.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w")

        switch_notif = ctk.CTkSwitch(
            notif_row,
            text="",
            variable=self.show_notif_var,
            progress_color=COLORS["accent"],
            width=46
        )
        switch_notif.grid(row=0, column=1, sticky="e")

        # Update visibility of custom path
        self._update_custom_frame_visibility()

        # ---------------------------------------------------------
        # 3. Bottom Action Bar
        # ---------------------------------------------------------
        bottom_bar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=52, corner_radius=0, border_width=1, border_color=COLORS["line"])
        bottom_bar.grid(row=2, column=0, sticky="ew")

        # Test Editor button on left
        btn_test = ctk.CTkButton(
            bottom_bar,
            text=" Test Buka Editor",
            image=get_icon("play", (12, 12), COLORS["text"]),
            compound="left",
            height=32,
            corner_radius=8,
            fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12),
            command=self._test_open_editor
        )
        btn_test.pack(side="left", padx=16, pady=10)

        # Save and Cancel buttons on right
        btn_save = ctk.CTkButton(
            bottom_bar,
            text=" Simpan Pengaturan",
            image=get_icon("check", (13, 13), "#FFFFFF"),
            compound="left",
            height=32,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save_and_close
        )
        btn_save.pack(side="right", padx=(6, 16), pady=10)

        btn_cancel = ctk.CTkButton(
            bottom_bar,
            text="Batal",
            height=32,
            corner_radius=8,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=12),
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(0, 6), pady=10)

    def _render_editor_row(self, parent: ctk.CTkFrame, editor: EditorInfo, index: int):
        """Render satu kartu baris opsi editor."""
        if index > 0:
            divider = ctk.CTkFrame(parent, height=1, fg_color=COLORS["line_subtle"])
            divider.pack(fill="x", padx=12)

        row = ctk.CTkFrame(parent, fg_color="transparent", cursor="hand2")
        row.pack(fill="x", padx=12, pady=8)
        row.grid_columnconfigure(1, weight=1)

        # Radio button
        rb = ctk.CTkRadioButton(
            row,
            text="",
            value=editor.id,
            variable=self.selected_editor_id,
            width=24,
            command=self._on_editor_selected
        )
        rb.grid(row=0, column=0, padx=(4, 8), sticky="w")

        # Icon
        icon_color = COLORS["accent"] if editor.id == "builtin" else COLORS["text"]
        lbl_icon = ctk.CTkLabel(
            row,
            text="",
            image=get_icon(editor.icon_name, (16, 16), icon_color),
            width=20
        )
        lbl_icon.grid(row=0, column=1, padx=(0, 8), sticky="w")

        # Details Box (Title & Description)
        detail_box = ctk.CTkFrame(row, fg_color="transparent")
        detail_box.grid(row=0, column=2, sticky="w")

        lbl_name = ctk.CTkLabel(
            detail_box,
            text=editor.name,
            text_color=COLORS["text"] if editor.is_available else COLORS["muted"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_name.pack(anchor="w")

        desc_text = editor.description
        lbl_desc = ctk.CTkLabel(
            detail_box,
            text=desc_text,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=10)
        )
        lbl_desc.pack(anchor="w")

        # Status Badge
        badge_box = ctk.CTkFrame(row, fg_color="transparent")
        badge_box.grid(row=0, column=3, padx=(8, 4), sticky="e")

        if editor.id == "builtin":
            badge = ctk.CTkLabel(
                badge_box,
                text="Bawaan",
                fg_color=COLORS["accent_subtle"],
                text_color=COLORS["accent_text"],
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold"),
                width=62,
                height=22
            )
            badge.pack(side="right")
        elif editor.is_available:
            badge = ctk.CTkLabel(
                badge_box,
                text="✓ Terpasang",
                fg_color=COLORS["success_subtle"],
                text_color=COLORS["success_text"],
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold"),
                width=76,
                height=22
            )
            badge.pack(side="right")
        else:
            badge = ctk.CTkLabel(
                badge_box,
                text="Tidak Ada",
                fg_color=COLORS["surface_hover"],
                text_color=COLORS["subtle"],
                corner_radius=6,
                font=ctk.CTkFont(size=10),
                width=66,
                height=22
            )
            badge.pack(side="right")

        # Click row to select
        def on_click(e):
            self.selected_editor_id.set(editor.id)
            self._on_editor_selected()

        row.bind("<Button-1>", on_click)
        lbl_icon.bind("<Button-1>", on_click)
        detail_box.bind("<Button-1>", on_click)
        lbl_name.bind("<Button-1>", on_click)
        lbl_desc.bind("<Button-1>", on_click)

    def _on_editor_selected(self):
        self._update_custom_frame_visibility()

    def _update_custom_frame_visibility(self):
        if self.selected_editor_id.get() == "custom":
            self.custom_path_frame.pack(fill="x", pady=(0, 16))
        else:
            # We can keep it visible or dim it
            pass

    def _browse_custom_path(self):
        initial_dir = r"C:\Program Files" if sys.platform == "win32" else "/Applications"
        filetypes = [("Executable Files", "*.exe;*.cmd;*.bat;*"), ("All Files", "*.*")] if sys.platform == "win32" else [("All Files", "*.*")]
        chosen = filedialog.askopenfilename(
            parent=self,
            title="Pilih Executable Teks Editor",
            initialdir=initial_dir,
            filetypes=filetypes
        )
        if chosen:
            self.custom_path_var.set(chosen)
            self.selected_editor_id.set("custom")
            self._on_custom_path_changed()

    def _on_custom_path_changed(self):
        # Refresh custom editor availability in list
        custom_path = self.custom_path_var.get().strip()
        EditorService._update_custom_editor(self.editors, custom_path)

    def _test_open_editor(self):
        """Membuat file teks sementara dan menguji peluncuran editor yang dipilih."""
        selected_id = self.selected_editor_id.get()
        custom_path = self.custom_path_var.get().strip()

        # Update custom path
        EditorService._update_custom_editor(self.editors, custom_path)
        editor = next((e for e in self.editors if e.id == selected_id), None)
        if not editor:
            messagebox.showwarning("Peringatan", "Pilih salah satu editor terlebih dahulu.", parent=self)
            return

        if not editor.is_available and editor.id != "builtin":
            messagebox.showerror(
                "Editor Tidak Ditemukan",
                f"Editor '{editor.name}' belum terpasang atau file executable tidak valid di sistem Anda.",
                parent=self
            )
            return

        # Buat temporary sample file
        try:
            temp_dir = tempfile.gettempdir()
            test_file = os.path.join(temp_dir, "pullman_test_file.txt")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("Halo dari DO.MBA Pull Manager!\n\nTeks editor Anda berhasil terhubung dengan File Manager Pullman.\nAnda dapat menutup file ini.")

            ok, err = EditorService.launch_external_editor(editor, test_file) if editor.id != "builtin" else (True, None)
            if editor.id == "builtin":
                from ui.file_editor_dialog import FileEditorDialog
                FileEditorDialog.open_file(self, host=None, remote_file_path=test_file)

            if ok:
                messagebox.showinfo("Sukses", f"Berhasil membuka test file dengan {editor.name}!", parent=self)
            else:
                messagebox.showerror("Gagal Membuka", f"Gagal menjalankan {editor.name}:\n\n{err}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Terjadi kesalahan saat menguji editor:\n{e}", parent=self)

    def _save_and_close(self):
        selected_id = self.selected_editor_id.get()
        custom_path = self.custom_path_var.get().strip()
        auto_sync = self.auto_sync_var.get()
        show_notif = self.show_notif_var.get()

        if selected_id == "custom":
            if not custom_path or not os.path.isfile(custom_path):
                messagebox.showerror("Path Tidak Valid", "Silakan masukkan lokasi file executable kustom yang valid.", parent=self)
                return

        EditorService.save_settings(
            db=self.db,
            default_editor=selected_id,
            custom_path=custom_path,
            auto_sync=auto_sync,
            show_notifications=show_notif
        )

        if self.on_saved:
            try:
                self.on_saved()
            except Exception:
                pass

        self.destroy()
