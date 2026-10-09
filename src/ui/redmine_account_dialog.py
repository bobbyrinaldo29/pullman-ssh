import threading
import customtkinter as ctk
from tkinter import messagebox
from typing import Any, Callable, Optional
from theme import COLORS
from icons import get_icon
from redmine_markup import FORMAT_OPTIONS
from redmine_notifier import INTERVAL_OPTIONS, notifications_enabled, notify_interval_minutes
from redmine_service import RedmineClient, RedmineError, normalize_base_url


class RedmineAccountDialog(ctk.CTkToplevel):
    """Pengaturan akun Redmine per user (URL + API key pribadi)."""

    def __init__(self, parent: ctk.CTk, db_manager: Any, on_saved: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color=COLORS["window"])
        self.db = db_manager
        self._on_saved = on_saved

        self.title("Akun Redmine")
        self.geometry("490x510")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self._load_credential()

    def _setup_ui(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(frame, text="Akun Redmine", text_color=COLORS["text"], font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            frame,
            text="Gunakan API key pribadi Anda (Redmine → My account → API access key). "
                 "Task yang tampil adalah task yang di-assign ke akun tersebut. "
                 "API key disimpan terenkripsi di perangkat ini.",
            text_color=COLORS["muted"], justify="left", wraplength=430,
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=(5, 20))

        ctk.CTkLabel(frame, text="URL Redmine", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.url_entry = ctk.CTkEntry(frame, placeholder_text="https://redmine.example.com")
        self.url_entry.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(frame, text="API access key", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.key_entry = ctk.CTkEntry(frame, placeholder_text="Masukkan API key Redmine", show="•")
        self.key_entry.pack(fill="x", pady=(4, 14))

        notify_row = ctk.CTkFrame(frame, fg_color="transparent")
        notify_row.pack(fill="x", pady=(0, 10))
        self.notify_switch = ctk.CTkSwitch(
            notify_row, text="Notifikasi perubahan status / update task", text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=12), progress_color=COLORS["accent"]
        )
        self.notify_switch.pack(side="left")
        if notifications_enabled(self.db):
            self.notify_switch.select()

        interval_label = next((k for k, v in INTERVAL_OPTIONS.items() if v == notify_interval_minutes(self.db)), "5 menit")
        self.interval_opt = ctk.CTkOptionMenu(
            notify_row, values=list(INTERVAL_OPTIONS.keys()), width=100, height=28,
            fg_color=COLORS["surface"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"]
        )
        self.interval_opt.set(interval_label)
        self.interval_opt.pack(side="right")
        format_row = ctk.CTkFrame(frame, fg_color="transparent")
        format_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(format_row, text="Format teks Redmine", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12)).pack(side="left")
        current_format = self.db.get_setting("redmine_text_format", "auto")
        self.format_opt = ctk.CTkOptionMenu(
            format_row, values=list(FORMAT_OPTIONS.keys()), width=100, height=28,
            fg_color=COLORS["surface"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"]
        )
        self.format_opt.set(next((k for k, v in FORMAT_OPTIONS.items() if v == current_format), "Otomatis"))
        self.format_opt.pack(side="right")

        ctk.CTkLabel(notify_row, text="Cek tiap", text_color=COLORS["muted"], font=ctk.CTkFont(size=11)).pack(side="right", padx=(0, 6))

        self.status_label = ctk.CTkLabel(frame, text="", text_color=COLORS["danger"], font=ctk.CTkFont(size=11), wraplength=430, justify="left")
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
        self.btn_save = ctk.CTkButton(
            actions, text=" Test & Simpan", image=get_icon("check", (14, 14), "#FFFFFF"), compound="left",
            width=130, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(weight="bold"), command=self._save
        )
        self.btn_save.pack(side="right")

    def _load_credential(self):
        credential = self.db.get_redmine_credential()
        if credential:
            self.url_entry.insert(0, credential["base_url"])
            self.key_entry.insert(0, credential["api_key"])

    def _save(self):
        base_url = normalize_base_url(self.url_entry.get())
        api_key = self.key_entry.get().strip()
        if not base_url or not api_key:
            self.status_label.configure(text="URL Redmine dan API key wajib diisi.", text_color=COLORS["danger"])
            return

        self.btn_save.configure(state="disabled", text=" Menguji...")
        self.status_label.configure(text="Menghubungkan ke Redmine...", text_color=COLORS["muted"])

        def worker():
            try:
                user = RedmineClient(base_url, api_key).get_current_user()
                self.after(0, lambda: self._on_test_success(base_url, api_key, user))
            except RedmineError as error:
                message = str(error)
                self.after(0, lambda: self._on_test_failed(message))

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_success(self, base_url: str, api_key: str, user: dict):
        if not self.winfo_exists():
            return
        full_name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip() or user.get("login", "")
        self.db.save_redmine_credential(base_url, api_key, full_name, user.get("id"))
        self.db.set_setting("redmine_notify_enabled", "1" if self.notify_switch.get() else "0")
        self.db.set_setting("redmine_text_format", FORMAT_OPTIONS[self.format_opt.get()])
        self.db.set_setting("redmine_notify_interval", str(INTERVAL_OPTIONS[self.interval_opt.get()]))
        if self._on_saved:
            self._on_saved()
        self.destroy()

    def _on_test_failed(self, message: str):
        if not self.winfo_exists():
            return
        self.btn_save.configure(state="normal", text=" Test & Simpan")
        self.status_label.configure(text=message, text_color=COLORS["danger"])

    def _delete(self):
        if not self.db.get_redmine_credential():
            self.destroy()
            return
        if messagebox.askyesno("Hapus Akun Redmine", "Hapus akun Redmine dari perangkat ini?", parent=self):
            self.db.delete_redmine_credential()
            if self._on_saved:
                self._on_saved()
            self.destroy()
