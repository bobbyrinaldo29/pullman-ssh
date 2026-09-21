import asyncio
import os
import shutil
import subprocess
import sys
import threading
from tkinter import messagebox
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

import pull_service
from theme import COLORS
from ui.db_tool_import_dialog import DbToolImportDialog
from ui.export_dialog import ExportDialog
from ui.host_dialog import HostDialog
from ui.import_dialog import ImportDialog
from ui.import_source_dialog import ImportSourceDialog
from ui.terminal_window import TerminalWindow


class HostsView(ctk.CTkFrame):
    """Tampilan 'Pull Blast': daftar host, filter/search, dan aksi git pull massal."""

    def __init__(self, parent: ctk.CTk, db_manager: Any, on_data_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color=COLORS["window"])
        self.app = parent
        self.db = db_manager
        self._on_data_changed = on_data_changed

        self.selected_host_ids = set()
        self.host_checkbox_vars = {}

        self.grid_columnconfigure(0, weight=1)
        self._setup_ui()

    def refresh(self):
        """Memuat ulang data dan merender daftar host dari SQLite."""
        self._refresh_filter_options()
        self._render_hosts_list()
        self.after(50, lambda: self._bind_mousewheel(self.hosts_scroll))

    def _notify_data_changed(self):
        """Beritahu view lain (DB Blast) bahwa data host berubah, karena satu tabel dipakai bersama."""
        if self._on_data_changed:
            self._on_data_changed()

    def open_import_dialog(self):
        ImportSourceDialog(parent=self.app, on_select=self._handle_import_source_selected)

    def _handle_import_source_selected(self, source: str):
        if source == "pullman":
            ImportDialog(
                parent=self.app,
                db_manager=self.db,
                on_import_callback=self._refresh_and_notify
            )
        else:
            DbToolImportDialog(
                parent=self.app,
                db_manager=self.db,
                source=source,
                on_import_callback=self._refresh_and_notify
            )

    def open_export_dialog(self):
        ExportDialog(parent=self.app, db_manager=self.db)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)
        header.grid_columnconfigure(2, weight=0)
        header.grid_columnconfigure(3, weight=0)
        header.grid_columnconfigure(4, weight=0)

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

        btn_refresh = ctk.CTkButton(header, text="↻", width=34, height=34, corner_radius=8, fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"], command=self.refresh)
        btn_refresh.grid(row=0, column=2, sticky="e", padx=(5, 0))

        btn_new_host = ctk.CTkButton(header, text="+  New Host", width=112, height=34, corner_radius=8, fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"], command=self._add_host_dialog)
        btn_new_host.grid(row=0, column=3, sticky="e", padx=(5, 0))

        self.btn_run_all = ctk.CTkButton(header, text="Run All", width=100, height=34, corner_radius=8, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._run_all_hosts)
        self.btn_run_all.grid(row=0, column=4, sticky="e", padx=(5, 0))

        # --- Search Bar ---
        search_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=10)
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

        self.hosts_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.hosts_scroll.grid(row=2, column=0, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

        self.output_textbox = ctk.CTkTextbox(self, font=("Menlo", 12), wrap="none", height=155, corner_radius=10, border_width=1, border_color=COLORS["line"], fg_color="#17181C", text_color="#D1D5DB")
        self.output_textbox.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        self.grid_rowconfigure(3, weight=0)

    # ------------------------------------------------------------------
    # Filter / search / selection
    # ------------------------------------------------------------------

    def _refresh_filter_options(self):
        """Memperbarui daftar opsi filter grup di header."""
        groups = self.db.get_groups()
        group_names = ["All Groups"] + [g["name"] for g in groups]
        current_val = self.filter_group_opt.get()
        self.filter_group_opt.configure(values=group_names)
        if current_val in group_names:
            self.filter_group_opt.set(current_val)
        else:
            self.filter_group_opt.set("All Groups")

    def _on_filter_changed(self, selected_group: str):
        self._render_hosts_list()

    def _bind_mousewheel(self, widget):
        """Rekursif bind event scroll trackpad/mouse ke semua child widget di CTkScrollableFrame."""
        canvas = self.hosts_scroll._parent_canvas

        def _scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 60)), "units")

        widget.bind("<MouseWheel>", _scroll, add="+")
        for child in widget.winfo_children():
            self._bind_mousewheel(child)

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
        selected_filter = self.filter_group_opt.get()
        if count > 0:
            self.btn_run_all.configure(text=f"Pull Selected ({count})")
        else:
            if selected_filter == "All Groups":
                self.btn_run_all.configure(text="Run All")
            else:
                self.btn_run_all.configure(text=f"Run All ({selected_filter})")

    def _get_filtered_hosts(self):
        """Ambil host sesuai filter grup dan kata kunci pencarian yang aktif."""
        all_hosts = self.db.get_all_hosts()
        selected_filter = self.filter_group_opt.get()
        search_query = self.search_var.get().strip().lower()

        if selected_filter == "All Groups":
            hosts = all_hosts
        else:
            hosts = [h for h in all_hosts if h.get("group_name") == selected_filter]

        if search_query:
            hosts = [h for h in hosts if search_query in h.get("label", "").lower()]

        return all_hosts, hosts

    # ------------------------------------------------------------------
    # Host list rendering
    # ------------------------------------------------------------------

    def _render_hosts_list(self):
        """Merender daftar host sesuai filter grup dan kata kunci pencarian."""
        for widget in self.hosts_scroll.winfo_children():
            widget.destroy()

        self.host_checkbox_vars.clear()

        all_hosts, hosts = self._get_filtered_hosts()
        selected_filter = self.filter_group_opt.get()

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

        btn_edit = ctk.CTkButton(
            card,
            text="Edit",
            width=52, height=30, corner_radius=7,
            fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"],
            command=lambda h=host: self._edit_host_dialog(h)
        )
        btn_edit.pack(side="right", padx=4, pady=10)

        btn_terminal = ctk.CTkButton(
            card,
            text="Terminal",
            width=70, height=30, corner_radius=7,
            fg_color=COLORS["surface_hover"],
            hover_color=COLORS["line"],
            command=lambda h=host: self._open_manual_terminal(h)
        )
        btn_terminal.pack(side="right", padx=4, pady=10)

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

        btn_pull = ctk.CTkButton(
            card,
            text="Pull",
            width=62, height=30, corner_radius=7,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(weight="bold"),
            command=lambda h=host: self._open_terminal(h)
        )
        btn_pull.pack(side="right", padx=4, pady=10)

    # ------------------------------------------------------------------
    # Host CRUD
    # ------------------------------------------------------------------

    def _refresh_and_notify(self):
        """Refresh daftar host di sini, lalu beritahu DB Blast karena satu tabel yang sama bisa berubah."""
        self.refresh()
        self._notify_data_changed()

    def _delete_host(self, host_id: int):
        self.db.delete_host(host_id)
        self._refresh_and_notify()

    def _add_host_dialog(self):
        HostDialog(
            parent=self.app,
            db_manager=self.db,
            on_save_callback=self._refresh_and_notify
        )

    def _edit_host_dialog(self, host: dict):
        HostDialog(
            parent=self.app,
            db_manager=self.db,
            host_data=host,
            on_save_callback=self._refresh_and_notify
        )

    # ------------------------------------------------------------------
    # Terminal / connection actions
    # ------------------------------------------------------------------

    def _open_terminal(self, host: dict):
        """Buka terminal dan terapkan credential Git global bila tersedia."""
        terminal_host = dict(host)
        global_credential = self.db.get_global_git_credential()
        if global_credential:
            terminal_host["git_user"] = global_credential["username"]
            terminal_host["git_pass"] = global_credential["password"]
        TerminalWindow(self.app, terminal_host)

    def _test_host_connection(self, host: dict, btn_test: ctk.CTkButton):
        """Tes koneksi SSH ke remote host tanpa menjalankan perintah git pull."""
        original_text = btn_test.cget("text")
        btn_test.configure(state="disabled", text="...")

        def worker():
            result = pull_service.test_connection(host)
            self.after(0, lambda: self._on_test_result(host, btn_test, original_text, result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_result(self, host: dict, btn_test: ctk.CTkButton, original_text: str, result: Dict[str, Any]):
        btn_test.configure(state="normal", text=original_text)
        elapsed = result["elapsed_ms"]
        if result["success"]:
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
            error_msg = result["error"]
            self.output_textbox.insert("end", f"✗ [{host['label']}] Connection test FAILED: {error_msg}\n")
            self.output_textbox.see("end")
            messagebox.showerror(
                "Connection Failed",
                f"Koneksi SSH ke '{host['label']}' GAGAL!\n\n"
                f"Host: {host['hostname']}:{host.get('port', 22)}\n"
                f"Error: {error_msg}"
            )

    def _open_manual_terminal(self, host: dict):
        """Membuka sesi terminal interaktif (macOS Terminal/sshpass, PuTTY, atau Windows CMD) untuk akses manual."""
        hostname = host.get('hostname', '')
        port = str(host.get('port', 22))
        username = host.get('username', '')
        password = host.get('password', '')
        key_file = host.get('key_filename', '')
        auth_type = host.get('auth_type', 'password')

        # Salin password ke clipboard bila ada agar user tetap bisa paste secara manual jika dibutuhkan
        if password:
            try:
                self.app.clipboard_clear()
                self.app.clipboard_append(password)
                self.output_textbox.insert("end", f"ℹ [{host['label']}] Password SSH telah disalin ke clipboard.\n")
                self.output_textbox.see("end")
            except Exception:
                pass

        # ==========================================
        # 1. PENANGANAN UNTUK MACOS (sys.platform == "darwin")
        # ==========================================
        if sys.platform == "darwin":
            extra_opts = "-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa"
            sshpass_bin = shutil.which("sshpass")

            # Kasus A: Kunci SSH (Key Authentication)
            if auth_type == "key" and key_file:
                ssh_cmd = f"ssh -i '{key_file}' {extra_opts} -p {port} {username}@{hostname}"
                applescript = f'''
                tell application "Terminal"
                    activate
                    do script "{ssh_cmd}"
                end tell
                '''
            # Kasus B: Password via sshpass (Jika terinstal di macOS)
            elif auth_type == "password" and password and sshpass_bin:
                ssh_cmd = f"{sshpass_bin} -p '{password}' ssh {extra_opts} -p {port} {username}@{hostname}"
                applescript = f'''
                tell application "Terminal"
                    activate
                    do script "{ssh_cmd}"
                end tell
                '''
            # Kasus C: Password via AppleScript Auto-Type (Tanpa butuh install sshpass)
            elif auth_type == "password" and password:
                ssh_cmd = f"ssh {extra_opts} -p {port} {username}@{hostname}"
                # AppleScript akan membuka tab terminal baru, mengeksekusi SSH, 
                # menunggu 1.5 detik hingga prompt password muncul, lalu otomatis mengetikkan password
                applescript = f'''
                tell application "Terminal"
                    activate
                    set newTab to do script "{ssh_cmd}"
                    delay 1.5
                    do script "{password}" in newTab
                end tell
                '''
            # Kasus D: Standar SSH tanpa password
            else:
                ssh_cmd = f"ssh {extra_opts} -p {port} {username}@{hostname}"
                applescript = f'''
                tell application "Terminal"
                    activate
                    do script "{ssh_cmd}"
                end tell
                '''

            try:
                subprocess.Popen(["osascript", "-e", applescript])
                self.output_textbox.insert("end", f"🚀 [{host['label']}] Membuka Terminal macOS ({hostname}:{port})...\n")
                self.output_textbox.see("end")
                return
            except Exception as e:
                self.output_textbox.insert("end", f"Gagal membuka Terminal macOS ({e}), mencoba fallback...\n")

        # ==========================================
        # 2. PENANGANAN UNTUK WINDOWS (PuTTY / CMD)
        # ==========================================
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

    # ------------------------------------------------------------------
    # Bulk pull
    # ------------------------------------------------------------------

    def _run_all_hosts(self):
        """Menjalankan git pull pada seluruh host yang dipilih (atau seluruh host yang difilter jika tidak ada yang dicentang) di background thread tanpa freeze UI."""
        self.output_textbox.delete("1.0", "end")
        _, filtered_hosts = self._get_filtered_hosts()
        selected_filter = self.filter_group_opt.get()

        selected_ids = [hid for hid, var in self.host_checkbox_vars.items() if var.get()]
        if selected_ids:
            hosts = [h for h in filtered_hosts if h['id'] in selected_ids]
        else:
            hosts = filtered_hosts

        if not hosts:
            self.output_textbox.insert("end", f"Tidak ada host yang dipilih di grup '{selected_filter}'.\n")
            return

        self.btn_run_all.configure(state="disabled")
        global_credential = self.db.get_global_git_credential()

        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    pull_service.run_pull_on_hosts(hosts, global_credential, self._append_output)
                )
            finally:
                loop.close()
            self.after(0, lambda: self.btn_run_all.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _append_output(self, text: str):
        """Callback thread-safe untuk menulis log dari worker ke textbox (dipanggil via self.after)."""
        def write():
            self.output_textbox.insert("end", text)
            self.output_textbox.see("end")
        self.after(0, write)
