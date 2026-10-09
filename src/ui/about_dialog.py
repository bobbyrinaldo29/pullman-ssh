import webbrowser
from typing import Any, Optional
import customtkinter as ctk
from PIL import Image

from theme import APP_VERSION, COLORS, resource_path
from icons import get_icon


class AboutDialog(ctk.CTkToplevel):
    """Dialog Tentang Aplikasi (About DO.MBA Pull Manager) yang modern dan elegan."""

    def __init__(self, parent: Any):
        super().__init__(parent)
        self.app = parent

        self.title("About DO.MBA Pull Manager")
        self.geometry("400x440")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["window"])

        # Modal behavior
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self._center_window(parent)

        self._build_ui()

    def _center_window(self, parent: Any):
        self.update_idletasks()
        try:
            px = parent.winfo_x()
            py = parent.winfo_y()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = 400
            h = 440
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["line"])
        container.pack(fill="both", expand=True, padx=20, pady=20)
        container.pack_propagate(False)

        # 1. Logo
        logo_loaded = False
        try:
            logo_path1 = resource_path("assets/icon_512x512.png")
            logo_path2 = resource_path("src/assets/icon_512x512.png")
            logo_path = logo_path1 if logo_path1.exists() else (logo_path2 if logo_path2.exists() else None)
            if logo_path:
                pil_img = Image.open(logo_path)
                logo_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(76, 76))
                lbl_logo = ctk.CTkLabel(container, text="", image=logo_ctk)
                lbl_logo.pack(pady=(24, 12))
                logo_loaded = True
        except Exception:
            pass

        if not logo_loaded:
            lbl_fallback = ctk.CTkLabel(
                container,
                text="DO.MBA",
                width=76,
                height=76,
                corner_radius=16,
                fg_color=COLORS["accent"],
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=18, weight="bold")
            )
            lbl_fallback.pack(pady=(24, 12))

        # 2. App Name & Subtitle
        ctk.CTkLabel(
            container,
            text="DO.MBA - Pull Manager",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            container,
            text=f"Version {APP_VERSION}",
            text_color=COLORS["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            container,
            text="High-Performance SSH Deployment,\nDatabase Blast & SFTP File Manager",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11),
            justify="center"
        ).pack(pady=(0, 16))

        # 3. Copyright
        ctk.CTkLabel(
            container,
            text="Copyright © 2026 DO.MBA Devs • Vibe Code.\nAll rights reserved.",
            text_color=COLORS["subtle"],
            font=ctk.CTkFont(size=10),
            justify="center"
        ).pack(pady=(0, 18))

        # 4. Action Buttons
        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.pack(fill="x", padx=24, pady=(0, 12))

        btn_github = ctk.CTkButton(
            btn_box,
            text=" GitHub Releases",
            image=get_icon("sparkles", (13, 13), COLORS["text"]),
            compound="left",
            height=32,
            corner_radius=8,
            fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=11),
            command=lambda: webbrowser.open("https://github.com/bobbyrinaldo29/pullman-ssh/releases")
        )
        btn_github.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_close = ctk.CTkButton(
            btn_box,
            text="Close",
            height=32,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.destroy
        )
        btn_close.pack(side="right", fill="x", expand=True, padx=(6, 0))
