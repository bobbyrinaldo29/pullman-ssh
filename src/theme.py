import os
import sys
from pathlib import Path

os.environ['TK_SILENCE_DEPRECATION'] = '1'

APP_VERSION = "1.0.0"
APP_NAME = "DO.MBA Pull Manager"

# A restrained graphite palette inspired by current macOS utility apps.
COLORS = {
    "window": "#1A1B1F",
    "sidebar": "#242529",
    "surface": "#1A1B1F",
    "surface_hover": "#2A2C33",
    "line": "#32343B",
    "text": "#F5F5F7",
    "muted": "#9699A3",
    "accent": "#0A84FF",
    "accent_hover": "#0072E5",
    "danger": "#FF453A",
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
