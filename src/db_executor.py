import asyncio
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import asyncssh
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# Navicat 12+ key / iv for AES decryption (reverse-engineered, key != iv).
_NAVICAT12_KEY = b'libcckeylibcckey'
_NAVICAT12_IV = b'libcciv libcciv '


def decrypt_navicat_password(hex_str: Optional[str]) -> str:
    """Mendekripsi password terenkripsi dari file connections.ncx Navicat (skema AES Navicat 12+)."""
    if not hex_str:
        return ""
    try:
        data = bytes.fromhex(hex_str.strip())
        cipher = Cipher(algorithms.AES(_NAVICAT12_KEY), modes.CBC(_NAVICAT12_IV), backend=default_backend())
        dec = cipher.decryptor()
        padded = dec.update(data) + dec.finalize()

        # Proper PKCS7 unpad, alih-alih sekadar rstrip byte kontrol.
        if padded:
            pad_len = padded[-1]
            if 0 < pad_len <= 16:
                padded = padded[:-pad_len]

        cleaned = padded.decode('utf-8', errors='ignore').strip()
        if cleaned and all(32 <= ord(c) <= 126 for c in cleaned):
            return cleaned
    except Exception:
        pass
    return hex_str.strip()


def parse_ncx_content(file_path: str) -> List[Dict[str, Any]]:
    """Membaca file export Navicat XML (.ncx) dan mengembalikan list koneksi."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    connections = []

    for idx, elem in enumerate(root.findall("Connection"), 1):
        attr = elem.attrib
        name = attr.get("ConnectionName") or f"Database-{idx}"
        conn_type = attr.get("ConnType") or "MYSQL"
        host = attr.get("Host") or "localhost"
        port = int(attr.get("Port", 3306)) if attr.get("Port") else 3306
        username = attr.get("UserName") or "root"
        db_pass = decrypt_navicat_password(attr.get("Password", ""))
        database_name = attr.get("Database", "")

        use_ssh = (attr.get("SSH", "false").lower() == "true")
        ssh_host = attr.get("SSH_Host", "")
        ssh_port = int(attr.get("SSH_Port", 22)) if attr.get("SSH_Port") else 22
        ssh_user = attr.get("SSH_UserName", "")
        ssh_pass = decrypt_navicat_password(attr.get("SSH_Password", ""))
        ssh_key = attr.get("SSH_PrivateKey", "")

        connections.append({
            "name": name,
            "db_type": conn_type,
            "host": host,
            "port": port,
            "username": username,
            "password": db_pass,
            "database_name": database_name,
            "use_ssh": 1 if use_ssh else 0,
            "ssh_host": ssh_host,
            "ssh_port": ssh_port,
            "ssh_username": ssh_user,
            "ssh_password": ssh_pass,
            "ssh_key_filename": ssh_key,
            "group_name": "Default"
        })

    return connections


def parse_js_content(file_path: str) -> List[Dict[str, Any]]:
    """Membaca file JavaScript (.js) atau JSON (.json) yang berisi array koneksi database."""
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    # Jika file .js (misal: module.exports = [ ... ]; atau const conns = [ ... ];)
    # Ekstrak konten array JSON di dalamnya
    match = re.search(r'(\[\s*\{.*\}\s*\])', text, re.DOTALL)
    if match:
        json_text = match.group(1)
    else:
        json_text = text

    # Bersihkan trailing commas sebelum parsing
    if json_text.endswith(","):
        json_text = json_text[:-1].strip()
    json_text = re.sub(r",(\s*[}\]])", r"\1", json_text)

    raw = json.loads(json_text)
    if isinstance(raw, dict):
        raw = raw.get("connections") or raw.get("configs") or raw.get("data") or [raw]

    connections = []
    for idx, c in enumerate(raw, 1):
        if not isinstance(c, dict):
            continue
        name = c.get("name") or c.get("ConnectionName") or f"Database-{idx}"
        connections.append({
            "name": name,
            "db_type": c.get("db_type") or c.get("type") or "MYSQL",
            "host": c.get("host") or "localhost",
            "port": int(c.get("port", 3306)) if c.get("port") else 3306,
            "username": c.get("username") or c.get("user") or "root",
            "password": c.get("password") or "",
            "database_name": c.get("database_name") or c.get("database") or "",
            "use_ssh": 1 if c.get("use_ssh", True) else 0,
            "ssh_host": c.get("ssh_host") or "",
            "ssh_port": int(c.get("ssh_port", 22)) if c.get("ssh_port") else 22,
            "ssh_username": c.get("ssh_username") or c.get("ssh_user") or "",
            "ssh_password": c.get("ssh_password") or "",
            "ssh_key_filename": c.get("ssh_key_filename") or c.get("ssh_key") or "",
            "group_name": c.get("group_name") or c.get("group") or "Default"
        })

    return connections


def import_connections_from_file(file_path: str) -> List[Dict[str, Any]]:
    """Import otomatis dari .ncx, .js, atau .json."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".ncx":
        return parse_ncx_content(file_path)
    else:
        return parse_js_content(file_path)


def export_connections_to_file(connections: List[Dict[str, Any]], file_path: str, as_js: bool = False) -> None:
    """Menyimpan koneksi database ke file .json atau .js."""
    clean_list = []
    for c in connections:
        item = {
            "name": c.get("name"),
            "db_type": c.get("db_type", "MYSQL"),
            "host": c.get("host", "localhost"),
            "port": int(c.get("port", 3306)),
            "username": c.get("username", "root"),
            "password": c.get("password") or "",
            "database": c.get("database_name") or "",
            "use_ssh": bool(c.get("use_ssh", 1)),
            "ssh_host": c.get("ssh_host") or "",
            "ssh_port": int(c.get("ssh_port", 22)),
            "ssh_username": c.get("ssh_username") or "",
            "ssh_password": c.get("ssh_password") or "",
            "ssh_key": c.get("ssh_key_filename") or "",
            "group": c.get("group_name") or "Default"
        }
        clean_list.append(item)

    is_js_target = as_js or file_path.lower().endswith(".js")
    with open(file_path, "w", encoding="utf-8") as f:
        if is_js_target:
            f.write("// DO.MBA DB Blast - Database Connections Export\n")
            f.write("module.exports = " + json.dumps(clean_list, indent=2, ensure_ascii=False) + ";\n")
        else:
            json.dump(clean_list, f, indent=2, ensure_ascii=False)


async def execute_query_via_ssh(conn_info: Dict[str, Any], query: str, timeout: int = 15) -> Dict[str, Any]:
    """Mengeksekusi query SQL pada remote MySQL server melalui koneksi SSH."""
    start_time = time.time()
    ssh_host = conn_info.get("ssh_host") or conn_info.get("host")
    ssh_port = int(conn_info.get("ssh_port", 22)) if conn_info.get("ssh_port") else 22
    ssh_user = conn_info.get("ssh_username") or conn_info.get("username")
    ssh_pass = conn_info.get("ssh_password")
    ssh_key = conn_info.get("ssh_key_filename")

    client_keys = [ssh_key] if ssh_key and os.path.exists(ssh_key) else None

    options = asyncssh.SSHClientConnectionOptions(
        username=ssh_user,
        password=ssh_pass if not client_keys else None,
        client_keys=client_keys,
        kex_algs=['curve25519-sha256', 'diffie-hellman-group14-sha1', 'diffie-hellman-group1-sha1'],
        server_host_key_algs=['ssh-ed25519', 'ecdsa-sha2-nistp256', 'ssh-rsa', 'ssh-dss'],
        known_hosts=None
    )

    db_host = conn_info.get("host") or "localhost"
    db_port = int(conn_info.get("port", 3306)) if conn_info.get("port") else 3306
    db_user = conn_info.get("username") or "root"
    db_pass = conn_info.get("password") or ""
    db_name = conn_info.get("database_name") or conn_info.get("database") or ""

    # Susun perintah CLI MySQL remote
    escaped_query = query.replace('"', '\\"').replace('$', '\\$')
    pass_arg = f"-p'{db_pass}'" if db_pass else ""
    db_arg = db_name if db_name else ""

    cmd = f'mysql -h {db_host} -P {db_port} -u {db_user} {pass_arg} {db_arg} -e "{escaped_query}"'

    try:
        async with asyncssh.connect(ssh_host, port=ssh_port, options=options, login_timeout=timeout) as conn:
            result = await asyncio.wait_for(conn.run(cmd, check=False), timeout=timeout)
            elapsed = round((time.time() - start_time) * 1000)

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            if result.exit_status == 0:
                return {
                    "success": True,
                    "output": stdout if stdout else "Query OK (0 rows affected)",
                    "error": "",
                    "elapsed_ms": elapsed
                }
            else:
                return {
                    "success": False,
                    "output": stdout,
                    "error": stderr if stderr else f"Process exited with code {result.exit_status}",
                    "elapsed_ms": elapsed
                }
    except Exception as e:
        elapsed = round((time.time() - start_time) * 1000)
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "elapsed_ms": elapsed
        }


def execute_query_direct(conn_info: Dict[str, Any], query: str, timeout: int = 15) -> Dict[str, Any]:
    """Mengeksekusi query MySQL secara langsung tanpa SSH menggunakan pymysql."""
    start_time = time.time()
    try:
        import pymysql
        conn = pymysql.connect(
            host=conn_info.get("host", "localhost"),
            port=int(conn_info.get("port", 3306)),
            user=conn_info.get("username", "root"),
            password=conn_info.get("password", ""),
            database=conn_info.get("database_name") or None,
            connect_timeout=timeout,
            read_timeout=timeout,
            write_timeout=timeout
        )
        with conn.cursor() as cursor:
            # Dukung multi-statements
            cursor.execute(query)
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                # Format ke tabel sederhana
                col_widths = [max(len(str(c)), max((len(str(r[i])) for r in rows), default=0)) for i, c in enumerate(columns)]
                header_line = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
                title_line = "| " + " | ".join(f"{c:<{w}}" for c, w in zip(columns, col_widths)) + " |"
                lines = [header_line, title_line, header_line]
                for r in rows:
                    lines.append("| " + " | ".join(f"{str(v):<{w}}" for v, w in zip(r, col_widths)) + " |")
                lines.append(header_line)
                lines.append(f"{len(rows)} row(s) in set")
                output = "\n".join(lines)
            else:
                conn.commit()
                output = f"Query OK, {cursor.rowcount} row(s) affected"

        conn.close()
        elapsed = round((time.time() - start_time) * 1000)
        return {"success": True, "output": output, "error": "", "elapsed_ms": elapsed}
    except Exception as e:
        elapsed = round((time.time() - start_time) * 1000)
        return {"success": False, "output": "", "error": str(e), "elapsed_ms": elapsed}


def run_db_query(conn_info: Dict[str, Any], query: str, timeout: int = 15) -> Dict[str, Any]:
    """Fungsi utama untuk mengeksekusi query pada koneksi database (baik lewat SSH maupun langsung)."""
    if conn_info.get("use_ssh") and conn_info.get("ssh_host"):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(execute_query_via_ssh(conn_info, query, timeout))
        finally:
            loop.close()
    else:
        return execute_query_direct(conn_info, query, timeout)
