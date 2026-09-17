import asyncio
import asyncssh
import threading
import warnings
from typing import Callable, Optional
from cryptography.utils import CryptographyDeprecationWarning

warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

class SSHConnection:
    def __init__(
        self,
        hostname: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        repo_path: str = "/var/www/html",
        git_branch: Optional[str] = None,     # Git branch pilihan
        git_user: Optional[str] = None,       # Ditambahkan
        git_pass: Optional[str] = None,       # Ditambahkan
        on_output_callback: Optional[Callable[[str], None]] = None,
        on_close_callback: Optional[Callable[[], None]] = None
    ):
        self.hostname = hostname
        self.port = int(port)
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.repo_path = repo_path.strip() or "/var/www/html"
        self.git_branch = git_branch.strip() if git_branch and git_branch.strip() else None
        self.git_user = git_user
        self.git_pass = git_pass
        self.on_output_callback = on_output_callback
        self.on_close_callback = on_close_callback

        self.conn = None
        self._thread = None

    def start(self):
        """Memulai eksekusi SSH di background thread."""
        self._thread = threading.Thread(
            target=self._run_event_loop, 
            daemon=True
        )
        self._thread.start()

    def _run_event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run_command())

    def _build_git_command(self) -> str:
        """Menyusun perintah Git Pull dengan sudo dan injeksi credential helper jika tersedia."""
        base_cmd = f"cd {self.repo_path}"
        pull_target = f"pull origin {self.git_branch}" if self.git_branch else "pull"

        if self.git_user and self.git_pass:
            # Inline credential.helper with proper quoting using single quotes around helper string
            git_core = f"git -c credential.helper='!f() {{ echo \"username={self.git_user}\"; echo \"password={self.git_pass}\"; }}; f' {pull_target}"
        else:
            git_core = f"git {pull_target}"

        # Jalankan dengan sudo menggunakan password SSH yang tersimpan (jika ada)
        if self.password:
            escaped_pass = self.password.replace("'", "'\\''")
            git_cmd = f"printf '%s\\n' '{escaped_pass}' | sudo -S -p '' {git_core}"
        else:
            git_cmd = f"sudo {git_core}"

        return f"{base_cmd} && {git_cmd}"

    async def _run_command(self):
        try:
            options = asyncssh.SSHClientConnectionOptions(
                username=self.username,
                password=self.password,
                client_keys=[self.key_filename] if self.key_filename else None,
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

            if self.on_output_callback:
                self.on_output_callback(f"Connecting to {self.hostname}:{self.port}...\n")

            async with asyncssh.connect(self.hostname, port=self.port, options=options) as conn:
                command = self._build_git_command()
                
                # Sembunyikan Password/Token Git dan Password SSH dari Tampilan Logs UI
                display_cmd = command
                if self.password:
                    display_cmd = display_cmd.replace(self.password, "********")
                if self.git_pass:
                    display_cmd = display_cmd.replace(self.git_pass, "********")

                if self.on_output_callback:
                    self.on_output_callback(f"Target Directory: {self.repo_path}\n")
                    self.on_output_callback(f"Executing: {display_cmd}\n" + "-"*40 + "\n")

                result = await conn.run(command, check=False)

                if result.stdout and self.on_output_callback:
                    self.on_output_callback(result.stdout)
                if result.stderr and self.on_output_callback:
                    self.on_output_callback(f"\n[STDERR]:\n{result.stderr}")

                if self.on_output_callback:
                    self.on_output_callback(f"\n" + "-"*40 + f"\n=== Process Finished (Exit Code: {result.exit_status}) ===\n")

        except Exception as e:
            if self.on_output_callback:
                self.on_output_callback(f"\n[SSH Error]: {str(e)}\n")
        finally:
            if self.on_close_callback:
                self.on_close_callback()

    def send_command(self, text: str):
        pass

    def disconnect(self):
        pass