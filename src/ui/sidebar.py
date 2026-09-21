import threading
import webbrowser
from typing import Callable

import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

from theme import APP_VERSION, COLORS, resource_path
from update_service import check_for_update


class Sidebar(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTk,
        on_show_hosts: Callable[[], None],
        on_show_db_blast: Callable[[], None],
        on_git_credential: Callable[[], None],
        on_import: Callable[[], None],
        on_export: Callable[[], None],
    ):
        super().__init__(parent, width=224, corner_radius=0, fg_color=COLORS["sidebar"])

        self.grid_rowconfigure(4, weight=1)  # row 4 = spacer
        self.grid_columnconfigure(0, weight=1)

        self._build_brand()
        self._build_nav(on_show_hosts, on_show_db_blast, on_git_credential)
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
        ctk.CTkLabel(brand, text="D", width=35, height=35, corner_radius=9, fg_color=COLORS["accent"], font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=(0, 9))

    def _build_nav(self, on_show_hosts: Callable[[], None], on_show_db_blast: Callable[[], None], on_git_credential: Callable[[], None]):
        self.btn_hosts = ctk.CTkButton(
            self, text="Pull Blast", anchor="w",
            height=38, corner_radius=9, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], text_color=COLORS["text"],
            command=on_show_hosts
        )
        self.btn_hosts.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.btn_db_blast = ctk.CTkButton(
            self, text="DB Blast", anchor="w",
            height=38, corner_radius=9, fg_color="transparent", hover_color=COLORS["surface_hover"], text_color=COLORS["text"],
            command=on_show_db_blast
        )
        self.btn_db_blast.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        btn_git_credential = ctk.CTkButton(
            self, text="⌘  Git Credential", anchor="w",
            height=34, corner_radius=8, fg_color="transparent", hover_color=COLORS["surface_hover"],
            command=on_git_credential
        )
        btn_git_credential.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Spacer keeps data actions aligned with the lower edge of the window.
        ctk.CTkLabel(self, text="").grid(row=4, column=0)
        ctk.CTkLabel(self, text="DATA", text_color=COLORS["muted"], font=ctk.CTkFont(size=10, weight="bold")).grid(row=5, column=0, padx=20, pady=(0, 5), sticky="w")

    def _build_data_actions(self, on_import: Callable[[], None], on_export: Callable[[], None]):
        btn_import = ctk.CTkButton(
            self,
            text="⬇  Import",
            height=34, corner_radius=8, fg_color="transparent", hover_color=COLORS["surface_hover"],
            anchor="w",
            command=on_import
        )
        btn_import.grid(row=6, column=0, padx=10, pady=5, sticky="ew")

        btn_export = ctk.CTkButton(
            self,
            text="⬆  Export",
            height=34, corner_radius=8, fg_color="transparent", hover_color=COLORS["surface_hover"],
            anchor="w",
            command=on_export
        )
        btn_export.grid(row=7, column=0, padx=10, pady=(5, 10), sticky="ew")

        self.btn_update = ctk.CTkButton(
            self,
            text="↻  Check for Updates",
            height=34, corner_radius=8, fg_color="transparent", hover_color=COLORS["surface_hover"],
            anchor="w", command=self._check_for_updates
        )
        self.btn_update.grid(row=8, column=0, padx=10, pady=(0, 10), sticky="ew")

    def _build_footer(self):
        footer_label = ctk.CTkLabel(
            self,
            text="Vibe Code \n By DO.MBA Devs",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["muted"]
        )
        footer_label.grid(row=9, column=0, padx=10, pady=(0, 12), sticky="ew")

    def set_active(self, view_name: str):
        """Reset semua tombol nav ke transparan, lalu aktifkan yang dipilih."""
        self.btn_hosts.configure(fg_color=COLORS["accent"] if view_name == "hosts" else "transparent")
        self.btn_db_blast.configure(fg_color=COLORS["accent"] if view_name == "db_blast" else "transparent")

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

    def _restore_update_button(self):
        self.btn_update.configure(state="normal", text="↻  Check for Updates")

    def _show_update_result(self, result):
        self._restore_update_button()
        if not result.update_available:
            messagebox.showinfo(
                "No Update Available",
                f"Anda sudah memakai versi terbaru (v{APP_VERSION})."
            )
            return

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
