import threading
import webbrowser
from typing import Callable, Optional

import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

from theme import APP_VERSION, COLORS, resource_path
from icons import get_icon
from update_service import check_for_update


class Sidebar(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTk,
        on_show_hosts: Callable[[], None],
        on_show_db_blast: Callable[[], None],
        on_show_sftp: Callable[[], None],
        on_git_credential: Callable[[], None],
        on_import: Callable[[], None],
        on_export: Callable[[], None],
        on_toggle_theme: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent, width=224, corner_radius=0, fg_color=COLORS["sidebar"])

        self._on_toggle_theme = on_toggle_theme
        self.grid_rowconfigure(5, weight=1)  # row 5 = spacer
        self.grid_columnconfigure(0, weight=1)

        self._build_brand()
        self._build_nav(on_show_hosts, on_show_db_blast, on_show_sftp, on_git_credential)
        self._build_data_actions(on_import, on_export)
        self._build_footer()

    def _build_brand(self):
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=0, padx=18, pady=(25, 30), sticky="w")
        try:
            logo_path1 = resource_path("assets/icon_512x512.png")
            logo_path2 = resource_path("src/assets/icon_512x512.png")
            logo_path = logo_path1 if logo_path1.exists() else (logo_path2 if logo_path2.exists() else None)
            if logo_path:
                pil_logo = Image.open(logo_path)
                self.brand_icon = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(35, 35))
                ctk.CTkLabel(brand, text="", image=self.brand_icon).pack(side="left", padx=(0, 9))
            else:
                self._build_brand_fallback(brand)
        except Exception:
            self._build_brand_fallback(brand)

        brand_copy = ctk.CTkFrame(brand, fg_color="transparent")
        brand_copy.pack(side="left")
        ctk.CTkLabel(brand_copy, text="DO.MBA", text_color=COLORS["text"], font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(brand_copy, text="DEPLOYMENT CONSOLE", text_color=COLORS["muted"], font=ctk.CTkFont(size=8, weight="bold")).pack(anchor="w")

    @staticmethod
    def _build_brand_fallback(brand):
        ctk.CTkLabel(brand, text="D", width=35, height=35, corner_radius=9, fg_color=COLORS["accent"], text_color="#FFFFFF", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=(0, 9))

    def _build_nav(
        self,
        on_show_hosts: Callable[[], None],
        on_show_db_blast: Callable[[], None],
        on_show_sftp: Callable[[], None],
        on_git_credential: Callable[[], None]
    ):
        self.btn_hosts = ctk.CTkButton(
            self,
            text=" Pull Blast",
            image=get_icon("rocket", (16, 16), "#FFFFFF"),
            compound="left",
            anchor="w",
            height=38,
            corner_radius=9,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=on_show_hosts
        )
        self.btn_hosts.grid(row=1, column=0, padx=10, pady=4, sticky="ew")

        self.btn_db_blast = ctk.CTkButton(
            self,
            text=" DB Blast",
            image=get_icon("database", (16, 16), COLORS["text_secondary"]),
            compound="left",
            anchor="w",
            height=38,
            corner_radius=9,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=13),
            command=on_show_db_blast
        )
        self.btn_db_blast.grid(row=2, column=0, padx=10, pady=4, sticky="ew")

        self.btn_sftp = ctk.CTkButton(
            self,
            text=" File Manager",
            image=get_icon("folder-tree", (16, 16), COLORS["text_secondary"]),
            compound="left",
            anchor="w",
            height=38,
            corner_radius=9,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=13),
            command=on_show_sftp
        )
        self.btn_sftp.grid(row=3, column=0, padx=10, pady=4, sticky="ew")

        btn_git_credential = ctk.CTkButton(
            self,
            text=" Git Credential",
            image=get_icon("key", (15, 15), COLORS["text_secondary"]),
            compound="left",
            anchor="w",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=12),
            command=on_git_credential
        )
        btn_git_credential.grid(row=4, column=0, padx=10, pady=4, sticky="ew")

        # Spacer keeps data actions aligned with the lower edge of the window.
        ctk.CTkLabel(self, text="").grid(row=5, column=0)
        ctk.CTkLabel(self, text="DATA & TOOLS", text_color=COLORS["subtle"], font=ctk.CTkFont(size=10, weight="bold")).grid(row=6, column=0, padx=18, pady=(0, 4), sticky="w")

    def _build_data_actions(self, on_import: Callable[[], None], on_export: Callable[[], None]):
        btn_import = ctk.CTkButton(
            self,
            text=" Import",
            image=get_icon("download", (15, 15), COLORS["text_secondary"]),
            compound="left",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=12),
            anchor="w",
            command=on_import
        )
        btn_import.grid(row=7, column=0, padx=10, pady=3, sticky="ew")

        btn_export = ctk.CTkButton(
            self,
            text=" Export",
            image=get_icon("upload", (15, 15), COLORS["text_secondary"]),
            compound="left",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=12),
            anchor="w",
            command=on_export
        )
        btn_export.grid(row=8, column=0, padx=10, pady=3, sticky="ew")

        # Tombol Toggle Theme (Light Mode / Dark Mode)
        self.btn_theme = ctk.CTkButton(
            self,
            text=" Light Mode" if ctk.get_appearance_mode() == "Dark" else " Dark Mode",
            image=get_icon("sun" if ctk.get_appearance_mode() == "Dark" else "moon", (14, 14), COLORS["text_secondary"]),
            compound="left",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=12),
            anchor="w",
            command=self._on_theme_toggle_clicked
        )
        self.btn_theme.grid(row=9, column=0, padx=10, pady=(4, 2), sticky="ew")

        self.btn_update = ctk.CTkButton(
            self,
            text=" Check for Updates",
            image=get_icon("refresh-cw", (14, 14), COLORS["muted"]),
            compound="left",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11),
            anchor="w",
            command=self._check_for_updates
        )
        self.btn_update.grid(row=10, column=0, padx=10, pady=(4, 10), sticky="ew")

    def _build_footer(self):
        footer_label = ctk.CTkLabel(
            self,
            text="Vibe Code • DO.MBA Devs",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["subtle"]
        )
        footer_label.grid(row=11, column=0, padx=10, pady=(0, 14), sticky="ew")

    def _on_theme_toggle_clicked(self):
        if self._on_toggle_theme:
            self._on_toggle_theme()

    def update_theme_state(self, mode: str):
        """Update label dan icon tombol theme toggle saat mode berganti."""
        is_dark = (mode.lower() == "dark")
        self.btn_theme.configure(
            text=" Light Mode" if is_dark else " Dark Mode",
            image=get_icon("sun" if is_dark else "moon", (14, 14), COLORS["text_secondary"])
        )

    def set_active(self, view_name: str):
        """Reset semua tombol nav ke transparan, lalu aktifkan yang dipilih."""
        is_hosts = (view_name == "hosts")
        is_db = (view_name == "db_blast")
        is_sftp = (view_name == "sftp")

        self.btn_hosts.configure(
            fg_color=COLORS["accent"] if is_hosts else "transparent",
            hover_color=COLORS["accent_hover"] if is_hosts else COLORS["surface_hover"],
            text_color="#FFFFFF" if is_hosts else COLORS["text_secondary"],
            image=get_icon("rocket", (16, 16), "#FFFFFF" if is_hosts else COLORS["text_secondary"]),
            font=ctk.CTkFont(size=13, weight="bold" if is_hosts else "normal")
        )
        self.btn_db_blast.configure(
            fg_color=COLORS["accent"] if is_db else "transparent",
            hover_color=COLORS["accent_hover"] if is_db else COLORS["surface_hover"],
            text_color="#FFFFFF" if is_db else COLORS["text_secondary"],
            image=get_icon("database", (16, 16), "#FFFFFF" if is_db else COLORS["text_secondary"]),
            font=ctk.CTkFont(size=13, weight="bold" if is_db else "normal")
        )
        self.btn_sftp.configure(
            fg_color=COLORS["accent"] if is_sftp else "transparent",
            hover_color=COLORS["accent_hover"] if is_sftp else COLORS["surface_hover"],
            text_color="#FFFFFF" if is_sftp else COLORS["text_secondary"],
            image=get_icon("folder-tree", (16, 16), "#FFFFFF" if is_sftp else COLORS["text_secondary"]),
            font=ctk.CTkFont(size=13, weight="bold" if is_sftp else "normal")
        )

    def _check_for_updates(self):
        """Check GitHub Releases in a worker thread so the UI remains responsive."""
        self.btn_update.configure(state="disabled", text="Checking...")

        def worker():
            try:
                result = check_for_update(APP_VERSION)
                self.after(0, lambda: self._show_update_result(result))
            except Exception as error:
                self.after(0, lambda: self._show_update_error(str(error)))

        threading.Thread(target=worker, daemon=True).start()

    def show_update_badge(self, version: str):
        """Ubah tampilan tombol update di sidebar agar memberi sinyal visual jelas bahwa ada versi baru."""
        self.btn_update.configure(
            text=f" Update {version} Tersedia!",
            text_color=COLORS["accent_text"],
            image=get_icon("sparkles", (14, 14), COLORS["accent_text"]),
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11, weight="bold")
        )

    def _restore_update_button(self):
        self.btn_update.configure(
            state="normal",
            text=" Check for Updates",
            text_color=COLORS["muted"],
            image=get_icon("refresh-cw", (14, 14), COLORS["muted"]),
            fg_color="transparent",
            border_width=0,
            font=ctk.CTkFont(size=11)
        )

    def _show_update_result(self, result):
        self._restore_update_button()
        if not result.update_available:
            messagebox.showinfo(
                "No Update Available",
                f"Anda sudah memakai versi terbaru (v{APP_VERSION})."
            )
            return

        self.show_update_badge(result.latest_version)
        should_open = messagebox.askyesno(
            "Update Available",
            f"Versi baru {result.latest_version} tersedia.\n"
            f"Versi saat ini: v{APP_VERSION}\n\n"
            "Buka halaman GitHub Releases?"
        )
        if should_open:
            webbrowser.open(result.release_url)

    def _show_update_error(self, error: str):
        self._restore_update_button()
        messagebox.showerror("Update Check Failed", error)
