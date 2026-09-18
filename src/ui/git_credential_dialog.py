import customtkinter as ctk
from tkinter import messagebox
from typing import Any


class GitCredentialDialog(ctk.CTkToplevel):
    """Editor untuk satu credential Git global aplikasi."""

    def __init__(self, parent: ctk.CTk, db_manager: Any):
        super().__init__(parent)
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

        ctk.CTkLabel(frame, text="Git Credential", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            frame,
            text="Dipakai untuk semua koneksi SSH yang menjalankan Git Pull. "
                 "Token akan disimpan terenkripsi di perangkat ini.",
            text_color="gray", justify="left", wraplength=410,
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=(5, 20))

        ctk.CTkLabel(frame, text="Git username / email", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.username_entry = ctk.CTkEntry(frame, placeholder_text="name@example.com atau username")
        self.username_entry.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(frame, text="Personal access token / password", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.token_entry = ctk.CTkEntry(frame, placeholder_text="Masukkan token Git", show="•")
        self.token_entry.pack(fill="x", pady=(4, 10))

        self.status_label = ctk.CTkLabel(frame, text="", text_color="#EF4444", font=ctk.CTkFont(size=11))
        self.status_label.pack(anchor="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x", side="bottom", pady=(18, 0))
        ctk.CTkButton(actions, text="Hapus", width=80, fg_color="transparent", border_width=1,
                      text_color="#EF4444", command=self._delete).pack(side="left")
        ctk.CTkButton(actions, text="Batal", width=80, fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(actions, text="Simpan Credential", width=145, command=self._save).pack(side="right")

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
