import os
os.environ['TK_SILENCE_DEPRECATION'] = '1'

import asyncio
import re
import threading
import customtkinter as ctk
from database import DatabaseManager
from ui.host_dialog import HostDialog
from ui.export_dialog import ExportDialog
from ui.import_dialog import ImportDialog
from ssh_client import SSHConnection
from PIL import ImageTk, Image
from ui.terminal_window import TerminalWindow

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class TerbiusApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.db = DatabaseManager("pullManager.db")

        self.title("DO.MBA - Pull Manager v1.0")
        self.geometry("950x600")

        # --- SET ICON DI SINI ---
        # Pastikan file 'app_icon' berada di folder yang sama atau tentukan path lengkapnya
        try:
            # 1. Buka gambar menggunakan Pillow
            pil_image = Image.open("src/assets/icon_512x512.png")
            
            # 2. Resize ke ukuran standar window icon (misal 512x512 agar tajam di Retina display)
            resized_image = pil_image.resize((250, 250), Image.Resampling.LANCZOS)
            
            # 3. Simpan referensi objek ke self agar tidak di-garbage collect
            self.icon_image = ImageTk.PhotoImage(resized_image)
            
            # 4. Pasang ke window
            self.wm_iconphoto(True, self.icon_image)

        except Exception as e:
            print(f"Gagal memuat ikon .png: {e}")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._setup_sidebar()
        self._setup_main_content()
        self._refresh_hosts_list()

    def _setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_rowconfigure(4, weight=1)  # row 4 = spacer
        self.sidebar.grid_columnconfigure(0, weight=1)

        logo_label = ctk.CTkLabel(self.sidebar, text="DO.MBA", font=ctk.CTkFont(size=20, weight="bold"))
        logo_label.grid(row=0, column=0, padx=20, pady=(20, 30))

        self.btn_hosts = ctk.CTkButton(
            self.sidebar, text="Pull Blast", anchor="w",
            fg_color="#1D3557", text_color="white",
            command=self._show_hosts_view
        )
        self.btn_hosts.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        # Spacer (row 4 has weight=1, pushes import/export to bottom)
        spacer = ctk.CTkLabel(self.sidebar, text="")
        spacer.grid(row=4, column=0)

        # --- Bottom: Import / Export Buttons ---
        btn_import = ctk.CTkButton(
            self.sidebar,
            text="⬇  Import",
            fg_color="transparent",
            anchor="w",
            command=self._open_import_dialog
        )
        btn_import.grid(row=5, column=0, padx=10, pady=5, sticky="ew")

        btn_export = ctk.CTkButton(
            self.sidebar,
            text="⬆  Export",
            fg_color="transparent",
            anchor="w",
            command=self._open_export_dialog
        )
        btn_export.grid(row=6, column=0, padx=10, pady=(5, 10), sticky="ew")

        footer_label = ctk.CTkLabel(
            self.sidebar,
            text="Vibe Code \n By Sukma Dewa",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        footer_label.grid(row=7, column=0, padx=10, pady=(0, 12), sticky="ew")

    def _setup_main_content(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)
        header.grid_columnconfigure(2, weight=0)
        header.grid_columnconfigure(3, weight=0)

        title = ctk.CTkLabel(header, text="Hosts", font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, sticky="w")

        # Filter Group Frame
        filter_frame = ctk.CTkFrame(header, fg_color="transparent")
        filter_frame.grid(row=0, column=1, sticky="e", padx=(0, 10))

        lbl_filter = ctk.CTkLabel(filter_frame, text="Group:", font=ctk.CTkFont(size=12))
        lbl_filter.pack(side="left", padx=(0, 5))

        self.filter_group_opt = ctk.CTkOptionMenu(
            filter_frame,
            values=["All Groups"],
            width=140,
            command=self._on_filter_changed
        )
        self.filter_group_opt.pack(side="left")

        btn_new_host = ctk.CTkButton(header, text="+ New Host", width=100, command=self._add_host_dialog)
        btn_new_host.grid(row=0, column=2, sticky="e", padx=(5, 0))

        self.btn_run_all = ctk.CTkButton(header, text="Run All", width=100, command=self._run_all_hosts)
        self.btn_run_all.grid(row=0, column=3, sticky="e", padx=(5, 0))

        # --- Search Bar ---
        search_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        search_frame.grid_columnconfigure(1, weight=1)

        lbl_search = ctk.CTkLabel(search_frame, text="🔍", font=ctk.CTkFont(size=14))
        lbl_search.grid(row=0, column=0, padx=(0, 6))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_hosts_list())

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Cari host berdasarkan nama...",
            textvariable=self.search_var,
            height=34
        )
        self.search_entry.grid(row=0, column=1, sticky="ew")

        self.hosts_scroll = ctk.CTkScrollableFrame(self.main_frame)
        self.hosts_scroll.grid(row=2, column=0, sticky="nsew")
        self.main_frame.grid_rowconfigure(2, weight=1)

        self.output_textbox = ctk.CTkTextbox(self.main_frame, font=("Courier", 12), wrap="none", height=200)
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
        active_btn.configure(fg_color="#1D3557")

    def _show_hosts_view(self):
        """Tampilkan kembali tampilan Hosts dan refresh daftar."""
        self._set_active_nav(self.btn_hosts)
        self._refresh_hosts_list()

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

    def _render_hosts_list(self):
        """Merender daftar host sesuai filter grup dan kata kunci pencarian."""
        for widget in self.hosts_scroll.winfo_children():
            widget.destroy()

        all_hosts = self.db.get_all_hosts()
        selected_filter = self.filter_group_opt.get() if hasattr(self, 'filter_group_opt') else "All Groups"
        search_query = self.search_var.get().strip().lower() if hasattr(self, 'search_var') else ""

        if selected_filter == "All Groups":
            hosts = all_hosts
            run_btn_text = "Run All"
        else:
            hosts = [h for h in all_hosts if h.get("group_name") == selected_filter]
            run_btn_text = f"Run All ({selected_filter})"

        # Filter berdasarkan search query
        if search_query:
            hosts = [h for h in hosts if search_query in h.get("label", "").lower()]

        self.btn_run_all.configure(text=run_btn_text)

        if not hosts:
            if not all_hosts:
                msg = "Belum ada host tersimpan. Klik '+ New Host' untuk menambahkan."
            else:
                msg = f"No host at group '{selected_filter}'."
            lbl_empty = ctk.CTkLabel(
                self.hosts_scroll, 
                text=msg,
                text_color="gray"
            )
            lbl_empty.pack(pady=20)
            return

        for host in hosts:
            self._create_host_card(host)

    def _create_host_card(self, host: dict):
        card = ctk.CTkFrame(self.hosts_scroll)
        card.pack(fill="x", padx=10, pady=5)

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", padx=15, pady=10)

        # Baris Header: Label Host + Badge Group
        title_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        title_row.pack(anchor="w")

        lbl_name = ctk.CTkLabel(title_row, text=host['label'], font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        lbl_name.pack(side="left")

        if host.get('group_name'):
            lbl_group_badge = ctk.CTkLabel(
                title_row,
                text=host['group_name'],
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#1E3A8A",
                text_color="#93C5FD",
                corner_radius=6,
                padx=8,
                pady=2
            )
            lbl_group_badge.pack(side="left", padx=(10, 0))

        branch_str = f"  •  Branch: {host['git_branch']}" if host.get('git_branch') else ""
        target_str = f"{host['username']}@{host['hostname']}:{host['port']} {branch_str}"
        lbl_target = ctk.CTkLabel(info_frame, text=target_str, text_color="gray", font=ctk.CTkFont(size=11), anchor="w")
        lbl_target.pack(anchor="w", pady=(3, 0))

        btn_delete = ctk.CTkButton(
            card, 
            text="Delete", 
            width=60, 
            fg_color="transparent", 
            border_width=1, 
            text_color="red",
            hover_color="#400000",
            command=lambda: self._delete_host(host['id'])
        )
        btn_delete.pack(side="right", padx=(5, 15), pady=10)

        btn_edit = ctk.CTkButton(
            card,
            text="Edit",
            width=60,
            fg_color="#374151",
            hover_color="#4B5563",
            command=lambda h=host: self._edit_host_dialog(h)
        )
        btn_edit.pack(side="right", padx=5, pady=10)

        btn_connect = ctk.CTkButton(
            card, 
            text="Connect", 
            width=80, 
            command=lambda h=host: TerminalWindow(self, h)
        )
        btn_connect.pack(side="right", padx=5, pady=10)

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
        """Menjalankan git pull pada seluruh host yang sedang difilter di background thread tanpa freeze UI."""
        self.output_textbox.delete("1.0", "end")
        all_hosts = self.db.get_all_hosts()
        selected_filter = self.filter_group_opt.get() if hasattr(self, 'filter_group_opt') else "All Groups"

        if selected_filter == "All Groups":
            hosts = all_hosts
        else:
            hosts = [h for h in all_hosts if h.get("group_name") == selected_filter]

        if not hosts:
            self.output_textbox.insert("end", f"No hosts configured for group '{selected_filter}'.\n")
            return

        self.btn_run_all.configure(state="disabled")

        def worker():
            import asyncssh

            async def run_all():
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