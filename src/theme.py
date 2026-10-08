import os
import sys
from pathlib import Path
from typing import Any, Optional, Tuple

os.environ['TK_SILENCE_DEPRECATION'] = '1'

import customtkinter as ctk

APP_VERSION = "1.2.0"
APP_NAME = "DO.MBA Pull Manager"

# Dual Theme Palette: Tuple (Light Mode, Dark Mode)
# Terintegrasi native dengan CustomTkinter untuk dynamic appearance switching.
COLORS = {
    # Canvas / Windows
    "window": ("#F8FAFC", "#0D0E12"),          # Light: Slate 50 / Dark: Deep Obsidian
    "sidebar": ("#F1F5F9", "#13151B"),         # Light: Slate 100 / Dark: Sleek Sidebar
    "sidebar_border": ("#E2E8F0", "#1E212B"),  # Subtle border line
    "surface": ("#FFFFFF", "#181A22"),         # Elevated panel / card surface
    "surface_hover": ("#F1F5F9", "#222530"),   # Interactive hover state
    "surface_active": ("#E2E8F0", "#2A2E3D"),  # Active pressed state
    "input_bg": ("#FFFFFF", "#101117"),        # Text entry, log & table background
    "line": ("#E2E8F0", "#262936"),            # Card borders & subtle dividers
    "line_subtle": ("#F1F5F9", "#1B1D27"),     # Minimal divider

    # Text Colors
    "text": ("#0F172A", "#F8FAFC"),            # Primary high-contrast text
    "text_secondary": ("#475569", "#CBD5E1"),  # Secondary soft text
    "muted": ("#64748B", "#94A3B8"),           # Subtitles & placeholder text
    "subtle": ("#94A3B8", "#64748B"),          # Footers & metadata hints

    # Accent (Electric Blue)
    "accent": ("#2563EB", "#3B82F6"),          # Blue 600 / Blue 500
    "accent_hover": ("#1D4ED8", "#2563EB"),    # Hover
    "accent_active": ("#1E40AF", "#1D4ED8"),   # Pressed
    "accent_subtle": ("#EFF6FF", "#1E293B"),   # Accent badge / secondary background
    "accent_text": ("#1D4ED8", "#93C5FD"),     # Accent badge / secondary text
    "accent_border": ("#BFDBFE", "#2E476B"),   # Accent border

    # Success (Emerald Green)
    "success": ("#059669", "#10B981"),
    "success_hover": ("#047857", "#059669"),
    "success_subtle": ("#ECFDF5", "#064E3B"),
    "success_text": ("#065F46", "#6EE7B7"),

    # Danger (Rose / Crimson Red)
    "danger": ("#DC2626", "#EF4444"),
    "danger_hover": ("#B91C1C", "#DC2626"),
    "danger_subtle": ("#FEF2F2", "#381717"),
    "danger_border": ("#FECACA", "#682323"),
    "danger_text": ("#991B1B", "#FCA5A5"),

    # Warning (Amber)
    "warning": ("#D97706", "#F59E0B"),
    "warning_subtle": ("#FFFBEB", "#3B2807"),
    "warning_text": ("#92400E", "#FCD34D"),

    "badge_bg": ("#EFF6FF", "#1E293B"),
    "badge_text": ("#1D4ED8", "#93C5FD"),

    # Console Text & BG
    "console_bg": ("#0F172A", "#090A0D"),      # True monospaced terminal bg
    "console_text": ("#F8FAFC", "#E2E8F0"),    # Crisp monospaced terminal text
}


def get_color(key: str, mode: Optional[str] = None) -> str:
    """Mengambil representasi single HEX color string untuk native Tkinter (Treeview, tk.Menu)."""
    val = COLORS.get(key, key)
    if isinstance(val, (tuple, list)):
        current_mode = (mode or ctk.get_appearance_mode()).lower()
        return val[0] if current_mode == "light" else val[1]
    return str(val)


def apply_treeview_styles(mode: Optional[str] = None) -> None:
    """Menerapkan konfigurasi ttk.Style Treeview sesuai dengan tema Light atau Dark."""
    from tkinter import ttk
    style = ttk.Style()
    style.theme_use("default")
    
    bg = get_color("input_bg", mode)
    fg = get_color("text", mode)
    heading_bg = get_color("surface", mode)
    heading_fg = get_color("muted", mode)
    accent = get_color("accent", mode)

    for prefix in ["Pullman", "Navicat"]:
        style.configure(
            f"{prefix}.Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            rowheight=29,
            font=("Segoe UI", 9),
            borderwidth=0
        )
        style.configure(
            f"{prefix}.Treeview.Heading",
            background=heading_bg,
            foreground=heading_fg,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            borderwidth=0
        )
        style.map(
            f"{prefix}.Treeview",
            background=[("selected", accent)],
            foreground=[("selected", "#FFFFFF")]
        )


def resource_path(relative_path: str) -> Path:
    """Resolve bundled assets in PyInstaller and source assets during development."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path


def application_data_path() -> Path:
    """Keep mutable data outside the read-only app bundle in packaged builds."""
    if not getattr(sys, "frozen", False):
        return Path.cwd()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base_dir = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    else:
        base_dir = Path.home() / ".local" / "share"
    data_path = base_dir / APP_NAME
    data_path.mkdir(parents=True, exist_ok=True)
    return data_path
