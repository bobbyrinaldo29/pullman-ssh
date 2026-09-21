import base64
import json
import os
from typing import Any, Dict, List, Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PBKDF2_ITERATIONS = 480000


def _derive_fernet_key(passphrase: str, salt: bytes) -> Fernet:
    """Menurunkan Fernet key dari passphrase menggunakan PBKDF2HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))
    return Fernet(key)


def export_data(
    hosts: List[Dict[str, Any]],
    groups: List[Dict[str, Any]],
    include_ssh_pass: bool = False,
    include_git_creds: bool = False,
    passphrase: Optional[str] = None
) -> Dict[str, Any]:
    """
    Menyusun struktur data export.
    Jika include_ssh_pass atau include_git_creds True, data WAJIB dienkripsi menggunakan passphrase.
    """
    should_encrypt = (include_ssh_pass or include_git_creds)

    if should_encrypt and (not passphrase or not passphrase.strip()):
        raise ValueError("Passphrase diperlukan untuk mengenkripsi kredensial pada file export.")

    clean_groups = [g["name"] for g in groups if g.get("name")]

    clean_hosts = []
    for h in hosts:
        item = {
            "label": h["label"],
            "hostname": h["hostname"],
            "port": int(h.get("port", 22)),
            "username": h["username"],
            "auth_type": h.get("auth_type", "password"),
            "repo_path": h.get("repo_path", "/var/www/html"),
            "git_branch": h.get("git_branch"),
            "group_name": h.get("group_name")
        }

        # Kredensial SSH
        if include_ssh_pass and h.get("password"):
            item["password"] = h["password"]
        else:
            item["password"] = None

        # Kredensial Git
        if include_git_creds:
            item["git_user"] = h.get("git_user")
            item["git_pass"] = h.get("git_pass")
        else:
            item["git_user"] = None
            item["git_pass"] = None

        clean_hosts.append(item)

    payload = {
        "groups": clean_groups,
        "hosts": clean_hosts
    }

    if should_encrypt:
        salt = os.urandom(16)
        fernet = _derive_fernet_key(passphrase.strip(), salt)
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        encrypted_token = fernet.encrypt(payload_bytes).decode("utf-8")

        return {
            "pullman_version": "1.1",
            "encrypted": True,
            "kdf": "PBKDF2HMAC-SHA256",
            "iterations": PBKDF2_ITERATIONS,
            "salt": salt.hex(),
            "payload": encrypted_token
        }
    else:
        return {
            "pullman_version": "1.1",
            "encrypted": False,
            "data": payload
        }


def save_export_file(file_path: str, data: Dict[str, Any]) -> None:
    """Menyimpan data export ke dalam file JSON."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def inspect_export_file(file_path: str) -> Dict[str, Any]:
    """Membaca metadata file export tanpa melakukan dekripsi."""
    if not os.path.exists(file_path):
        raise FileNotFoundError("File tidak ditemukan.")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or "pullman_version" not in data:
        raise ValueError("File bukan format export Pullman yang valid.")

    return {
        "version": data.get("pullman_version"),
        "encrypted": data.get("encrypted", False),
        "kdf": data.get("kdf")
    }


def load_export_file(file_path: str, passphrase: Optional[str] = None) -> Tuple[Dict[str, Any], bool]:
    """
    Membaca dan mendekripsi file export Pullman.
    Mengembalikan (payload_dict, is_encrypted).
    payload_dict memiliki format {"groups": [...], "hosts": [...]}.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or "pullman_version" not in data:
        raise ValueError("Format file export tidak dikenali.")

    is_encrypted = data.get("encrypted", False)

    if is_encrypted:
        if not passphrase:
            raise ValueError("File ini terenkripsi. Silakan masukkan passphrase.")

        salt_hex = data.get("salt")
        payload_token = data.get("payload")

        if not salt_hex or not payload_token:
            raise ValueError("Data enkripsi pada file rusak atau tidak lengkap.")

        salt = bytes.fromhex(salt_hex)
        fernet = _derive_fernet_key(passphrase.strip(), salt)

        try:
            decrypted_bytes = fernet.decrypt(payload_token.encode("utf-8"))
            payload = json.loads(decrypted_bytes.decode("utf-8"))
        except (InvalidToken, Exception):
            raise ValueError("Passphrase salah atau isi file telah rusak.")

        return payload, True
    else:
        payload = data.get("data", {})
        return payload, False
