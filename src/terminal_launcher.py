import os
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional, Tuple


def _escape_applescript(s: str) -> str:
    """Escape string for inclusion inside AppleScript double quotes."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _run_applescript(script: str) -> Tuple[bool, str]:
    """Menjalankan script AppleScript melalui stdin osascript secara aman dan bebas syntax error escaping."""
    try:
        proc = subprocess.Popen(
            ["osascript", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(script)
        if proc.returncode == 0:
            return True, stdout.strip()
        return False, stderr.strip() or f"Exit code {proc.returncode}"
    except Exception as e:
        return False, str(e)


def _find_windows_ssh_binary() -> Optional[str]:
    """Mencari lokasi binary OpenSSH ssh.exe di lingkungan sistem Windows."""
    # 1. Dari PATH
    found = shutil.which("ssh")
    if found and os.path.isfile(found):
        return found

    # 2. Lokasi bawaan Windows 10/11 (System32 OpenSSH)
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    sys32_ssh = os.path.join(system_root, "System32", "OpenSSH", "ssh.exe")
    if os.path.isfile(sys32_ssh):
        return sys32_ssh

    # 3. Lokasi Git for Windows
    git_candidates = [
        r"C:\Program Files\Git\usr\bin\ssh.exe",
        r"C:\Program Files (x86)\Git\usr\bin\ssh.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\usr\bin\ssh.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Git\usr\bin\ssh.exe")
    ]
    for c in git_candidates:
        if os.path.isfile(c):
            return c

    return None


def _find_windows_putty() -> Optional[str]:
    """Mencari executable PuTTY / KiTTY bila terpasang di Windows."""
    found = shutil.which("putty") or shutil.which("kitty")
    if found and os.path.isfile(found):
        return found

    candidates = [
        r"C:\Program Files\PuTTY\putty.exe",
        r"C:\Program Files (x86)\PuTTY\putty.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\PuTTY\putty.exe"),
        r"C:\Program Files\KiTTY\kitty.exe",
        r"C:\Program Files (x86)\KiTTY\kitty.exe"
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    return None


def _find_windows_git_bash() -> Optional[str]:
    """Mencari executable Git Bash di Windows."""
    candidates = [
        r"C:\Program Files\Git\git-bash.exe",
        r"C:\Program Files (x86)\Git\git-bash.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\git-bash.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Git\git-bash.exe")
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def launch_ssh_terminal(
    host: Dict[str, Any],
    initial_dir: Optional[str] = None,
    app: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Membuka sesi SSH terminal/Command Prompt interaktif lintas sistem operasi
    (Windows CMD / PowerShell / Windows Terminal / PuTTY, macOS Terminal, Linux Terminal)
    dan langsung berpindah ke direktori tertentu (initial_dir) bila ditentukan.
    """
    hostname = host.get("hostname", "")
    port = str(host.get("port", 22))
    username = host.get("username", "")
    password = host.get("password", "")
    key_file = host.get("key_filename", "")
    auth_type = host.get("auth_type", "password")
    label = host.get("label") or hostname or "SSH Server"

    # Salin password ke clipboard bila tersedia untuk mempermudah login
    if password and app:
        try:
            app.clipboard_clear()
            app.clipboard_append(password)
        except Exception:
            pass

    # Siapkan perintah direktori remote
    target_dir = initial_dir.strip() if initial_dir and initial_dir.strip() else ""
    if target_dir:
        safe_dir = target_dir.replace("'", "'\\''")
        remote_cmd = f"cd '{safe_dir}' 2>/dev/null || cd /; exec $SHELL -l"
    else:
        remote_cmd = ""

    # -------------------------------------------------------------------------
    # 1. WINDOWS (Command Prompt / PowerShell / Windows Terminal / PuTTY / Git Bash)
    # -------------------------------------------------------------------------
    if sys.platform.startswith("win"):
        title = f"SSH - {label} ({hostname}:{port})"
        ssh_bin = _find_windows_ssh_binary()

        if ssh_bin:
            ssh_bin_quoted = f'"{ssh_bin}"' if " " in ssh_bin else ssh_bin
            extra_opts = "-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa"

            if remote_cmd:
                safe_rc = remote_cmd.replace('"', '\\"')
                if auth_type == "key" and key_file:
                    ssh_target = f'{ssh_bin_quoted} -t -i "{key_file}" {extra_opts} -p {port} {username}@{hostname} "{safe_rc}"'
                else:
                    ssh_target = f'{ssh_bin_quoted} -t {extra_opts} -p {port} {username}@{hostname} "{safe_rc}"'
            else:
                if auth_type == "key" and key_file:
                    ssh_target = f'{ssh_bin_quoted} -i "{key_file}" {extra_opts} -p {port} {username}@{hostname}'
                else:
                    ssh_target = f'{ssh_bin_quoted} {extra_opts} -p {port} {username}@{hostname}'

            # A. Coba Windows Terminal (wt.exe) jika tersedia
            if shutil.which("wt"):
                try:
                    subprocess.Popen(["wt", "--title", title, "cmd", "/k", ssh_target])
                    return {"success": True, "message": f"Membuka Windows Terminal untuk {label}"}
                except Exception:
                    pass

            # B. Standard Command Prompt Windows (cmd.exe)
            try:
                full_cmd = f'start "{title}" cmd.exe /k "{ssh_target}"'
                subprocess.Popen(full_cmd, shell=True)
                return {"success": True, "message": f"Membuka Command Prompt SSH untuk {label}"}
            except Exception as e:
                # C. Fallback ke PowerShell jika cmd gagal
                try:
                    ps_cmd = f'Start-Process powershell -ArgumentList \'-NoExit\', \'-Command\', \'{ssh_target}\''
                    subprocess.Popen(["powershell.exe", "-Command", ps_cmd])
                    return {"success": True, "message": f"Membuka PowerShell SSH untuk {label}"}
                except Exception:
                    return {"success": False, "error": f"Gagal membuka Command Prompt/PowerShell: {e}"}

        # Jika ssh.exe tidak ditemukan, coba PuTTY sebagai alternatif
        putty_exe = _find_windows_putty()
        if putty_exe:
            cmd = [putty_exe, "-ssh", "-P", str(port), "-l", username]
            if auth_type == "password" and password:
                cmd.extend(["-pw", password])
            elif auth_type == "key" and key_file and key_file.lower().endswith(".ppk"):
                cmd.extend(["-i", key_file])
            cmd.append(hostname)
            try:
                subprocess.Popen(cmd)
                return {"success": True, "message": f"Membuka PuTTY untuk {label}"}
            except Exception as e:
                return {"success": False, "error": f"Gagal membuka PuTTY: {e}"}

        # Jika Git Bash ada
        git_bash = _find_windows_git_bash()
        if git_bash:
            try:
                subprocess.Popen([git_bash, "-c", f"ssh {username}@{hostname} -p {port}"])
                return {"success": True, "message": f"Membuka Git Bash untuk {label}"}
            except Exception:
                pass

        return {
            "success": False,
            "error": "Fitur OpenSSH (ssh.exe) atau PuTTY tidak ditemukan di sistem Windows ini.\nSilakan aktifkan OpenSSH Client di Windows Settings / Optional Features."
        }

    # -------------------------------------------------------------------------
    # 2. macOS (Darwin) -> AppleScript ke Terminal.app
    # -------------------------------------------------------------------------
    if sys.platform == "darwin":
        extra_opts = "-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa"
        sshpass_bin = shutil.which("sshpass")

        if remote_cmd:
            cmd_suffix = f' "{remote_cmd}"'
        else:
            cmd_suffix = ""

        if auth_type == "key" and key_file:
            ssh_cmd = f"ssh -t -i '{key_file}' {extra_opts} -p {port} {username}@{hostname}{cmd_suffix}"
            esc_ssh = _escape_applescript(ssh_cmd)
            applescript = f'''
            tell application "Terminal"
                activate
                do script "{esc_ssh}"
            end tell
            '''
        elif auth_type == "password" and password and sshpass_bin:
            ssh_cmd = f"{sshpass_bin} -p '{password}' ssh -t {extra_opts} -p {port} {username}@{hostname}{cmd_suffix}"
            esc_ssh = _escape_applescript(ssh_cmd)
            applescript = f'''
            tell application "Terminal"
                activate
                do script "{esc_ssh}"
            end tell
            '''
        elif auth_type == "password" and password:
            ssh_cmd = f"ssh -t {extra_opts} -p {port} {username}@{hostname}{cmd_suffix}"
            esc_ssh = _escape_applescript(ssh_cmd)
            esc_pwd = _escape_applescript(password)
            applescript = f'''
            tell application "Terminal"
                activate
                set newTab to do script "{esc_ssh}"
                delay 1.5
                do script "{esc_pwd}" in newTab
            end tell
            '''
        else:
            ssh_cmd = f"ssh -t {extra_opts} -p {port} {username}@{hostname}{cmd_suffix}"
            esc_ssh = _escape_applescript(ssh_cmd)
            applescript = f'''
            tell application "Terminal"
                activate
                do script "{esc_ssh}"
            end tell
            '''

        ok, err_msg = _run_applescript(applescript)
        if ok:
            return {"success": True, "message": f"Membuka Terminal macOS untuk {label} ({hostname}:{port})"}
        else:
            return {"success": False, "error": f"Gagal membuka Terminal macOS: {err_msg}"}

    # -------------------------------------------------------------------------
    # 3. LINUX / UNIX
    # -------------------------------------------------------------------------
    terminals = [
        ("gnome-terminal", lambda c: ["gnome-terminal", "--", "bash", "-c", f"{c}; exec bash"]),
        ("x-terminal-emulator", lambda c: ["x-terminal-emulator", "-e", f"bash -c '{c}; exec bash'"]),
        ("konsole", lambda c: ["konsole", "-e", f"bash -c '{c}; exec bash'"]),
        ("xfce4-terminal", lambda c: ["xfce4-terminal", "-e", f"bash -c '{c}; exec bash'"]),
        ("tilix", lambda c: ["tilix", "-e", f"bash -c '{c}; exec bash'"]),
        ("alacritty", lambda c: ["alacritty", "-e", "bash", "-c", f"{c}; exec bash"]),
        ("kitty", lambda c: ["kitty", "bash", "-c", f"{c}; exec bash"]),
        ("xterm", lambda c: ["xterm", "-e", f"bash -c '{c}; exec bash'"]),
    ]

    if remote_cmd:
        safe_rc = remote_cmd.replace('"', '\\"')
        cmd_suffix = f' "{safe_rc}"'
    else:
        cmd_suffix = ""

    sshpass_bin = shutil.which("sshpass")
    if auth_type == "key" and key_file:
        ssh_cmd = f"ssh -t -i '{key_file}' -p {port} {username}@{hostname}{cmd_suffix}"
    elif auth_type == "password" and password and sshpass_bin:
        ssh_cmd = f"{sshpass_bin} -p '{password}' ssh -t -p {port} {username}@{hostname}{cmd_suffix}"
    else:
        ssh_cmd = f"ssh -t -p {port} {username}@{hostname}{cmd_suffix}"

    for term_bin, arg_fn in terminals:
        if shutil.which(term_bin):
            try:
                cmd = arg_fn(ssh_cmd)
                subprocess.Popen(cmd)
                return {"success": True, "message": f"Membuka {term_bin} untuk {label}"}
            except Exception:
                continue

    return {"success": False, "error": "Tidak ditemukan emulator terminal yang kompatibel di sistem Linux ini."}


def launch_local_terminal(
    initial_dir: Optional[str] = None,
    app: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Membuka Command Prompt / Terminal lokal di komputer pengguna pada direktori tertentu (initial_dir).
    """
    target_dir = initial_dir if initial_dir and os.path.exists(initial_dir) else os.path.expanduser("~")
    target_dir = os.path.abspath(target_dir)

    # 1. WINDOWS (Command Prompt cmd.exe / PowerShell / Windows Terminal)
    if sys.platform.startswith("win"):
        # A. Coba Windows Terminal jika terpasang
        if shutil.which("wt"):
            try:
                subprocess.Popen(["wt", "-d", target_dir])
                return {"success": True, "message": f"Membuka Windows Terminal di: {target_dir}"}
            except Exception:
                pass

        # B. Standard Command Prompt (cmd.exe)
        try:
            full_cmd = f'start "Command Prompt - {target_dir}" cmd.exe /k "cd /d \"{target_dir}\""'
            subprocess.Popen(full_cmd, shell=True)
            return {"success": True, "message": f"Membuka Command Prompt di: {target_dir}"}
        except Exception as e:
            # C. Fallback ke PowerShell
            try:
                ps_cmd = f'Start-Process powershell -ArgumentList \'-NoExit\', \'-Command\', \'Set-Location -LiteralPath "{target_dir}"\''
                subprocess.Popen(["powershell.exe", "-Command", ps_cmd])
                return {"success": True, "message": f"Membuka PowerShell di: {target_dir}"}
            except Exception:
                return {"success": False, "error": f"Gagal membuka Command Prompt/PowerShell: {e}"}

    # 2. macOS (Darwin)
    if sys.platform == "darwin":
        local_cmd = f"cd '{target_dir}' && clear"
        esc_cmd = _escape_applescript(local_cmd)
        applescript = f'''
        tell application "Terminal"
            activate
            do script "{esc_cmd}"
        end tell
        '''
        ok, err_msg = _run_applescript(applescript)
        if ok:
            return {"success": True, "message": f"Membuka Terminal macOS di: {target_dir}"}
        else:
            return {"success": False, "error": f"Gagal membuka Terminal macOS: {err_msg}"}

    # 3. LINUX
    terminals = [
        ("gnome-terminal", ["gnome-terminal", f"--working-directory={target_dir}"]),
        ("konsole", ["konsole", f"--workdir={target_dir}"]),
        ("xfce4-terminal", ["xfce4-terminal", f"--working-directory={target_dir}"]),
        ("tilix", ["tilix", f"--working-directory={target_dir}"]),
        ("alacritty", ["alacritty", "--working-directory", target_dir]),
        ("kitty", ["kitty", "--directory", target_dir]),
        ("x-terminal-emulator", ["x-terminal-emulator", "-e", f"bash -c 'cd \"{target_dir}\" && exec bash'"]),
        ("xterm", ["xterm", "-e", f"bash -c 'cd \"{target_dir}\" && exec bash'"]),
    ]

    for term_bin, cmd in terminals:
        if shutil.which(term_bin):
            try:
                subprocess.Popen(cmd)
                return {"success": True, "message": f"Membuka {term_bin} di: {target_dir}"}
            except Exception:
                continue

    return {"success": False, "error": "Tidak ditemukan emulator terminal yang kompatibel di sistem Linux ini."}
