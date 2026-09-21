import asyncio
import re
import time
from typing import Any, Callable, Dict, List, Optional

import asyncssh


def _build_ssh_options(host: Dict[str, Any]) -> asyncssh.SSHClientConnectionOptions:
    client_keys = None
    if host.get('auth_type') == 'key' and host.get('key_filename'):
        client_keys = [host['key_filename']]

    return asyncssh.SSHClientConnectionOptions(
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


def _build_git_pull_command(host: Dict[str, Any], global_credential: Optional[Dict[str, str]]) -> str:
    """Menyusun perintah 'cd <repo> && sudo git pull' dengan credential helper Git bila tersedia."""
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

    return f"{base_cmd} && {git_cmd}"


def extract_git_summary(output: str) -> str:
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


def test_connection(host: Dict[str, Any]) -> Dict[str, Any]:
    """Tes koneksi SSH ke remote host tanpa menjalankan git pull. Blocking; jalankan dari worker thread."""
    start_time = time.time()
    success = False
    error_msg = ""

    try:
        options = _build_ssh_options(host)

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

    elapsed_ms = round((time.time() - start_time) * 1000)
    return {"success": success, "elapsed_ms": elapsed_ms, "error": error_msg}


async def run_pull_on_hosts(
    hosts: List[Dict[str, Any]],
    global_credential: Optional[Dict[str, str]],
    on_output: Callable[[str], None],
) -> None:
    """Menjalankan git pull berurutan pada setiap host, mengirim tiap potongan log ke on_output."""
    for host in hosts:
        on_output(f"=== Running on {host['label']} ({host['hostname']}) ===\n")

        try:
            options = _build_ssh_options(host)
            async with asyncssh.connect(host['hostname'], port=host.get('port', 22), options=options) as conn:
                command = _build_git_pull_command(host, global_credential)
                result = await conn.run(command, check=False)

                if result.exit_status == 0:
                    summary = extract_git_summary(result.stdout)
                    if not summary and result.stderr:
                        summary = extract_git_summary(result.stderr)
                    on_output(summary or "Already up to date.\n")
                else:
                    if result.stdout:
                        on_output(result.stdout)
                    if result.stderr:
                        on_output(f"[STDERR] {result.stderr}\n")

        except Exception as e:
            on_output(f"[ERROR] {str(e)}\n")

        on_output("-" * 40 + "\n\n")
