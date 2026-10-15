from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from sftp_service import SFTPService
from ui.toast import send_os_notification


@dataclass
class EditorInfo:
    """Informasi aplikasi teks editor yang terdaftar dalam sistem."""
    id: str
    name: str
    executable: Optional[str]
    is_available: bool
    icon_name: str
    description: str
    is_default: bool = False


# Cache editor yang terdeteksi untuk efisiensi
_DETECTED_EDITORS_CACHE: Optional[List[EditorInfo]] = None
_CACHE_TIMESTAMP: float = 0.0


def _find_vscode() -> Optional[str]:
    """Mencari lokasi binary executable Visual Studio Code."""
    if sys.platform == "win32":
        # Cek lokasi file .exe langsung
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("code")
        if found and os.path.isfile(found):
            return found
    elif sys.platform == "darwin":
        mac_candidates = [
            "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
            os.path.expanduser("~/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
        ]
        for c in mac_candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("code")
        if found:
            return found
    else:
        found = shutil.which("code")
        if found:
            return found
    return None


def _find_cursor() -> Optional[str]:
    """Mencari executable Cursor AI Editor."""
    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe"),
            r"C:\Program Files\Cursor\Cursor.exe",
            r"C:\Program Files (x86)\Cursor\Cursor.exe",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("cursor")
        if found and os.path.isfile(found):
            return found
    elif sys.platform == "darwin":
        mac_candidates = [
            "/Applications/Cursor.app/Contents/MacOS/Cursor",
            os.path.expanduser("~/Applications/Cursor.app/Contents/MacOS/Cursor"),
        ]
        for c in mac_candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("cursor")
        if found:
            return found
    else:
        found = shutil.which("cursor")
        if found:
            return found
    return None


def _find_windsurf() -> Optional[str]:
    """Mencari executable Windsurf Editor."""
    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\windsurf\Windsurf.exe"),
            r"C:\Program Files\Windsurf\Windsurf.exe",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("windsurf")
        if found and os.path.isfile(found):
            return found
    elif sys.platform == "darwin":
        mac_candidates = [
            "/Applications/Windsurf.app/Contents/MacOS/Windsurf",
            os.path.expanduser("~/Applications/Windsurf.app/Contents/MacOS/Windsurf"),
        ]
        for c in mac_candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("windsurf")
        if found:
            return found
    return None


def _find_sublime() -> Optional[str]:
    """Mencari executable Sublime Text."""
    if sys.platform == "win32":
        candidates = [
            r"C:\Program Files\Sublime Text\sublime_text.exe",
            r"C:\Program Files\Sublime Text 3\sublime_text.exe",
            r"C:\Program Files (x86)\Sublime Text 3\sublime_text.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Sublime Text\sublime_text.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("subl") or shutil.which("sublime_text")
        if found and os.path.isfile(found):
            return found
    elif sys.platform == "darwin":
        mac_candidates = [
            "/Applications/Sublime Text.app/Contents/SharedSupport/bin/subl",
            os.path.expanduser("~/Applications/Sublime Text.app/Contents/SharedSupport/bin/subl"),
        ]
        for c in mac_candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("subl")
        if found:
            return found
    else:
        found = shutil.which("subl") or shutil.which("sublime_text")
        if found:
            return found
    return None


def _find_notepadpp() -> Optional[str]:
    """Mencari executable Notepad++ di Windows."""
    if sys.platform != "win32":
        return None
    candidates = [
        r"C:\Program Files\Notepad++\notepad++.exe",
        r"C:\Program Files (x86)\Notepad++\notepad++.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Notepad++\notepad++.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    found = shutil.which("notepad++")
    if found and os.path.isfile(found):
        return found
    return None


def _find_notepad() -> Optional[str]:
    """Mencari executable Notepad bawaan Windows."""
    if sys.platform != "win32":
        return None
    candidates = [
        r"C:\Windows\notepad.exe",
        r"C:\Windows\System32\notepad.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    found = shutil.which("notepad")
    if found and os.path.isfile(found):
        return found
    return None


def _find_zed() -> Optional[str]:
    """Mencari executable Zed Editor."""
    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Zed\Zed.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("zed")
        if found and os.path.isfile(found):
            return found
    elif sys.platform == "darwin":
        mac_candidates = [
            "/Applications/Zed.app/Contents/MacOS/Zed",
            os.path.expanduser("~/Applications/Zed.app/Contents/MacOS/Zed"),
        ]
        for c in mac_candidates:
            if os.path.isfile(c):
                return c
        found = shutil.which("zed")
        if found:
            return found
    else:
        found = shutil.which("zed")
        if found:
            return found
    return None


class EditorService:
    """Service terpusat untuk deteksi, konfigurasi, dan eksekusi teks editor untuk File Manager."""

    SETTING_DEFAULT_EDITOR = "file_editor_choice"
    SETTING_CUSTOM_PATH = "file_editor_custom_path"
    SETTING_AUTO_SYNC = "file_editor_auto_sync"
    SETTING_SHOW_NOTIF = "file_editor_show_notifications"

    # Registry watcher aktif untuk auto-sync
    _ACTIVE_WATCHERS: Dict[str, "RemoteFileWatcher"] = {}
    _WATCHER_LOCK = threading.Lock()

    @classmethod
    def get_detected_editors(cls, custom_path: Optional[str] = None, force_refresh: bool = False) -> List[EditorInfo]:
        """Mendeteksi semua aplikasi teks editor yang tersedia pada komputer pengguna."""
        global _DETECTED_EDITORS_CACHE, _CACHE_TIMESTAMP

        now = time.time()
        if not force_refresh and _DETECTED_EDITORS_CACHE is not None and (now - _CACHE_TIMESTAMP) < 60:
            # Update custom editor if path provided
            editors = list(_DETECTED_EDITORS_CACHE)
            if custom_path:
                cls._update_custom_editor(editors, custom_path)
            return editors

        editors: List[EditorInfo] = []

        # 1. Built-in In-App Editor (Always available)
        editors.append(EditorInfo(
            id="builtin",
            name="Pullman Built-in Editor",
            executable=None,
            is_available=True,
            icon_name="file-code",
            description="Editor bawaan Pullman dengan multi-tab, line numbers, dan syntax highlighting modern."
        ))

        # 2. Visual Studio Code
        vsc_path = _find_vscode()
        editors.append(EditorInfo(
            id="vscode",
            name="Visual Studio Code",
            executable=vsc_path,
            is_available=vsc_path is not None,
            icon_name="file-code",
            description=f"Editor kode populer Microsoft ({vsc_path if vsc_path else 'Tidak terdeteksi'})."
        ))

        # 3. Cursor
        cursor_path = _find_cursor()
        editors.append(EditorInfo(
            id="cursor",
            name="Cursor",
            executable=cursor_path,
            is_available=cursor_path is not None,
            icon_name="sparkles",
            description=f"AI-first code editor berbasis VS Code ({cursor_path if cursor_path else 'Tidak terdeteksi'})."
        ))

        # 4. Windsurf
        windsurf_path = _find_windsurf()
        if windsurf_path or sys.platform == "win32":
            editors.append(EditorInfo(
                id="windsurf",
                name="Windsurf",
                executable=windsurf_path,
                is_available=windsurf_path is not None,
                icon_name="sparkles",
                description=f"AI-powered editor Codeium ({windsurf_path if windsurf_path else 'Tidak terdeteksi'})."
            ))

        # 5. Notepad++ (Khusus Windows)
        if sys.platform == "win32":
            npp_path = _find_notepadpp()
            editors.append(EditorInfo(
                id="notepadpp",
                name="Notepad++",
                executable=npp_path,
                is_available=npp_path is not None,
                icon_name="file-text",
                description=f"Editor teks ringan & serbaguna ({npp_path if npp_path else 'Tidak terdeteksi'})."
            ))

        # 6. Sublime Text
        subl_path = _find_sublime()
        editors.append(EditorInfo(
            id="sublime",
            name="Sublime Text",
            executable=subl_path,
            is_available=subl_path is not None,
            icon_name="file-text",
            description=f"Editor teks berkecepatan tinggi ({subl_path if subl_path else 'Tidak terdeteksi'})."
        ))

        # 7. Zed Editor
        zed_path = _find_zed()
        if zed_path or sys.platform in ("darwin", "win32"):
            editors.append(EditorInfo(
                id="zed",
                name="Zed",
                executable=zed_path,
                is_available=zed_path is not None,
                icon_name="zap",
                description=f"Editor performa tinggi generasi baru ({zed_path if zed_path else 'Tidak terdeteksi'})."
            ))

        # 8. Windows Notepad (Khusus Windows)
        if sys.platform == "win32":
            notepad_path = _find_notepad()
            editors.append(EditorInfo(
                id="notepad",
                name="Windows Notepad",
                executable=notepad_path,
                is_available=notepad_path is not None,
                icon_name="file-text",
                description=f"Aplikasi Notepad bawaan Windows ({notepad_path if notepad_path else 'Tidak terdeteksi'})."
            ))

        # 9. System Default Application
        editors.append(EditorInfo(
            id="system",
            name="Aplikasi Bawaan Sistem (System Default)",
            executable=None,
            is_available=True,
            icon_name="external-link",
            description="Buka menggunakan aplikasi default asosiasi file sistem operasi."
        ))

        # 10. Custom Editor Executable
        custom_exec = custom_path if (custom_path and os.path.isfile(custom_path)) else None
        editors.append(EditorInfo(
            id="custom",
            name="Custom Text Editor...",
            executable=custom_exec,
            is_available=custom_exec is not None,
            icon_name="settings",
            description="Gunakan file binary/executable (.exe) pilihan Anda sendiri."
        ))

        _DETECTED_EDITORS_CACHE = editors
        _CACHE_TIMESTAMP = now
        return editors

    @classmethod
    def _update_custom_editor(cls, editors: List[EditorInfo], custom_path: str):
        for ed in editors:
            if ed.id == "custom":
                is_valid = bool(custom_path and os.path.isfile(custom_path))
                ed.executable = custom_path if is_valid else None
                ed.is_available = is_valid
                ed.description = f"Lokasi: {custom_path}" if is_valid else "File executable belum ditentukan."
                break

    @classmethod
    def get_settings(cls, db: Optional[Any] = None) -> Dict[str, Any]:
        """Ambil konfigurasi teks editor dari database (atau default jika belum diatur)."""
        default_choice = "builtin"
        custom_path = ""
        auto_sync = True
        show_notif = True

        if db:
            try:
                saved_choice = db.get_setting(cls.SETTING_DEFAULT_EDITOR)
                if saved_choice:
                    default_choice = saved_choice
                saved_custom = db.get_setting(cls.SETTING_CUSTOM_PATH)
                if saved_custom:
                    custom_path = saved_custom
                saved_sync = db.get_setting(cls.SETTING_AUTO_SYNC)
                if saved_sync is not None:
                    auto_sync = (saved_sync == "1")
                saved_notif = db.get_setting(cls.SETTING_SHOW_NOTIF)
                if saved_notif is not None:
                    show_notif = (saved_notif == "1")
            except Exception:
                pass

        return {
            "default_editor": default_choice,
            "custom_path": custom_path,
            "auto_sync": auto_sync,
            "show_notifications": show_notif
        }

    @classmethod
    def save_settings(
        cls,
        db: Optional[Any],
        default_editor: str,
        custom_path: str = "",
        auto_sync: bool = True,
        show_notifications: bool = True
    ) -> None:
        """Simpan konfigurasi teks editor ke database."""
        if not db:
            return
        try:
            db.set_setting(cls.SETTING_DEFAULT_EDITOR, default_editor)
            db.set_setting(cls.SETTING_CUSTOM_PATH, custom_path.strip())
            db.set_setting(cls.SETTING_AUTO_SYNC, "1" if auto_sync else "0")
            db.set_setting(cls.SETTING_SHOW_NOTIF, "1" if show_notifications else "0")
        except Exception:
            pass

    @classmethod
    def get_active_editor_info(cls, db: Optional[Any] = None) -> EditorInfo:
        """Mengambil data EditorInfo untuk editor yang saat ini aktif/dipilih pengguna."""
        settings = cls.get_settings(db)
        choice = settings["default_editor"]
        custom_path = settings["custom_path"]

        editors = cls.get_detected_editors(custom_path=custom_path)
        active = next((e for e in editors if e.id == choice), None)
        if active and active.is_available:
            active.is_default = True
            return active

        # Fallback ke Built-in jika editor terpilih tidak lagi tersedia
        builtin = next((e for e in editors if e.id == "builtin"), None)
        if builtin:
            builtin.is_default = True
            return builtin
        return editors[0]

    @classmethod
    def get_editor_by_id(cls, editor_id: str, db: Optional[Any] = None) -> Optional[EditorInfo]:
        """Mencari data EditorInfo berdasarkan ID."""
        settings = cls.get_settings(db)
        editors = cls.get_detected_editors(custom_path=settings["custom_path"])
        return next((e for e in editors if e.id == editor_id), None)

    # ------------------------------------------------------------------
    # Process Launching & Execution
    # ------------------------------------------------------------------

    @classmethod
    def launch_external_editor(cls, editor: EditorInfo, file_path: str) -> Tuple[bool, Optional[str]]:
        """Membuka file lokal menggunakan executable teks editor eksternal."""
        abs_path = os.path.abspath(file_path)

        if editor.id == "system" or not editor.executable:
            try:
                if sys.platform == "win32":
                    os.startfile(abs_path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", abs_path])
                else:
                    subprocess.Popen(["xdg-open", abs_path])
                return True, None
            except Exception as e:
                return False, f"Gagal membuka aplikasi sistem: {e}"

        exe = editor.executable
        try:
            if sys.platform == "win32":
                # Jika .cmd atau .bat, jalankan dengan shell=True
                if exe.lower().endswith((".cmd", ".bat")):
                    subprocess.Popen(f'"{exe}" "{abs_path}"', shell=True)
                else:
                    subprocess.Popen([exe, abs_path])
            elif sys.platform == "darwin":
                if exe.endswith(".app"):
                    subprocess.Popen(["open", "-a", exe, abs_path])
                else:
                    subprocess.Popen([exe, abs_path])
            else:
                subprocess.Popen([exe, abs_path])
            return True, None
        except Exception as e:
            return False, f"Gagal menjalankan editor '{editor.name}': {e}"

    # ------------------------------------------------------------------
    # Local & Remote File Opening Flow
    # ------------------------------------------------------------------

    @classmethod
    def open_local_file(
        cls,
        parent: Any,
        file_path: str,
        editor_id: Optional[str] = None,
        db: Optional[Any] = None,
        on_saved_callback: Optional[Callable[[], None]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Membuka file lokal dengan teks editor yang dipilih atau default."""
        if not editor_id:
            editor = cls.get_active_editor_info(db)
        else:
            editor = cls.get_editor_by_id(editor_id, db) or cls.get_active_editor_info(db)

        if editor.id == "builtin":
            # Buka di in-app editor Pullman
            from ui.file_editor_dialog import FileEditorDialog
            try:
                FileEditorDialog.open_file(
                    parent=parent,
                    host=None,
                    remote_file_path=os.path.abspath(file_path),
                    as_sudo=False,
                    on_saved_callback=on_saved_callback
                )
                return True, None
            except Exception as e:
                return False, str(e)
        else:
            return cls.launch_external_editor(editor, file_path)

    @classmethod
    def open_remote_file(
        cls,
        parent: Any,
        host: Dict[str, Any],
        remote_file_path: str,
        as_sudo: bool = False,
        editor_id: Optional[str] = None,
        db: Optional[Any] = None,
        on_saved_callback: Optional[Callable[[], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Membuka file remote SFTP:
        - Jika editor == 'builtin': Membuka langsung di FileEditorDialog in-app.
        - Jika editor eksternal: Mendownload file ke local temporary cache, membuka di editor eksternal,
          dan mengaktifkan background file watcher untuk auto-sync setiap kali file disimpan di editor.
        """
        if not editor_id:
            editor = cls.get_active_editor_info(db)
        else:
            editor = cls.get_editor_by_id(editor_id, db) or cls.get_active_editor_info(db)

        # 1. Kasus In-App Editor
        if editor.id == "builtin":
            from ui.file_editor_dialog import FileEditorDialog
            try:
                FileEditorDialog.open_file(
                    parent=parent,
                    host=host,
                    remote_file_path=remote_file_path,
                    as_sudo=as_sudo,
                    on_saved_callback=on_saved_callback
                )
                return True, None
            except Exception as e:
                return False, str(e)

        # 2. Kasus Editor Eksternal: Download ke cache lokal & buka
        settings = cls.get_settings(db)
        auto_sync = settings.get("auto_sync", True)
        show_notif = settings.get("show_notifications", True)

        host_id = host.get("id") or host.get("hostname") or "temp"
        host_slug = f"host_{host_id}_{host.get('hostname', 'server')}".replace(":", "_").replace("@", "_")
        clean_rel = remote_file_path.lstrip("/").replace(":", "_")
        cache_base = os.path.join(tempfile.gettempdir(), "pullman_editor_cache", host_slug)
        local_cache_path = os.path.join(cache_base, clean_rel)

        os.makedirs(os.path.dirname(local_cache_path), exist_ok=True)

        if status_callback:
            status_callback(f"Mengunduh file remote '{os.path.basename(remote_file_path)}' untuk {editor.name}...")

        def download_and_launch():
            try:
                # Unduh file remote ke lokal
                if as_sudo:
                    ok, content, err = SFTPService.read_file_sudo(host, remote_file_path)
                    if ok:
                        with open(local_cache_path, "w", encoding="utf-8", errors="replace") as f:
                            f.write(content)
                    else:
                        raise RuntimeError(err or "Gagal membaca file dengan sudo")
                else:
                    ok, err = SFTPService.download_file(host, remote_file_path, local_cache_path)
                    if not ok:
                        # Fallback jika izin read biasa gagal tapi user punya akses
                        ok_txt, content, err_txt = SFTPService.read_file_text(host, remote_file_path)
                        if ok_txt:
                            with open(local_cache_path, "w", encoding="utf-8", errors="replace") as f:
                                f.write(content)
                        else:
                            raise RuntimeError(err or err_txt or "Gagal mengunduh file remote")

                # Jalankan editor eksternal
                ok_launch, err_launch = cls.launch_external_editor(editor, local_cache_path)
                if not ok_launch:
                    raise RuntimeError(err_launch or "Gagal menjalankan executable editor")

                if status_callback:
                    parent.after(0, lambda: status_callback(f"Terbuka di {editor.name}: {os.path.basename(remote_file_path)}"))

                # Aktifkan auto-sync background watcher jika diaktifkan
                if auto_sync:
                    cls._register_watcher(
                        parent=parent,
                        host=host,
                        remote_path=remote_file_path,
                        local_path=local_cache_path,
                        as_sudo=as_sudo,
                        editor_name=editor.name,
                        show_notif=show_notif,
                        on_saved_callback=on_saved_callback,
                        status_callback=status_callback
                    )

            except Exception as e:
                err_msg = str(e)
                if status_callback:
                    parent.after(0, lambda: status_callback(f"Error membuka file: {err_msg}"))
                from tkinter import messagebox
                parent.after(0, lambda: messagebox.showerror("Error Editor", f"Gagal membuka file di {editor.name}:\n\n{err_msg}"))

        threading.Thread(target=download_and_launch, daemon=True).start()
        return True, None

    @classmethod
    def _register_watcher(
        cls,
        parent: Any,
        host: Dict[str, Any],
        remote_path: str,
        local_path: str,
        as_sudo: bool,
        editor_name: str,
        show_notif: bool,
        on_saved_callback: Optional[Callable[[], None]],
        status_callback: Optional[Callable[[str], None]]
    ):
        """Mendaftarkan watcher untuk sinkronisasi otomatis saat file lokal disimpan."""
        key = f"{host.get('id', host.get('hostname'))}:{remote_path}"
        with cls._WATCHER_LOCK:
            existing = cls._ACTIVE_WATCHERS.get(key)
            if existing and existing.is_alive():
                existing.update_callbacks(on_saved_callback, status_callback)
                return

            watcher = RemoteFileWatcher(
                parent=parent,
                host=host,
                remote_path=remote_path,
                local_path=local_path,
                as_sudo=as_sudo,
                editor_name=editor_name,
                show_notif=show_notif,
                on_saved_callback=on_saved_callback,
                status_callback=status_callback
            )
            cls._ACTIVE_WATCHERS[key] = watcher
            watcher.start()


class RemoteFileWatcher(threading.Thread):
    """
    Background Thread yang memantau perubahan waktu modifikasi (mtime) pada file cache lokal.
    Ketika user menekan Ctrl+S di VS Code / Sublime / Notepad++ dll, file akan otomatis diupload
    kembali ke server SFTP (Auto-Sync on Save).
    """

    def __init__(
        self,
        parent: Any,
        host: Dict[str, Any],
        remote_path: str,
        local_path: str,
        as_sudo: bool = False,
        editor_name: str = "Editor",
        show_notif: bool = True,
        on_saved_callback: Optional[Callable[[], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ):
        super().__init__(daemon=True)
        self.parent = parent
        self.host = host
        self.remote_path = remote_path
        self.local_path = local_path
        self.as_sudo = as_sudo
        self.editor_name = editor_name
        self.show_notif = show_notif
        self.on_saved_callback = on_saved_callback
        self.status_callback = status_callback
        self.last_mtime = self._get_current_mtime()
        self.running = True
        self.filename = os.path.basename(remote_path)

    def _get_current_mtime(self) -> float:
        try:
            return os.path.getmtime(self.local_path)
        except Exception:
            return 0.0

    def update_callbacks(self, on_saved: Optional[Callable[[], None]], status: Optional[Callable[[str], None]]):
        if on_saved:
            self.on_saved_callback = on_saved
        if status:
            self.status_callback = status

    def stop(self):
        self.running = False

    def run(self):
        idle_count = 0
        while self.running:
            time.sleep(1.2)
            if not os.path.exists(self.local_path):
                break

            current_mtime = self._get_current_mtime()
            if current_mtime > self.last_mtime + 0.1:
                # Beri sedikit jeda 0.3 detik agar editor eksternal tuntas menulis file ke disk
                time.sleep(0.3)
                self.last_mtime = self._get_current_mtime()

                # Upload perubahan ke server remote
                self._upload_changes()

            # Setiap interval waktu panjang (misal 30 menit tanpa perubahan), watcher tetap jalan di background
            idle_count += 1

    def _upload_changes(self):
        filename = self.filename
        try:
            if self.status_callback:
                self.parent.after(0, lambda: self.status_callback(f"Menyinkronkan '{filename}' ke server..."))

            if self.as_sudo:
                with open(self.local_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                ok, err = SFTPService.write_file_sudo(self.host, self.remote_path, content)
            else:
                ok, err = SFTPService.upload_file(self.host, self.local_path, self.remote_path)

            if ok:
                msg = f"File remote '{filename}' berhasil disinkronkan dari {self.editor_name}."
                if self.status_callback:
                    self.parent.after(0, lambda: self.status_callback(msg))

                if self.on_saved_callback:
                    self.parent.after(0, self.on_saved_callback)

                # Notifikasi jika diaktifkan
                if self.show_notif:
                    host_label = self.host.get("label") or self.host.get("hostname") or "Server"
                    self._notify_success(f"Sinkronisasi Selesai", f"'{filename}' berhasil diperbarui di {host_label}.")
            else:
                err_msg = f"Gagal sinkronisasi '{filename}': {err}"
                if self.status_callback:
                    self.parent.after(0, lambda: self.status_callback(err_msg))
                from tkinter import messagebox
                self.parent.after(0, lambda: messagebox.showerror("Gagal Sinkronisasi", f"{err_msg}"))

        except Exception as e:
            if self.status_callback:
                self.parent.after(0, lambda: self.status_callback(f"Error sinkronisasi: {e}"))

    def _notify_success(self, title: str, message: str):
        try:
            if hasattr(self.parent, "toasts") and self.parent.toasts:
                self.parent.after(0, lambda: self.parent.toasts.success(title, message))
            else:
                send_os_notification(title, message)
        except Exception:
            pass
