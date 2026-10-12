import subprocess
import sys
import threading
from typing import Any, Callable, List, Optional

import customtkinter as ctk

from theme import COLORS, resource_path
from icons import get_icon

TOAST_WIDTH = 360
TOAST_GAP = 10
MAX_VISIBLE = 4


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
                # macOS AppleScript via System Events
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


class ToastNotification(ctk.CTkToplevel):
    """Pop-up bawaan aplikasi di pojok kanan bawah layar."""

    def __init__(self, manager: "ToastManager", title: str, message: str,
                 on_click: Optional[Callable[[], None]], duration_ms: int):
        super().__init__(manager.root, fg_color=COLORS["surface"])
        self.manager = manager
        self._on_click = on_click

        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        card = ctk.CTkFrame(
            self, fg_color=COLORS["surface"], border_width=1,
            border_color=COLORS["accent_border"], corner_radius=8
        )
        card.pack(fill="both", expand=True)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="", image=get_icon("bell", (18, 18), COLORS["accent"])).grid(
            row=0, column=0, rowspan=2, padx=(14, 10), pady=12, sticky="n"
        )
        lbl_title = ctk.CTkLabel(
            card, text=title if len(title) <= 48 else title[:47] + "…", text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w", justify="left"
        )
        lbl_title.grid(row=0, column=1, sticky="ew", pady=(10, 0))
        lbl_message = ctk.CTkLabel(
            card, text=message, text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
            anchor="w", justify="left", wraplength=TOAST_WIDTH - 90
        )
        lbl_message.grid(row=1, column=1, sticky="ew", pady=(0, 12))
        ctk.CTkButton(
            card, text="", image=get_icon("x", (12, 12), COLORS["muted"]), width=24, height=24,
            fg_color="transparent", hover_color=COLORS["surface_hover"], command=self.close
        ).grid(row=0, column=2, padx=(4, 8), pady=(8, 0), sticky="ne")

        for widget in (card, lbl_title, lbl_message):
            widget.bind("<Button-1>", self._clicked)
            widget.configure(cursor="hand2")

        self._close_job = self.after(duration_ms, self.close)

    def _clicked(self, _event=None):
        callback = self._on_click
        self.close()
        if callback:
            callback()

    def close(self):
        if self._close_job:
            try:
                self.after_cancel(self._close_job)
            except Exception:
                pass
            self._close_job = None
        self.manager._remove(self)
        try:
            if self.winfo_exists():
                self.destroy()
        except Exception:
            pass


class ToastManager:
    """Manajer notifikasi aplikasi yang mendukung mode OS native dan mode bawaan aplikasi (built-in)."""

    def __init__(self, root: ctk.CTk, db: Optional[Any] = None):
        self.root = root
        self.db = db
        self._toasts: List[ToastNotification] = []

    def show(self, title: str, message: str, on_click: Optional[Callable[[], None]] = None, duration_ms: int = 9000):
        notify_type = "os"
        if self.db:
            notify_type = self.db.get_setting("redmine_notify_type", "os")

        if notify_type in ("os", "both"):
            send_os_notification(title, message, on_click=on_click)

        if notify_type in ("app", "both"):
            self.show_app_toast(title, message, on_click=on_click, duration_ms=duration_ms)

    def show_app_toast(self, title: str, message: str, on_click: Optional[Callable[[], None]] = None, duration_ms: int = 9000):
        """Menampilkan notifikasi popup bawaan aplikasi."""
        while len(self._toasts) >= MAX_VISIBLE:
            self._toasts[0].close()
        toast = ToastNotification(self, title, message, on_click, duration_ms)
        self._toasts.append(toast)
        self._layout()
        toast.deiconify()
        toast.lift()

    def _remove(self, toast: ToastNotification):
        if toast in self._toasts:
            self._toasts.remove(toast)
            self._layout()

    def _layout(self):
        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            bottom = screen_h - (56 if sys.platform == "win32" else 24)  # sisakan ruang taskbar
            for toast in reversed(self._toasts):
                toast.update_idletasks()
                height = max(toast.winfo_reqheight(), 70)
                bottom -= height
                toast.geometry(f"{TOAST_WIDTH}x{height}+{screen_w - TOAST_WIDTH - 16}+{bottom}")
                bottom -= TOAST_GAP
        except Exception:
            pass


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
