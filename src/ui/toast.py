import subprocess
import sys
import threading
from typing import Callable, Optional

import customtkinter as ctk

from theme import resource_path


def send_os_notification(title: str, message: str, subtitle: str = "", on_click: Optional[Callable[[], None]] = None) -> None:
    """Mengirim notifikasi murni ke Sistem Operasi (macOS Notification Center, Windows Toast/Balloon, Linux notify-send)."""
    def _worker():
        try:
            icon_ico = resource_path("assets/app_icon.ico")
            if not icon_ico.exists():
                icon_ico = resource_path("src/assets/app_icon.ico")

            icon_png = resource_path("assets/icon_512x512.png")
            if not icon_png.exists():
                icon_png = resource_path("src/assets/icon_512x512.png")

            if sys.platform == "darwin":
                # macOS AppleScript via System Events: 100% stabil, tanpa crash/segfault
                t = (title or "DO.MBA Pull Manager").replace('\\', '\\\\').replace('"', '\\"')
                m = (message or "").replace('\\', '\\\\').replace('"', '\\"')
                s = (subtitle or "").replace('\\', '\\\\').replace('"', '\\"')
                sub_part = f' subtitle "{s}"' if s else ""
                script = f'tell application "System Events" to display notification "{m}" with title "{t}"{sub_part} sound name "default"'
                subprocess.run(
                    ["osascript", "-e", script],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            elif sys.platform == "win32":
                # Windows PowerShell Balloon / Toast notification
                t = (title or "DO.MBA Pull Manager").replace("'", "''")
                m = (message or "").replace("'", "''")
                ico_str = str(icon_ico.resolve()).replace("'", "''") if icon_ico.exists() else ""
                
                if ico_str:
                    icon_init = f"$objNotifyIcon.Icon = New-Object System.Drawing.Icon('{ico_str}');"
                else:
                    icon_init = "$objNotifyIcon.Icon = [System.Drawing.SystemIcons]::Information;"

                ps_script = (
                    "[void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
                    "$objNotifyIcon = New-Object System.Windows.Forms.NotifyIcon; "
                    f"{icon_init} "
                    f"$objNotifyIcon.BalloonTipTitle = '{t}'; "
                    f"$objNotifyIcon.BalloonTipText = '{m}'; "
                    "$objNotifyIcon.Visible = $True; "
                    "$objNotifyIcon.ShowBalloonTip(5000); "
                    "Start-Sleep -Seconds 5; "
                    "$objNotifyIcon.Dispose()"
                )
                kwargs = {}
                if hasattr(subprocess, "CREATE_NO_WINDOW"):
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps_script],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs
                )
            elif sys.platform.startswith("linux"):
                # Linux notify-send dengan icon aplikasi
                cmd = ["notify-send", "-a", "DO.MBA Pull Manager"]
                if icon_png.exists():
                    cmd.extend(["-i", str(icon_png.resolve())])
                cmd.extend([title, message])
                subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


class ToastManager:
    """Manajer notifikasi aplikasi: secara eksklusif menggunakan notifikasi native Sistem Operasi."""

    def __init__(self, root: ctk.CTk):
        self.root = root

    def show(self, title: str, message: str, on_click: Optional[Callable[[], None]] = None, duration_ms: int = 9000):
        send_os_notification(title, message, on_click=on_click)


def flash_taskbar(window: ctk.CTk) -> None:
    """Kedipkan ikon taskbar Windows jika aplikasi sedang tidak aktif."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                        ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]

        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        # FLASHW_ALL (3) | FLASHW_TIMERNOFG (12): kedip sampai jendela kembali di-fokuskan
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 3 | 12, 0, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass
