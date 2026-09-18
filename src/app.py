from PIL import ExifTags
import os
os.environ['TK_SILENCE_DEPRECATION'] = '1'

import asyncio
import re
import threading
import webbrowser
import sys
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox
from database import DatabaseManager
from ui.host_dialog import HostDialog
from ui.export_dialog import ExportDialog
from ui.import_dialog import ImportDialog
from ui.git_credential_dialog import GitCredentialDialog
from ui.db_blast_view import DBBlastView
from update_service import check_for_update
from ssh_client import SSHConnection
from PIL import ImageTk, Image
from ui.terminal_window import TerminalWindow

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


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

APP_VERSION = "1.0.0"
APP_NAME = "DO.MBA Pull Manager"


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


class TerbiusApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        data_path = application_data_path()
        self.db = DatabaseManager(
            str(data_path / "pullManager.db"),
            str(data_path / ".master.key")
        )

        self.selected_host_ids = set()
        self.host_checkbox_vars = {}

        self.title(f"DO.MBA - Pull Manager v{APP_VERSION}")
        self.geometry("1080x680")
        self.minsize(900, 560)
        # Set AppUserModelID agar icon taskbar Windows muncul terpisah & berikon
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("domba.pullmanager.ssh.app")
            except Exception:
                pass

        # Pasang icon aplikasi (Window Titlebar & Taskbar)
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

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._setup_sidebar()
        self._setup_main_content()
        self.db_blast_frame = DBBlastView(self, self.db)
        self._refresh_hosts_list()

    def _setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=224, corner_radius=0, fg_color=COLORS["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_rowconfigure(4, weight=1)  # row 4 = spacer
        self.sidebar.grid_columnconfigure(0, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=18, pady=(25, 30), sticky="w")
        try:
            logo_path1 = resource_path("assets/icon_512x512.png")
            logo_path2 = resource_path("src/assets/icon_512x512.png")
            if logo_path1.exists():
                pil_logo = Image.open(logo_path1)
                self.brand_icon = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(35, 35))
                ctk.CTkLabel(brand, text="", image=self.brand_icon).pack(side="left", padx=(0, 9))
            elif logo_path2.exists():
                pil_logo = Image.open(logo_path2)
                self.brand_icon = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(35, 35))
                ctk.CTkLabel(brand, text="", image=self.brand_icon).pack(side="left", padx=(0, 9))
            else:
                ctk.CTkLabel(brand, text="D", width=35, height=35, corner_radius=9, fg_color=COLORS["accent"], font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=(0, 9))
        except Exception:
            ctk.CTkLabel(brand, text="D", width=35, height=35, corner_radius=9, fg_color=COLORS["accent"], font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=(0, 9))

        brand_copy = ctk.CTkFrame(brand, fg_color="transparent")
        brand_copy.pack(side="left")
        ctk.CTkLabel(brand_copy, text="DO.MBA", text_color=COLORS["text"], font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(brand_copy, text="DEPLOYMENT CONSOLE", text_color=COLORS["muted"], font=ctk.CTkFont(size=8, weight="bold")).pack(anchor="w")

        self.btn_hosts = ctk.CTkButton(
            self.sidebar, text="Pull Blast", anchor="w",
            height=38, corner_radius=9, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], text_color=COLORS["text"],
            command=self._show_hosts_view
        )
        self.btn_hosts.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.btn_db_blast = ctk.CTkButton(
            self.sidebar, text="DB Blast", anchor="w",
            height=38, corner_radius=9, fg_color="transparent", hover_color=COLORS["surface_hover"], text_color=COLORS["text"],
            command=self._show_db_blast_view
        )
        self.btn_db_blast.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        btn_git_credential = ctk.CTkButton(
            self.sidebar, text="⌘  Git Credential", anchor="w",
            height=34, corner_radius=8, fg_color="transparent", hover_color=COLORS["surface_hover"],
            command=self._open_git_credential_dialog
        )
        btn_git_credential.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Spacer keeps data actions aligned with the lower edge of the window.
        ctk.CTkLabel(self.sidebar, text="").grid(row=4, column=0)
        ctk.CTkLabel(self.sidebar, text="DATA", text_color=COLORS["muted"], font=ctk.CTkFont(size=10, weight="bold")).grid(row=5, column=0, padx=20, pady=(0, 5), sticky="w")

        # --- Bottom: Import / Export Buttons ---
        btn_import = ctk.CTkButton(
            self.sidebar,
            text="⬇  Import",
            height=34, corner_radius=8, fg_color="transparent", hover_color=COLORS["surface_hover"],
            anchor="w",
            command=self._open_import_dialog
        )
        btn_import.grid(row=6, column=0, padx=10, pady=5, sticky="ew")

        btn_export = ctk.CTkButton(
            self.sidebar,
            text="⬆  Export",
            height=34, corner_radius=8, fg_color="transparent", hover_color=COLORS["surface_hover"],
            anchor="w",
            command=self._open_export_dialog
        )
        btn_export.grid(row=7, column=0, padx=10, pady=(5, 10), sticky="ew")

        btn_update = ctk.CTkButton(
            self.sidebar,
            text="↻  Check for Updates",
            height=34, corner_radius=8, fg_color="transparent", hover_color=COLORS["surface_hover"],
            anchor="w", command=self._check_for_updates
        )
        btn_update.grid(row=8, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.btn_update = btn_update

        footer_label = ctk.CTkLabel(
            self.sidebar,
            text="Vibe Code \n By DO.MBA Devs",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["muted"]
        )
        footer_label.grid(row=9, column=0, padx=10, pady=(0, 12), sticky="ew")

    def _setup_main_content(self):
        self.main_frame = ctk.CTkFrame(self, fg_color=COLORS["window"])
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        self.main_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)
        header.grid_columnconfigure(2, weight=0)
        header.grid_columnconfigure(3, weight=0)

        title = ctk.CTkLabel(header, text="Servers", text_color=COLORS["text"], font=ctk.CTkFont(size=28, weight="bold"))
        title.grid(row=0, column=0, sticky="w")

        # Filter Group Frame
        filter_frame = ctk.CTkFrame(header, fg_color="transparent")
        filter_frame.grid(row=0, column=1, sticky="e", padx=(0, 10))

        lbl_filter = ctk.CTkLabel(filter_frame, text="Group", text_color=COLORS["muted"], font=ctk.CTkFont(size=12))
        lbl_filter.pack(side="left", padx=(0, 5))

        self.filter_group_opt = ctk.CTkOptionMenu(
            filter_frame,
            values=["All Groups"],
            width=140,
            height=34,
            corner_radius=8,
            fg_color=COLORS["surface"],
            button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"],
            command=self._on_filter_changed
        )
        self.filter_group_opt.pack(side="left")

        self.chk_all_var = ctk.BooleanVar(value=False)
        self.chk_all = ctk.CTkCheckBox(
            filter_frame,
            text="Check All",
            variable=self.chk_all_var,
            width=22,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=5,
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._toggle_check_all
        )
        self.chk_all.pack(side="left", padx=(14, 0))

        btn_new_host = ctk.CTkButton(header, text="+  New Host", width=112, height=34, corner_radius=8, fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"], command=self._add_host_dialog)
        btn_new_host.grid(row=0, column=2, sticky="e", padx=(5, 0))

        self.btn_run_all = ctk.CTkButton(header, text="Run All", width=100, height=34, corner_radius=8, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._run_all_hosts)
        self.btn_run_all.grid(row=0, column=3, sticky="e", padx=(5, 0))

        # --- Search Bar ---
        search_frame = ctk.CTkFrame(self.main_frame, fg_color=COLORS["surface"], corner_radius=10)
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        search_frame.grid_columnconfigure(1, weight=1)

        lbl_search = ctk.CTkLabel(search_frame, text="⌕", text_color=COLORS["muted"], font=ctk.CTkFont(size=22))
        lbl_search.grid(row=0, column=0, padx=(0, 6))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_hosts_list())

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Cari host berdasarkan nama...",
            textvariable=self.search_var,
            height=38, corner_radius=8, border_width=0, fg_color="transparent", text_color=COLORS["text"], placeholder_text_color=COLORS["muted"]
        )
        self.search_entry.grid(row=0, column=1, sticky="ew")

        self.hosts_scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent", corner_radius=0)
        self.hosts_scroll.grid(row=2, column=0, sticky="nsew")
        self.main_frame.grid_rowconfigure(2, weight=1)

        self.output_textbox = ctk.CTkTextbox(self.main_frame, font=("Menlo", 12), wrap="none", height=155, corner_radius=10, border_width=1, border_color=COLORS["line"], fg_color="#17181C", text_color="#D1D5DB")
        self.output_textbox.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        self.main_frame.grid_rowconfigure(3, weight=0)

    def _refresh_filter_options(self):
        """Memperbarui daftar opsi filter grup di header."""
        groups = self.db.get_groups()
        group_names = ["All Groups"] + [g["name"] for g in groups]
        current_val = self.filter_group_opt.get() if hasattr(self, 'filter_group_opt') else "All Groups"
        if hasattr(self, 'filter_group_opt'):
            self.filter_group_opt.configure(values=group_names)
            if current_val in group_names:
                self.filter_group_opt.set(current_val)
            else:
                self.filter_group_opt.set("All Groups")

    def _on_filter_changed(self, selected_group: str):
        self._render_hosts_list()

    def _set_active_nav(self, active_btn):
        """Reset semua tombol nav ke transparan, lalu aktifkan yang dipilih."""
        self.btn_hosts.configure(fg_color="transparent")
        if hasattr(self, 'btn_db_blast'):
            self.btn_db_blast.configure(fg_color="transparent")
        active_btn.configure(fg_color=COLORS["accent"])

    def _show_hosts_view(self):
        """Tampilkan kembali tampilan Hosts dan refresh daftar."""
        self._set_active_nav(self.btn_hosts)
        if hasattr(self, 'db_blast_frame'):
            self.db_blast_frame.grid_remove()
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        self._refresh_hosts_list()

    def _show_db_blast_view(self):
        """Tampilkan tampilan DB Blast bergaya Navicat (Instant Switch)."""
        self._set_active_nav(self.btn_db_blast)
        self.main_frame.grid_remove()
        self.db_blast_frame.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        if not getattr(self.db_blast_frame, '_is_loaded', False):
            self.db_blast_frame._refresh_connections()

    def _bind_mousewheel(self, widget):
        """Rekursif bind event scroll trackpad/mouse ke semua child widget di CTkScrollableFrame."""
        canvas = self.hosts_scroll._parent_canvas

        def _scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 60)), "units")

        widget.bind("<MouseWheel>", _scroll, add="+")
        for child in widget.winfo_children():
            self._bind_mousewheel(child)

    def _refresh_hosts_list(self):
        """Memuat ulang data dan merender daftar host dari SQLite."""
        self._refresh_filter_options()
        self._render_hosts_list()
        self.after(50, lambda: self._bind_mousewheel(self.hosts_scroll))

    def _toggle_check_all(self):
        """Centang atau lepas centang semua host yang sedang tampil."""
        is_checked = self.chk_all_var.get()
        for host_id, var in self.host_checkbox_vars.items():
            var.set(is_checked)
            if is_checked:
                self.selected_host_ids.add(host_id)
            else:
                self.selected_host_ids.discard(host_id)
        self._update_run_button_text()

    def _on_host_checked(self, host_id: int):
        """Handler saat checkbox host individual diubah."""
        var = self.host_checkbox_vars.get(host_id)
        if var:
            if var.get():
                self.selected_host_ids.add(host_id)
            else:
                self.selected_host_ids.discard(host_id)

        # Update status Check All jika semua tercentang
        if self.host_checkbox_vars:
            all_checked = all(v.get() for v in self.host_checkbox_vars.values())
            self.chk_all_var.set(all_checked)
        else:
            self.chk_all_var.set(False)

        self._update_run_button_text()

    def _update_run_button_text(self):
        """Perbarui label tombol run all / pull selected."""
        count = len([hid for hid in self.selected_host_ids if hid in self.host_checkbox_vars])
        selected_filter = self.filter_group_opt.get() if hasattr(self, 'filter_group_opt') else "All Groups"
        if count > 0:
            self.btn_run_all.configure(text=f"Pull Selected ({count})")
        else:
            if selected_filter == "All Groups":
                self.btn_run_all.configure(text="Run All")
            else:
                self.btn_run_all.configure(text=f"Run All ({selected_filter})")

    def _render_hosts_list(self):
        """Merender daftar host sesuai filter grup dan kata kunci pencarian."""
        for widget in self.hosts_scroll.winfo_children():
            widget.destroy()

        self.host_checkbox_vars.clear()

        all_hosts = self.db.get_all_hosts()
        selected_filter = self.filter_group_opt.get() if hasattr(self, 'filter_group_opt') else "All Groups"
        search_query = self.search_var.get().strip().lower() if hasattr(self, 'search_var') else ""

        if selected_filter == "All Groups":
            hosts = all_hosts
        else:
            hosts = [h for h in all_hosts if h.get("group_name") == selected_filter]

        # Filter berdasarkan search query
        if search_query:
            hosts = [h for h in hosts if search_query in h.get("label", "").lower()]

        if not hosts:
            self.chk_all_var.set(False)
            self._update_run_button_text()
            if not all_hosts:
                msg = "Belum ada host tersimpan. Klik '+ New Host' untuk menambahkan."
            else:
                msg = f"No host at group '{selected_filter}'."
            lbl_empty = ctk.CTkLabel(
                self.hosts_scroll, 
                text=msg,
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=13)
            )
            lbl_empty.pack(pady=42)
            return

        for host in hosts:
            self._create_host_card(host)

        # Sinkronkan status Check All
        if self.host_checkbox_vars:
            all_checked = all(v.get() for v in self.host_checkbox_vars.values())
            self.chk_all_var.set(all_checked)
        else:
            self.chk_all_var.set(False)

        self._update_run_button_text()

    def _create_host_card(self, host: dict):
        card = ctk.CTkFrame(
            self.hosts_scroll, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["line"]
        )
        card.pack(fill="x", padx=2, pady=5)

        # 4. Checkbox untuk memilih host
        is_selected = host['id'] in self.selected_host_ids
        chk_var = ctk.BooleanVar(value=is_selected)
        self.host_checkbox_vars[host['id']] = chk_var

        chk = ctk.CTkCheckBox(
            card,
            text="",
            variable=chk_var,
            width=22,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=5,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=lambda h_id=host['id']: self._on_host_checked(h_id)
        )
        chk.pack(side="left", padx=(14, 0))

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", padx=(10, 15), pady=13)

        # Baris Header: Label Host + Badge Group
        title_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        title_row.pack(anchor="w")

        lbl_name = ctk.CTkLabel(title_row, text=host['label'], text_color=COLORS["text"], font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        lbl_name.pack(side="left")

        if host.get('group_name'):
            lbl_group_badge = ctk.CTkLabel(
                title_row,
                text=host['group_name'],
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#12355F",
                text_color="#8DC6FF",
                corner_radius=7,
                padx=8,
                pady=2
            )
            lbl_group_badge.pack(side="left", padx=(10, 0))

        branch_str = f"  •  Branch: {host['git_branch']}" if host.get('git_branch') else ""
        target_str = f"{host['username']}@{host['hostname']}:{host['port']} {branch_str}"
        lbl_target = ctk.CTkLabel(info_frame, text=target_str, text_color=COLORS["muted"], font=ctk.CTkFont(size=11), anchor="w")
        lbl_target.pack(anchor="w", pady=(3, 0))

        # Tombol aksi (Pack side='right' sehingga urutan dari kiri ke kanan rapi)
        # Tombol Delete
        btn_delete = ctk.CTkButton(
            card, 
            text="Delete", 
            width=58, height=30, corner_radius=7,
            fg_color="transparent", 
            border_width=1, 
            border_color="#71322E",
            text_color=COLORS["danger"],
            hover_color="#3B2223",
            command=lambda: self._delete_host(host['id'])
        )
        btn_delete.pack(side="right", padx=(4, 14), pady=10)

        # Tombol Edit
        btn_edit = ctk.CTkButton(
            card,
            text="Edit",
            width=52, height=30, corner_radius=7,
            fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"],
            command=lambda h=host: self._edit_host_dialog(h)
        )
        btn_edit.pack(side="right", padx=4, pady=10)

        # 3. Tombol Terminal (PuTTY / Command Prompt untuk akses manual)
        btn_terminal = ctk.CTkButton(
            card,
            text="Terminal",
            width=70, height=30, corner_radius=7,
            fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"],
            command=lambda h=host: self._open_manual_terminal(h)
        )
        btn_terminal.pack(side="right", padx=4, pady=10)

        # 2. Tombol Test Connection
        btn_test = ctk.CTkButton(
            card,
            text="Test",
            width=56, height=30, corner_radius=7,
            fg_color="#18283E",
            hover_color="#223B5D",
            text_color="#60A5FA",
            border_width=1,
            border_color="#254A78"
        )
        btn_test.configure(command=lambda h=host, b=btn_test: self._test_host_connection(h, b))
        btn_test.pack(side="right", padx=4, pady=10)

        # 1. Tombol Pull (Menggantikan Connect, menjalankan git pull)
        btn_pull = ctk.CTkButton(
            card, 
            text="Pull", 
            width=62, height=30, corner_radius=7,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(weight="bold"),
            command=lambda h=host: self._open_terminal(h)
        )
        btn_pull.pack(side="right", padx=4, pady=10)

    def _delete_host(self, host_id: int):
        self.db.delete_host(host_id)
        self._refresh_hosts_list()

    def _add_host_dialog(self):
        HostDialog(
            parent=self,
            db_manager=self.db,
            on_save_callback=self._refresh_hosts_list
        )

    def _edit_host_dialog(self, host: dict):
        HostDialog(
            parent=self,
            db_manager=self.db,
            host_data=host,
            on_save_callback=self._refresh_hosts_list
        )

    def _open_export_dialog(self):
        ExportDialog(parent=self, db_manager=self.db)

    def _open_import_dialog(self):
        ImportDialog(
            parent=self,
            db_manager=self.db,
            on_import_callback=self._refresh_hosts_list
        )

    def _open_git_credential_dialog(self):
        GitCredentialDialog(parent=self, db_manager=self.db)

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

    def _open_terminal(self, host: dict):
        """Buka terminal dan terapkan credential Git global bila tersedia."""
        terminal_host = dict(host)
        global_credential = self.db.get_global_git_credential()
        if global_credential:
            terminal_host["git_user"] = global_credential["username"]
            terminal_host["git_pass"] = global_credential["password"]
        TerminalWindow(self, terminal_host)

    def _test_host_connection(self, host: dict, btn_test: ctk.CTkButton):
        """Tes koneksi SSH ke remote host tanpa menjalankan perintah git pull."""
        original_text = btn_test.cget("text")
        btn_test.configure(state="disabled", text="...")

        def worker():
            import time
            import asyncssh
            start_time = time.time()
            success = False
            error_msg = ""

            try:
                client_keys = None
                if host.get('auth_type') == 'key' and host.get('key_filename'):
                    client_keys = [host['key_filename']]

                options = asyncssh.SSHClientConnectionOptions(
                    username=host['username'],
                    password=host.get('password') if host.get('auth_type') == 'password' else None,
                    client_keys=client_keys,
                    kex_algs=[
                        'curve25519-sha256',
                        'diffie-hellman-group14-sha1',
                        'diffie-hellman-group1-sha1'
                    ],
                    server_host_key_algs=[
                        'ssh-ed25519',
                        'ecdsa-sha2-nistp256',
                        'ssh-rsa',
                        'ssh-dss'
                    ],
                    known_hosts=None
                )

                async def do_test():
                    async with asyncssh.connect(
                        host['hostname'],
                        port=int(host.get('port', 22)),
                        options=options,
                        login_timeout=7
                    ) as conn:
                        res = await conn.run("echo ok", check=False)
                        return res.exit_status == 0

                success = asyncio.run(do_test())
            except Exception as e:
                error_msg = str(e)

            elapsed = round((time.time() - start_time) * 1000)

            def update_ui():
                btn_test.configure(state="normal", text=original_text)
                if success:
                    self.output_textbox.insert("end", f"✓ [{host['label']}] Connection test SUCCESSFUL ({elapsed} ms) -> {host['hostname']}:{host.get('port', 22)}\n")
                    self.output_textbox.see("end")
                    messagebox.showinfo(
                        "Connection Successful",
                        f"Koneksi SSH ke '{host['label']}' BERHASIL!\n\n"
                        f"Host: {host['hostname']}:{host.get('port', 22)}\n"
                        f"User: {host['username']}\n"
                        f"Waktu respon: {elapsed} ms"
                    )
                else:
                    self.output_textbox.insert("end", f"✗ [{host['label']}] Connection test FAILED: {error_msg}\n")
                    self.output_textbox.see("end")
                    messagebox.showerror(
                        "Connection Failed",
                        f"Koneksi SSH ke '{host['label']}' GAGAL!\n\n"
                        f"Host: {host['hostname']}:{host.get('port', 22)}\n"
                        f"Error: {error_msg}"
                    )

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _open_manual_terminal(self, host: dict):
        """Membuka sesi terminal interaktif (PuTTY atau Command Prompt SSH) untuk akses manual."""
        import shutil
        import subprocess

        hostname = host.get('hostname', '')
        port = str(host.get('port', 22))
        username = host.get('username', '')
        password = host.get('password', '')
        key_file = host.get('key_filename', '')
        auth_type = host.get('auth_type', 'password')

        # Salin password ke clipboard bila ada agar user bisa langsung paste
        if sys.platform != "darwin":
            if password:
                try:
                    self.clipboard_clear()
                    self.clipboard_append(password)
                    self.output_textbox.insert("end", f"ℹ [{host['label']}] Password SSH telah disalin ke clipboard.\n")
                    self.output_textbox.see("end")
                except Exception:
                    pass

        # ==========================================
        # 1. PENANGANAN UNTUK MACOS (sys.platform == "darwin")
        # ==========================================
        if sys.platform == "darwin":
            # Tambahkan penanganan kompatibilitas hostkey lama (+ssh-rsa,ssh-dss)
            extra_opts = "-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa"

            # Susun perintah dasar SSH
            if auth_type == "key" and key_file:
                ssh_cmd = f"ssh -i '{key_file}' {extra_opts} -p {port} {username}@{hostname}"
            else:
                ssh_cmd = f"ssh {extra_opts} -p {port} {username}@{hostname}"

            try:
                # Gunakan AppleScript via osascript untuk membuka Terminal.app / iTerm
                # Buka jendela Terminal baru dan jalankan perintah SSH
                applescript = f'''
                tell application "Terminal"
                    activate
                    do script "{ssh_cmd}"
                end tell
                '''
                subprocess.Popen(["osascript", "-e", applescript])
                self.output_textbox.insert("end", f"🚀 [{host['label']}] Membuka Terminal macOS: {ssh_cmd}\n")
                self.output_textbox.see("end")
                return
            except Exception as e:
                self.output_textbox.insert("end", f"Gagal membuka Terminal macOS ({e}), mencoba fallback...\n")

        # ==========================================
        # 2. PENANGANAN UNTUK WINDOWS (PuTTY / CMD)
        # ==========================================
        # Cari PuTTY di sistem
        putty_exe = shutil.which("putty")
        if not putty_exe:
            for candidate in [
                r"C:\Program Files\PuTTY\putty.exe",
                r"C:\Program Files (x86)\PuTTY\putty.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\PuTTY\putty.exe")
            ]:
                if os.path.exists(candidate):
                    putty_exe = candidate
                    break

        # Jika PuTTY ada, buka PuTTY (mendukung auto login dengan -pw)
        if putty_exe:
            cmd = [putty_exe, "-ssh", "-P", port, "-l", username]
            if auth_type == "password" and password:
                cmd.extend(["-pw", password])
            elif auth_type == "key" and key_file and key_file.lower().endswith(".ppk"):
                cmd.extend(["-i", key_file])
            cmd.append(hostname)

            try:
                subprocess.Popen(cmd)
                self.output_textbox.insert("end", f"🚀 [{host['label']}] Membuka sesi SSH via PuTTY ({hostname}:{port})...\n")
                self.output_textbox.see("end")
                return
            except Exception as e:
                self.output_textbox.insert("end", f"Gagal membuka PuTTY ({e}), beralih ke Command Prompt...\n")

        # Fallback ke Command Prompt Windows (OpenSSH bawaan)
        title = f"SSH - {host['label']} ({hostname})"
        if auth_type == "key" and key_file:
            ssh_target = f'ssh -i "{key_file}" -p {port} {username}@{hostname}'
        else:
            ssh_target = f'ssh -p {port} {username}@{hostname}'

        full_cmd = f'start "{title}" cmd /k "{ssh_target}"'
        try:
            subprocess.Popen(full_cmd, shell=True)
            self.output_textbox.insert("end", f"🚀 [{host['label']}] Membuka Command Prompt SSH: {ssh_target}\n")
            self.output_textbox.see("end")
        except Exception as e:
            messagebox.showerror("Terminal Error", f"Gagal membuka terminal: {e}")

    @staticmethod
    def _extract_git_summary(output: str) -> str:
        """Mengambil baris ringkasan dari output git pull (misal: 'X files changed...' atau 'Already up to date.')."""
        if not output:
            return ""

        lines = [line.strip() for line in output.strip().splitlines() if line.strip()]

        # 1. Cari baris ringkasan perubahan ("X file(s) changed...")
        for line in reversed(lines):
            if re.search(r"\d+\s+files?\s+changed", line):
                return line + "\n"

        # 2. Cari baris "Already up to date"
        for line in lines:
            if "already up to date" in line.lower() or "already up-to-date" in line.lower():
                return line + "\n"

        # 3. Fallback jika ada output lain
        return output.strip() + "\n"

    def _run_all_hosts(self):
        """Menjalankan git pull pada seluruh host yang dipilih (atau seluruh host yang difilter jika tidak ada yang dicentang) di background thread tanpa freeze UI."""
        self.output_textbox.delete("1.0", "end")
        all_hosts = self.db.get_all_hosts()
        selected_filter = self.filter_group_opt.get() if hasattr(self, 'filter_group_opt') else "All Groups"

        if selected_filter == "All Groups":
            filtered_hosts = all_hosts
        else:
            filtered_hosts = [h for h in all_hosts if h.get("group_name") == selected_filter]

        search_query = self.search_var.get().strip().lower() if hasattr(self, 'search_var') else ""
        if search_query:
            filtered_hosts = [h for h in filtered_hosts if search_query in h.get("label", "").lower()]

        # Jika ada host yang dicentang, jalankan HANYA pada host yang dicentang
        selected_ids = [hid for hid, var in self.host_checkbox_vars.items() if var.get()]
        if selected_ids:
            hosts = [h for h in filtered_hosts if h['id'] in selected_ids]
        else:
            hosts = filtered_hosts

        if not hosts:
            self.output_textbox.insert("end", f"Tidak ada host yang dipilih di grup '{selected_filter}'.\n")
            return

        self.btn_run_all.configure(state="disabled")

        def worker():
            import asyncssh

            async def run_all():
                global_credential = self.db.get_global_git_credential()
                for host in hosts:
                    self.after(0, self.output_textbox.insert, "end", f"=== Running on {host['label']} ({host['hostname']}) ===\n")
                    self.after(0, self.output_textbox.see, "end")

                    try:
                        client_keys = None
                        if host.get('auth_type') == 'key' and host.get('key_filename'):
                            client_keys = [host['key_filename']]

                        options = asyncssh.SSHClientConnectionOptions(
                            username=host['username'],
                            password=host.get('password') if host.get('auth_type') == 'password' else None,
                            client_keys=client_keys,
                            kex_algs=[
                                'curve25519-sha256',
                                'diffie-hellman-group14-sha1',
                                'diffie-hellman-group1-sha1'
                            ],
                            server_host_key_algs=[
                                'ssh-ed25519',
                                'ecdsa-sha2-nistp256',
                                'ssh-rsa',
                                'ssh-dss'
                            ],
                            known_hosts=None
                        )

                        async with asyncssh.connect(host['hostname'], port=host.get('port', 22), options=options) as conn:
                            repo_path = host.get('repo_path') or '/var/www/html'
                            base_cmd = f"cd {repo_path}"

                            git_branch = host.get('git_branch')
                            pull_target = f"pull origin {git_branch}" if git_branch else "pull"

                            git_user = host.get('git_user')
                            git_pass = host.get('git_pass')
                            if global_credential:
                                git_user = global_credential['username']
                                git_pass = global_credential['password']

                            if git_user and git_pass:
                                helper_str = f'!f() {{ echo "username={git_user}"; echo "password={git_pass}"; }}; f'
                                git_core = f"git -c credential.helper='{helper_str}' {pull_target}"
                            else:
                                git_core = f"git {pull_target}"

                            ssh_password = host.get('password')
                            if ssh_password:
                                escaped_pass = ssh_password.replace("'", "'\\''")
                                git_cmd = f"printf '%s\\n' '{escaped_pass}' | sudo -S -p '' {git_core}"
                            else:
                                git_cmd = f"sudo {git_core}"

                            command = f"{base_cmd} && {git_cmd}"
                            result = await conn.run(command, check=False)

                            if result.exit_status == 0:
                                summary = self._extract_git_summary(result.stdout)
                                if not summary and result.stderr:
                                    summary = self._extract_git_summary(result.stderr)
                                self.after(0, self.output_textbox.insert, "end", summary or "Already up to date.\n")
                            else:
                                if result.stdout:
                                    self.after(0, self.output_textbox.insert, "end", result.stdout)
                                if result.stderr:
                                    self.after(0, self.output_textbox.insert, "end", f"[STDERR] {result.stderr}\n")

                    except Exception as e:
                        self.after(0, self.output_textbox.insert, "end", f"[ERROR] {str(e)}\n")

                    self.after(0, self.output_textbox.insert, "end", "-" * 40 + "\n\n")
                    self.after(0, self.output_textbox.see, "end")

                self.after(0, lambda: self.btn_run_all.configure(state="normal"))

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_all())
            finally:
                loop.close()

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = TerbiusApp()
    app.mainloop()
