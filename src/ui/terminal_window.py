import customtkinter as ctk
from ssh_client import SSHConnection

class TerminalWindow(ctk.CTkToplevel):
    def __init__(self, parent, host_config):
        super().__init__(parent)
        self.title(f"Git Pull - {host_config.get('name', host_config['hostname'])}")
        self.geometry("700x480")

        # Event ketika jendela ditutup via tombol [X]
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Label Status
        self.status_label = ctk.CTkLabel(
            self, 
            text=" Status: Connecting...", 
            anchor="w", 
            text_color="#3B82F6",
            font=("Helvetica", 12, "bold")
        )
        self.status_label.pack(fill="x", padx=10, pady=(10, 0))

        # Text Box Log Output
        self.textbox = ctk.CTkTextbox(
            self, 
            font=("Courier", 12), 
            wrap="none",
            activate_scrollbars=True
        )
        self.textbox.pack(fill="both", expand=True, padx=10, pady=10)

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
            text_color="#10B981"
        )

    def _on_close(self):
        """Pembersihan saat jendela ditutup."""
        if hasattr(self, 'ssh'):
            self.ssh.disconnect()
        self.destroy()