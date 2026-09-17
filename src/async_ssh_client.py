import asyncio
import asyncssh
import sys

class AsyncSSHClient:
    def __init__(self, hostname, port, username, password=None, key_filename=None, on_output_callback=None):
        self.hostname = hostname
        self.port = int(port)
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.on_output_callback = on_output_callback
        self.conn = None
        self.process = None
        self._is_running = False

    async def connect_and_run(self):
        try:
            # Pilihan algoritma legacy diizinkan secara eksplisit menggunakan tanda '+'
            options = asyncssh.SSHClientConnectionOptions(
                username=self.username,
                password=self.password,
                client_keys=[self.key_filename] if self.key_filename else None,
                kex_algs=[
                    'curve25519-sha256',
                    '+diffie-hellman-group14-sha1',
                    '+diffie-hellman-group1-sha1'
                ],
                server_host_key_algs=[
                    'ssh-ed25519',
                    'ecdsa-sha2-nistp256',
                    '+ssh-rsa',
                    '+ssh-dss'
                ],
                known_hosts=None  # Abaikan verifikasi strict host key jika diperlukan
            )

            if self.on_output_callback:
                self.on_output_callback(f"Connecting to {self.hostname}:{self.port}...\n")

            self.conn = await asyncssh.connect(
                self.hostname,
                port=self.port,
                options=options
            )

            if self.on_output_callback:
                self.on_output_callback(f"=== Connected to {self.hostname}:{self.port} ===\n\n")

            # Buka pty interaktif
            self.process = await self.conn.create_process(term_type='xterm')
            self._is_running = True

            # Loop membaca output dari server
            while self._is_running:
                try:
                    data = await asyncio.wait_for(self.process.stdout.read(1024), timeout=0.1)
                    if data:
                        if self.on_output_callback:
                            self.on_output_callback(data)
                    elif self.process.stdout.at_eof():
                        break
                except asyncio.TimeoutError:
                    continue

        except Exception as e:
            if self.on_output_callback:
                self.on_output_callback(f"\n[SSH Error]: {str(e)}\n")
        finally:
            self.disconnect()

    def send_input(self, text: str):
        """Kirim perintah dari GUI/UI ke server SSH"""
        if self.process and self.process.stdin:
            self.process.stdin.write(text)

    def disconnect(self):
        self._is_running = False
        if self.process:
            self.process.close()
        if self.conn:
            self.conn.close()
        if self.on_output_callback:
            self.on_output_callback("\n[Session Closed]\n")