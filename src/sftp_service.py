import asyncio
from datetime import datetime
import os
from pathlib import Path
import stat
from typing import Any, Callable, Dict, List, Optional, Tuple
import warnings

import asyncssh
from cryptography.utils import CryptographyDeprecationWarning

warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)


def _format_size(size_bytes: int) -> str:
    """Format bytes to human readable format (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_permissions(mode: Optional[int]) -> str:
    """Format file mode to standard rwxrwxrwx string."""
    if mode is None:
        return "----------"
    return stat.filemode(mode)


def _get_connection_options(host: Dict[str, Any]) -> Tuple[asyncssh.SSHClientConnectionOptions, str, int]:
    hostname = host.get("hostname", "")
    port = int(host.get("port", 22))
    username = host.get("username", "root")
    auth_type = host.get("auth_type", "password")

    client_keys = None
    if auth_type == "key" and host.get("key_filename"):
        key_path = Path(host["key_filename"])
        if key_path.exists():
            client_keys = [str(key_path)]

    password = host.get("password") if auth_type == "password" else None
    if password is None and not client_keys and host.get("password"):
        password = host.get("password")

    options = asyncssh.SSHClientConnectionOptions(
        username=username,
        password=password,
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
    return options, hostname, port


class SFTPService:
    """Backend service untuk operasi SFTP berkecepatan tinggi."""

    @staticmethod
    async def _async_list_dir(host: Dict[str, Any], remote_path: str) -> Dict[str, Any]:
        options, hostname, port = _get_connection_options(host)
        remote_path = remote_path.strip() or "/"
        
        try:
            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                async with conn.start_sftp_client() as sftp:
                    # Resolve realpath
                    real_path = await sftp.realpath(remote_path)
                    items: List[Dict[str, Any]] = []
                    
                    async for entry in sftp.scandir(real_path):
                        filename = entry.filename
                        if filename in (".", ".."):
                            continue
                        
                        attrs = entry.attrs
                        is_dir = stat.S_ISDIR(attrs.permissions) if attrs.permissions is not None else False
                        is_link = stat.S_ISLNK(attrs.permissions) if attrs.permissions is not None else False
                        
                        size = attrs.size or 0
                        mtime = attrs.mtime
                        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else "-"
                        perm_str = _format_permissions(attrs.permissions)
                        
                        # File extension
                        ext = Path(filename).suffix.lower() if not is_dir else ""
                        
                        items.append({
                            "name": filename,
                            "path": f"{real_path.rstrip('/')}/{filename}",
                            "is_dir": is_dir,
                            "is_link": is_link,
                            "size_bytes": size,
                            "size_str": "-" if is_dir else _format_size(size),
                            "permissions": perm_str,
                            "mtime_str": mtime_str,
                            "mtime": mtime or 0,
                            "ext": ext
                        })
                    
                    # Sort: direktori terlebih dahulu (A-Z), lalu file (A-Z)
                    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
                    
                    return {
                        "success": True,
                        "current_path": real_path,
                        "items": items,
                        "error": None
                    }
        except Exception as e:
            return {
                "success": False,
                "current_path": remote_path,
                "items": [],
                "error": str(e)
            }

    @staticmethod
    def list_dir(host: Dict[str, Any], remote_path: str) -> Dict[str, Any]:
        """Menjalankan scandir secara synchronous via event loop."""
        return asyncio.run(SFTPService._async_list_dir(host, remote_path))

    @staticmethod
    async def _async_download_file(
        host: Dict[str, Any], 
        remote_path: str, 
        local_path: str, 
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[bool, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        try:
            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                async with conn.start_sftp_client() as sftp:
                    def prog(srcpath, dstpath, bytes_copied, total_bytes):
                        if progress_cb and total_bytes:
                            progress_cb(bytes_copied, total_bytes)

                    await sftp.get(remote_path, local_path, progress_handler=prog)
                    return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def download_file(
        host: Dict[str, Any], 
        remote_path: str, 
        local_path: str, 
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[bool, Optional[str]]:
        return asyncio.run(SFTPService._async_download_file(host, remote_path, local_path, progress_cb))

    @staticmethod
    async def _async_upload_file(
        host: Dict[str, Any], 
        local_path: str, 
        remote_path: str, 
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[bool, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        try:
            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                async with conn.start_sftp_client() as sftp:
                    def prog(srcpath, dstpath, bytes_copied, total_bytes):
                        if progress_cb and total_bytes:
                            progress_cb(bytes_copied, total_bytes)

                    await sftp.put(local_path, remote_path, progress_handler=prog)
                    return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def upload_file(
        host: Dict[str, Any], 
        local_path: str, 
        remote_path: str, 
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[bool, Optional[str]]:
        return asyncio.run(SFTPService._async_upload_file(host, local_path, remote_path, progress_cb))

    @staticmethod
    async def _async_read_file_text(
        host: Dict[str, Any], 
        remote_path: str, 
        max_bytes: int = 2 * 1024 * 1024
    ) -> Tuple[bool, str, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        try:
            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                async with conn.start_sftp_client() as sftp:
                    async with sftp.open(remote_path, 'rb') as f:
                        data = await f.read(max_bytes)
                        try:
                            text = data.decode('utf-8')
                        except UnicodeDecodeError:
                            text = data.decode('latin-1', errors='replace')
                        return True, text, None
        except Exception as e:
            return False, "", str(e)

    @staticmethod
    def read_file_text(host: Dict[str, Any], remote_path: str) -> Tuple[bool, str, Optional[str]]:
        return asyncio.run(SFTPService._async_read_file_text(host, remote_path))

    @staticmethod
    async def _async_read_file_sudo(
        host: Dict[str, Any],
        remote_path: str
    ) -> Tuple[bool, str, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        try:
            safe_path = remote_path.replace("'", "'\\''")
            password = host.get("password")
            if password:
                escaped_pass = password.replace("'", "'\\''")
                cmd = f"printf '%s\\n' '{escaped_pass}' | sudo -S -p '' cat -- '{safe_path}'"
            else:
                cmd = f"sudo -n cat -- '{safe_path}' 2>/dev/null || sudo cat -- '{safe_path}'"

            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                res = await conn.run(cmd, check=False)
                if res.exit_status == 0:
                    return True, res.stdout, None
                else:
                    err_msg = (res.stderr or "").strip() or f"Exit status {res.exit_status}"
                    # Fallback ke pembacaan SFTP standar bila sudo tidak diperlukan
                    ok_sftp, content_sftp, _ = await SFTPService._async_read_file_text(host, remote_path)
                    if ok_sftp:
                        return True, content_sftp, None
                    return False, "", err_msg
        except Exception as e:
            return False, "", str(e)

    @staticmethod
    def read_file_sudo(host: Dict[str, Any], remote_path: str) -> Tuple[bool, str, Optional[str]]:
        return asyncio.run(SFTPService._async_read_file_sudo(host, remote_path))

    @staticmethod
    async def _async_write_file_text(
        host: Dict[str, Any], 
        remote_path: str, 
        text_content: str, 
        encoding: str = "utf-8"
    ) -> Tuple[bool, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        try:
            data = text_content.encode(encoding)
            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                async with conn.start_sftp_client() as sftp:
                    async with sftp.open(remote_path, 'wb') as f:
                        await f.write(data)
                        return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def write_file_text(host: Dict[str, Any], remote_path: str, text_content: str) -> Tuple[bool, Optional[str]]:
        return asyncio.run(SFTPService._async_write_file_text(host, remote_path, text_content))

    @staticmethod
    async def _async_write_file_sudo(
        host: Dict[str, Any],
        remote_path: str,
        text_content: str,
        encoding: str = "utf-8"
    ) -> Tuple[bool, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        import uuid
        tmp_name = f".pullman_sudo_{uuid.uuid4().hex[:8]}.tmp"
        tmp_path = f"/tmp/{tmp_name}"
        try:
            data = text_content.encode(encoding)
            safe_target = remote_path.replace("'", "'\\''")
            password = host.get("password")

            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                # 1. Upload ke temp path di /tmp via SFTP
                async with conn.start_sftp_client() as sftp:
                    async with sftp.open(tmp_path, 'wb') as f:
                        await f.write(data)

                # 2. Pindahkan dengan sudo cp ke target path dan hapus file temp
                if password:
                    escaped_pass = password.replace("'", "'\\''")
                    cmd = f"printf '%s\\n' '{escaped_pass}' | sudo -S -p '' cp -f '{tmp_path}' '{safe_target}' && printf '%s\\n' '{escaped_pass}' | sudo -S -p '' rm -f '{tmp_path}'"
                else:
                    cmd = f"sudo -n cp -f '{tmp_path}' '{safe_target}' && sudo -n rm -f '{tmp_path}'"

                res = await conn.run(cmd, check=False)
                if res.exit_status == 0:
                    return True, None
                else:
                    try:
                        await conn.run(f"rm -f '{tmp_path}'", check=False)
                    except Exception:
                        pass
                    err_msg = (res.stderr or "").strip() or f"Sudo write failed (exit code {res.exit_status})"
                    return False, err_msg
        except Exception as e:
            return False, str(e)

    @staticmethod
    def write_file_sudo(host: Dict[str, Any], remote_path: str, text_content: str) -> Tuple[bool, Optional[str]]:
        return asyncio.run(SFTPService._async_write_file_sudo(host, remote_path, text_content))

    @staticmethod
    async def _async_delete_item(host: Dict[str, Any], remote_path: str, is_dir: bool = False) -> Tuple[bool, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        try:
            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                async with conn.start_sftp_client() as sftp:
                    if is_dir:
                        # Recursive rmdir or simple rmdir
                        await sftp.rmtree(remote_path)
                    else:
                        await sftp.remove(remote_path)
                    return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def delete_item(host: Dict[str, Any], remote_path: str, is_dir: bool = False) -> Tuple[bool, Optional[str]]:
        return asyncio.run(SFTPService._async_delete_item(host, remote_path, is_dir))

    @staticmethod
    async def _async_create_dir(host: Dict[str, Any], remote_path: str) -> Tuple[bool, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        try:
            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                async with conn.start_sftp_client() as sftp:
                    await sftp.mkdir(remote_path)
                    return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_dir(host: Dict[str, Any], remote_path: str) -> Tuple[bool, Optional[str]]:
        return asyncio.run(SFTPService._async_create_dir(host, remote_path))

    @staticmethod
    async def _async_create_file(host: Dict[str, Any], remote_path: str, content: str = "") -> Tuple[bool, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        try:
            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                async with conn.start_sftp_client() as sftp:
                    async with sftp.open(remote_path, 'w') as f:
                        if content:
                            await f.write(content)
                    return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_file(host: Dict[str, Any], remote_path: str, content: str = "") -> Tuple[bool, Optional[str]]:
        return asyncio.run(SFTPService._async_create_file(host, remote_path, content))

    @staticmethod
    async def _async_rename(host: Dict[str, Any], old_path: str, new_path: str) -> Tuple[bool, Optional[str]]:
        options, hostname, port = _get_connection_options(host)
        try:
            async with asyncssh.connect(hostname, port=port, options=options, login_timeout=15) as conn:
                async with conn.start_sftp_client() as sftp:
                    await sftp.rename(old_path, new_path)
                    return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def rename(host: Dict[str, Any], old_path: str, new_path: str) -> Tuple[bool, Optional[str]]:
        return asyncio.run(SFTPService._async_rename(host, old_path, new_path))
