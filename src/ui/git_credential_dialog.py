import customtkinter as ctk
from tkinter import messagebox
from typing import Any
from theme import COLORS
from icons import get_icon


class GitCredentialDialog(ctk.CTkToplevel):
    """Editor untuk satu credential Git global aplikasi."""

    def __init__(self, parent: ctk.CTk, db_manager: Any):
        super().__init__(parent, fg_color=COLORS["window"])
        self.db = db_manager

        self.title("Git Credential")
        self.geometry("470x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self._load_credential()

    def _setup_ui(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(frame, text="Git Credential", text_color=COLORS["text"], font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            frame,
            text="Dipakai untuk semua koneksi SSH yang menjalankan Git Pull. "
                 "Token akan disimpan terenkripsi di perangkat ini.",
            text_color=COLORS["muted"], justify="left", wraplength=410,
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=(5, 20))

        ctk.CTkLabel(frame, text="Git username / email", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.username_entry = ctk.CTkEntry(frame, placeholder_text="name@example.com atau username")
        self.username_entry.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(frame, text="Personal access token / password", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.token_entry = ctk.CTkEntry(frame, placeholder_text="Masukkan token Git", show="•")
        self.token_entry.pack(fill="x", pady=(4, 10))

        self.status_label = ctk.CTkLabel(frame, text="", text_color=COLORS["danger"], font=ctk.CTkFont(size=11))
        self.status_label.pack(anchor="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x", side="bottom", pady=(18, 0))
        ctk.CTkButton(
            actions, text=" Hapus", image=get_icon("trash", (13, 13), COLORS["danger_text"]), compound="left",
            width=88, fg_color=COLORS["danger_subtle"], border_width=1, border_color=COLORS["danger_border"],
            text_color=COLORS["danger_text"], hover_color=COLORS["danger_hover"], command=self._delete
        ).pack(side="left")
        ctk.CTkButton(
            actions, text="Batal", width=80, fg_color=COLORS["surface"], border_width=1, border_color=COLORS["line"],
            text_color=COLORS["text_secondary"], hover_color=COLORS["surface_hover"], command=self.destroy
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            actions, text=" Simpan", image=get_icon("key", (14, 14), "#FFFFFF"), compound="left",
            width=110, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(weight="bold"), command=self._save
        ).pack(side="right")

    def _load_credential(self):
        credential = self.db.get_global_git_credential()
        if credential:
            self.username_entry.insert(0, credential["username"])
            self.token_entry.insert(0, credential["password"])

    def _save(self):
        username = self.username_entry.get().strip()
        token = self.token_entry.get().strip()
        if not username or not token:
            self.status_label.configure(text="Username dan token Git wajib diisi.")
            return
        self.db.save_global_git_credential(username, token)
        self.destroy()

    def _delete(self):
        if not self.db.get_global_git_credential():
            self.destroy()
            return
        if messagebox.askyesno("Hapus Git Credential", "Hapus credential Git global dari perangkat ini?", parent=self):
            self.db.delete_global_git_credential()
            self.destroy()
