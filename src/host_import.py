import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from db_executor import parse_ncx_content

# Fixed local-storage key DBeaver uses when no master password is set
# (reverse-engineered from DBeaver's own source, widely documented).
_DBEAVER_CRED_KEY = bytes([186, 187, 74, 159, 119, 74, 184, 83, 201, 108, 45, 101, 61, 254, 84, 74])


def _decrypt_dbeaver_credentials(data: bytes) -> Dict[str, Any]:
    """Mendekripsi credentials-config.json milik DBeaver (AES-128-CBC, IV = 16 byte pertama file)."""
    iv, ciphertext = data[:16], data[16:]
    cipher = Cipher(algorithms.AES(_DBEAVER_CRED_KEY), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    if padded:
        pad_len = padded[-1]
        if 0 < pad_len <= 16:
            padded = padded[:-pad_len]

    return json.loads(padded.decode("utf-8", errors="ignore"))


def _dbeaver_connection_to_dict(conn_id: str, conn: Dict[str, Any], creds_for_conn: Dict[str, Any]) -> Dict[str, Any]:
    cfg = conn.get("configuration") or {}
    handlers = conn.get("handlers") or {}

    ssh_handler = {}
    for handler_name, handler_val in handlers.items():
        if isinstance(handler_val, dict) and "ssh" in handler_name.lower():
            ssh_handler = handler_val
            break

    db_password = ""
    ssh_password = ""
    for cred_key, cred_val in (creds_for_conn or {}).items():
        if not isinstance(cred_val, dict):
            continue
        pwd = cred_val.get("password") or ""
        if "ssh" in cred_key.lower():
            ssh_password = ssh_password or pwd
        else:
            db_password = db_password or pwd

    use_ssh = bool(ssh_handler) and str(ssh_handler.get("enabled", True)).lower() != "false"

    ssh_key_filename = ""
    ssh_props = ssh_handler.get("properties") if isinstance(ssh_handler.get("properties"), dict) else {}
    for prop_key, prop_val in (ssh_props or {}).items():
        if "key" in prop_key.lower() and isinstance(prop_val, str) and prop_val:
            ssh_key_filename = prop_val
            break

    return {
        "name": conn.get("name") or f"Database-{conn_id}",
        "db_type": (conn.get("driver") or "MYSQL").upper(),
        "host": cfg.get("host") or "localhost",
        "port": int(cfg.get("port") or 3306),
        "username": cfg.get("user") or cfg.get("userName") or "root",
        "password": db_password,
        "database_name": cfg.get("database") or "",
        "use_ssh": 1 if use_ssh else 0,
        "ssh_host": (ssh_handler.get("host") or "") if use_ssh else "",
        "ssh_port": int(ssh_handler.get("port") or 22) if use_ssh else 22,
        "ssh_username": ((ssh_handler.get("userName") or ssh_handler.get("user") or "") if use_ssh else ""),
        "ssh_password": ssh_password if use_ssh else "",
        "ssh_key_filename": ssh_key_filename if use_ssh else "",
        "group_name": conn.get("folder") or "Default",
    }


def _parse_dbeaver_project(data_sources_raw: bytes, credentials_raw: Optional[bytes]) -> List[Dict[str, Any]]:
    """Konversi isi data-sources.json (+ credentials-config.json terenkripsi, bila ada) jadi list koneksi."""
    raw = json.loads(data_sources_raw.decode("utf-8"))
    connections = raw.get("connections", raw) if isinstance(raw, dict) else {}
    if not isinstance(connections, dict):
        connections = {}

    credentials: Dict[str, Any] = {}
    if credentials_raw:
        try:
            credentials = _decrypt_dbeaver_credentials(credentials_raw)
        except Exception:
            credentials = {}

    results = []
    for conn_id, conn in connections.items():
        if not isinstance(conn, dict):
            continue
        try:
            results.append(_dbeaver_connection_to_dict(conn_id, conn, credentials.get(conn_id, {})))
        except Exception:
            continue
    return results


def _load_dbeaver_project_archive(dbp_path: Path) -> List[Dict[str, Any]]:
    """Membaca satu atau lebih project DBeaver dari file export project (.dbp), yaitu arsip ZIP
    berisi <project>/.dbeaver/data-sources.json (+ credentials-config.json)."""
    connections: List[Dict[str, Any]] = []

    with zipfile.ZipFile(dbp_path, "r") as zf:
        names = zf.namelist()
        data_source_entries = [n for n in names if n.replace("\\", "/").endswith(".dbeaver/data-sources.json")]

        for ds_entry in data_source_entries:
            creds_entry = ds_entry[:-len("data-sources.json")] + "credentials-config.json"
            try:
                data_sources_raw = zf.read(ds_entry)
            except Exception:
                continue
            credentials_raw = zf.read(creds_entry) if creds_entry in names else None
            connections.extend(_parse_dbeaver_project(data_sources_raw, credentials_raw))

    return connections


def _load_dbeaver_connections(data_sources_path: Path) -> List[Dict[str, Any]]:
    """Membaca data-sources.json + credentials-config.json (sibling file) milik DBeaver secara langsung."""
    creds_path = data_sources_path.parent / "credentials-config.json"
    credentials_raw = creds_path.read_bytes() if creds_path.exists() else None
    return _parse_dbeaver_project(data_sources_path.read_bytes(), credentials_raw)


def connections_to_hosts(connections: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Konversi koneksi database (Navicat/DBeaver) yang punya SSH Tunnel aktif jadi kandidat Host Pull Blast."""
    hosts = []
    skipped_no_ssh = 0
    skipped_key_only = 0

    for conn in connections:
        if not conn.get("use_ssh") or not conn.get("ssh_host"):
            skipped_no_ssh += 1
            continue

        if not conn.get("ssh_password"):
            if conn.get("ssh_key_filename"):
                skipped_key_only += 1
            else:
                skipped_no_ssh += 1
            continue

        hosts.append({
            "label": conn.get("name") or conn["ssh_host"],
            "hostname": conn["ssh_host"],
            "port": int(conn.get("ssh_port") or 22),
            "username": conn.get("ssh_username") or "root",
            "auth_type": "password",
            "password": conn.get("ssh_password"),
            "repo_path": "/var/www/html",
            "git_branch": None,
            "group_name": conn.get("group_name") or "Default",
            # Info DB (dari Navicat/DBeaver) ditempel di baris Host yang sama, dipakai oleh DB Blast.
            "db_type": conn.get("db_type") or "MYSQL",
            "db_host": conn.get("host") or "localhost",
            "db_port": int(conn.get("port") or 3306),
            "db_username": conn.get("username") or "root",
            "db_password": conn.get("password") or "",
            "db_database_name": conn.get("database_name") or "",
        })

    return hosts, {"skipped_no_ssh": skipped_no_ssh, "skipped_key_only": skipped_key_only}


def import_navicat_hosts(ncx_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    connections = parse_ncx_content(ncx_path)
    return connections_to_hosts(connections)


def import_dbeaver_hosts(file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Import dari file export project DBeaver (.dbp) atau langsung dari data-sources.json."""
    path = Path(file_path)
    if zipfile.is_zipfile(path):
        connections = _load_dbeaver_project_archive(path)
    else:
        connections = _load_dbeaver_connections(path)
    return connections_to_hosts(connections)


def save_hosts_to_db(db: Any, hosts: List[Dict[str, Any]], dup_action: str) -> Dict[str, int]:
    """Simpan kandidat host hasil import ke database, menangani grup dan duplikasi label.
    Info DB (jika ada) ditempel ke baris Host yang sama, supaya langsung terpakai di DB Blast."""
    existing_hosts = {h["label"].lower(): h for h in db.get_all_hosts()}
    imported = overwritten = skipped = 0

    for h in hosts:
        label = h["label"].strip()
        group_id = db.add_group(h["group_name"]) if h.get("group_name") else None
        existing = existing_hosts.get(label.lower())
        host_id = None

        if existing:
            if dup_action == "Skip existing":
                skipped += 1
                continue
            elif dup_action == "Overwrite existing":
                db.update_host(
                    host_id=existing["id"],
                    label=label,
                    hostname=h["hostname"],
                    port=h["port"],
                    username=h["username"],
                    auth_type=h["auth_type"],
                    password=h.get("password"),
                    repo_path=h.get("repo_path", "/var/www/html"),
                    git_branch=h.get("git_branch"),
                    key_id=existing.get("key_id"),
                    group_id=group_id
                )
                host_id = existing["id"]
                overwritten += 1
            else:  # Keep both (Append)
                label = f"{label} (Imported)"

        if host_id is None:
            host_id = db.add_host(
                label=label,
                hostname=h["hostname"],
                port=h["port"],
                username=h["username"],
                auth_type=h["auth_type"],
                password=h.get("password"),
                repo_path=h.get("repo_path", "/var/www/html"),
                git_branch=h.get("git_branch"),
                group_id=group_id
            )
            imported += 1

        if h.get("db_host"):
            db.set_host_db_info(
                host_id,
                db_type=h.get("db_type") or "MYSQL",
                host=h["db_host"],
                port=h.get("db_port") or 3306,
                username=h.get("db_username") or "root",
                password=h.get("db_password"),
                database_name=h.get("db_database_name"),
            )

    return {"imported": imported, "overwritten": overwritten, "skipped": skipped}
