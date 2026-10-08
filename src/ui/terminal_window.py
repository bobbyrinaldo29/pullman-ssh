import customtkinter as ctk
from theme import COLORS
from ssh_client import SSHConnection

class TerminalWindow(ctk.CTkToplevel):
    def __init__(self, parent, host_config):
        super().__init__(parent, fg_color=COLORS["window"])
        host_label = host_config.get('label') or host_config.get('name') or host_config.get('hostname', 'Host')
        self.title(f"Git Pull - {host_label}")
        self.geometry("720x480")

        # Event ketika jendela ditutup via tombol [X]
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Label Status
        self.status_label = ctk.CTkLabel(
            self, 
            text=" Status: Connecting...", 
            anchor="w", 
            text_color=COLORS["accent_text"],
            font=("Helvetica", 12, "bold")
        )
        self.status_label.pack(fill="x", padx=14, pady=(12, 0))

        # Text Box Log Output
        self.textbox = ctk.CTkTextbox(
            self, 
            font=("Menlo", 12), 
            wrap="none",
            activate_scrollbars=True,
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"],
            fg_color=COLORS["console_bg"],
            text_color=COLORS["console_text"]
        )
        self.textbox.pack(fill="both", expand=True, padx=14, pady=12)

        # Inisialisasi SSH Connection
        self.ssh = SSHConnection(
            hostname=host_config['hostname'],
            port=int(host_config.get('port', 22)),
            username=host_config['username'],
            password=host_config.get('password'),
            key_filename=host_config.get('key_filename'),
            repo_path=host_config.get('repo_path', '/var/www/html'),
            git_branch=host_config.get('git_branch'),
            git_user=host_config.get('git_user'),
            git_pass=host_config.get('git_pass'),
            on_output_callback=self._append_output,
            on_close_callback=self._on_process_finished
        )

        # Jalankan koneksi
        self.ssh.start()

    def _append_output(self, text: str):
        """Memasukkan teks log ke dalam textbox secara thread-safe."""
        self.textbox.insert("end", text)
        self.textbox.see("end")

    def _on_process_finished(self):
        """Callback saat eksekusi git pull di server selesai."""
        self.status_label.configure(
            text=" Status: Process Completed", 
            text_color=COLORS["success"]
        )

    def _on_close(self):
        """Pembersihan saat jendela ditutup."""
        if hasattr(self, 'ssh'):
            self.ssh.disconnect()
        self.destroy()