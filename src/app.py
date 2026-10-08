from datetime import datetime
import os
import sys
import threading
from tkinter import messagebox
import webbrowser

os.environ['TK_SILENCE_DEPRECATION'] = '1'

import customtkinter as ctk
from PIL import ImageTk, Image

from theme import APP_VERSION, COLORS, application_data_path, resource_path, apply_treeview_styles
from database import DatabaseManager
from update_service import check_for_update, UpdateCheckResult
from ui.db_blast_view import DBBlastView
from ui.git_credential_dialog import GitCredentialDialog
from ui.hosts_view import HostsView
from ui.sidebar import Sidebar


class PullmanApp(ctk.CTk):
    def __init__(self):
        # 1. Initialize Root Window first to ensure single Tk interpreter
        super().__init__(fg_color=COLORS["window"])

        # 2. Database & Key Storage
        data_path = application_data_path()
        self.db = DatabaseManager(
            str(data_path / "pullManager.db"),
            str(data_path / ".master.key")
        )

        # 3. Muat preferensi tema (Default: Dark)
        saved_theme = self.db.get_setting("appearance_mode", "Dark")
        ctk.set_appearance_mode(saved_theme)
        ctk.set_default_color_theme("dark-blue")
        apply_treeview_styles(saved_theme)

        self.title(f"DO.MBA - Pull Manager v{APP_VERSION}")
        self.geometry("1080x680")
        self.minsize(900, 560)
        self._set_windows_app_id()
        self._load_app_icon()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(
            self,
            on_show_hosts=self._show_hosts_view,
            on_show_db_blast=self._show_db_blast_view,
            on_git_credential=self._open_git_credential_dialog,
            on_import=lambda: self.hosts_view.open_import_dialog(),
            on_export=lambda: self.hosts_view.open_export_dialog(),
            on_toggle_theme=self._toggle_appearance_mode,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Pull Blast dan DB Blast berbagi satu tabel host yang sama, jadi masing-masing memberi tahu
        # yang lain ketika datanya berubah (tambah/edit/hapus), agar keduanya selalu tersinkron.
        self.hosts_view = HostsView(self, self.db, on_data_changed=self._notify_db_blast_changed)
        self.db_blast_frame = None

        self._show_hosts_view()

        # Mulai auto check update harian di background setelah startup
        self.after(3000, self._start_background_update_checker)

    def _toggle_appearance_mode(self):
        """Beralih antara Dark Mode dan Light Mode secara dinamis."""
        current = ctk.get_appearance_mode()
        new_mode = "Light" if current.lower() == "dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        self.db.set_setting("appearance_mode", new_mode)
        apply_treeview_styles(new_mode)
        self.sidebar.update_theme_state(new_mode)
        if hasattr(self, "hosts_view") and self.hosts_view:
            self.hosts_view.on_theme_changed(new_mode)
        if getattr(self, "db_blast_frame", None):
            self.db_blast_frame.on_theme_changed(new_mode)

    def _start_background_update_checker(self):
        """Memulai pengecekan update otomatis di background secara berkala (1x sehari)."""
        self._check_update_daily_background()
        # Periksa ulang setiap 1 jam untuk mengecek apakah sudah saatnya cek harian (>= 24 jam)
        self.after(3600 * 1000, self._start_background_update_checker)

    def _check_update_daily_background(self):
        """Cek update terbaru di GitHub jika belum pernah dicek dalam 24 jam terakhir."""
        last_check_str = self.db.get_setting("last_update_check")
        if last_check_str:
            try:
                last_check_dt = datetime.fromisoformat(last_check_str)
                # Jika belum 24 jam (86400 detik), lewati
                if (datetime.now() - last_check_dt).total_seconds() < 86400:
                    return
            except Exception:
                pass

        def worker():
            try:
                result = check_for_update(APP_VERSION, timeout=10)
                self.db.set_setting("last_update_check", datetime.now().isoformat())
                if result.update_available:
                    self.after(0, lambda: self._on_update_available_background(result))
            except Exception:
                # Diamkan kegagalan koneksi di background check agar tidak mengganggu user
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_available_background(self, result: UpdateCheckResult):
        """Tampilkan notifikasi dan badge update saat versi baru terdeteksi di background."""
        self.sidebar.show_update_badge(result.latest_version)
        should_open = messagebox.askyesno(
            "Update Tersedia",
            f"Versi baru DO.MBA Pull Manager (v{result.latest_version}) telah tersedia!\n"
            f"Versi yang Anda gunakan saat ini: v{APP_VERSION}\n\n"
            "Apakah Anda ingin membuka halaman unduhan sekarang?"
        )
        if should_open:
            webbrowser.open(result.release_url)

    def _notify_db_blast_changed(self):
        if getattr(self, "db_blast_frame", None) is not None:
            self.db_blast_frame.mark_needs_refresh()

    def _notify_hosts_changed(self):
        if hasattr(self, "hosts_view"):
            self.hosts_view.mark_needs_refresh()

    def _set_windows_app_id(self):
        """Set AppUserModelID agar icon taskbar Windows muncul terpisah & berikon."""
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("domba.pullmanager.ssh.app")
            except Exception:
                pass

    def _load_app_icon(self):
        """Pasang icon aplikasi (Window Titlebar & Taskbar)."""
        try:
            ico_file = resource_path("assets/app_icon.ico")
            png_file = resource_path("assets/icon_512x512.png")
            if not png_file.exists():
                png_file = resource_path("src/assets/icon_512x512.png")

            if png_file.exists():
                pil_image = Image.open(png_file)
                self.icon_image = ImageTk.PhotoImage(pil_image.resize((256, 256), Image.Resampling.LANCZOS))
                self.wm_iconphoto(True, self.icon_image)

            if sys.platform == "win32" and ico_file.exists():
                self.iconbitmap(default=str(ico_file))
        except Exception as e:
            print(f"Gagal memuat ikon aplikasi: {e}")

    def _open_git_credential_dialog(self):
        GitCredentialDialog(parent=self, db_manager=self.db)

    def _show_hosts_view(self):
        """Tampilkan kembali tampilan Hosts."""
        self.sidebar.set_active("hosts")
        if self.db_blast_frame is not None:
            self.db_blast_frame.grid_remove()
        self.hosts_view.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        if getattr(self.hosts_view, "_needs_refresh", False):
            self.hosts_view.refresh()

    def _show_db_blast_view(self):
        """Tampilkan tampilan DB Blast bergaya Navicat (instan)."""
        self.sidebar.set_active("db_blast")
        self.hosts_view.grid_remove()
        if self.db_blast_frame is None:
            self.db_blast_frame = DBBlastView(self, self.db, on_data_changed=self._notify_hosts_changed)
            self.db_blast_frame.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        else:
            self.db_blast_frame.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
            if getattr(self.db_blast_frame, "_needs_refresh", False):
                self.db_blast_frame._refresh_connections()


if __name__ == "__main__":
    app = PullmanApp()
    app.mainloop()
