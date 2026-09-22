import os
import sys

os.environ['TK_SILENCE_DEPRECATION'] = '1'

import customtkinter as ctk
from PIL import ImageTk, Image

from theme import APP_VERSION, application_data_path, resource_path
from database import DatabaseManager
from ui.db_blast_view import DBBlastView
from ui.git_credential_dialog import GitCredentialDialog
from ui.hosts_view import HostsView
from ui.sidebar import Sidebar

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


class PullmanApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        data_path = application_data_path()
        self.db = DatabaseManager(
            str(data_path / "pullManager.db"),
            str(data_path / ".master.key")
        )

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
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Pull Blast dan DB Blast berbagi satu tabel host yang sama, jadi masing-masing memberi tahu
        # yang lain ketika datanya berubah (tambah/edit/hapus), agar keduanya selalu tersinkron.
        self.hosts_view = HostsView(self, self.db, on_data_changed=self._notify_db_blast_changed)
        self.db_blast_frame = None

        self._show_hosts_view()

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

            if png_file.exists():
                pil_image = Image.open(png_file)
                self.icon_image = ImageTk.PhotoImage(pil_image.resize((256, 256), Image.Resampling.LANCZOS))
                self.wm_iconphoto(True, self.icon_image)

            if sys.platform == "win32" and ico_file.exists():
                self.iconbitmap(default=str(ico_file))
            elif sys.platform == "darwin" and png_file.exists():
                app_icon = ImageTk.PhotoImage(Image.open(png_file))
                self.iconphoto(True, app_icon)
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
