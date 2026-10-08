import os
import sys
from pathlib import Path

os.environ['TK_SILENCE_DEPRECATION'] = '1'

APP_VERSION = "1.1.0"
APP_NAME = "DO.MBA Pull Manager"

# A refined, modern dark palette inspired by macOS Sonoma/Sequoia pro developer tools.
COLORS = {
    "window": "#0D0E12",          # Deep obsidian canvas background
    "sidebar": "#13151B",         # Sleek sidebar background
    "sidebar_border": "#1E212B",  # Subtle border line
    "surface": "#181A22",         # Elevated panel / card surface
    "surface_hover": "#222530",   # Interactive hover state
    "surface_active": "#2A2E3D",  # Active pressed state
    "input_bg": "#101117",        # Text entry, log & table background
    "line": "#262936",            # Card borders & subtle dividers
    "line_subtle": "#1B1D27",     # Minimal divider
    "text": "#F8FAFC",            # Primary high-contrast text
    "text_secondary": "#CBD5E1",  # Secondary soft text
    "muted": "#94A3B8",           # Subtitles & placeholder text
    "subtle": "#64748B",          # Footers & metadata hints
    "accent": "#3B82F6",          # Electric Blue accent
    "accent_hover": "#2563EB",    # Accent hover
    "accent_active": "#1D4ED8",   # Accent pressed
    "accent_subtle": "#1E293B",   # Accent badge / secondary background
    "accent_text": "#93C5FD",     # Accent badge / secondary text
    "accent_border": "#2E476B",   # Accent border
    "success": "#10B981",         # Emerald Green
    "success_hover": "#059669",
    "success_subtle": "#064E3B",
    "success_text": "#6EE7B7",
    "danger": "#EF4444",          # Modern Crimson / Rose Red
    "danger_hover": "#DC2626",
    "danger_subtle": "#381717",
    "danger_border": "#682323",
    "danger_text": "#FCA5A5",
    "warning": "#F59E0B",         # Amber
    "warning_subtle": "#3B2807",
    "warning_text": "#FCD34D",
    "badge_bg": "#1E293B",
    "badge_text": "#93C5FD",
    "console_bg": "#090A0D",      # True terminal background
    "console_text": "#E2E8F0",    # Crisp monospaced terminal text
}


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
