import json
import re
import os
import sys

# Tambahkan src ke path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from export_service import export_data

def main():
    base_dir = os.path.dirname(__file__)
    versi1_path = os.path.join(base_dir, "Versi 1.json")
    backup_path = os.path.join(base_dir, "Versi 1.original.json")

    with open(versi1_path, "r", encoding="utf-8") as f:
        raw_text = f.read().strip()

    # Simpan backup jika belum ada
    if not os.path.exists(backup_path):
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(raw_text)

    # Bersihkan format JSON sshfs.configs jika ada trailing comma atau missing bracket
    clean_text = raw_text
    if clean_text.endswith(","):
        clean_text = clean_text[:-1].strip()
    clean_text = re.sub(r",(\s*[}\]])", r"\1", clean_text)
    if not clean_text.startswith("{"):
        clean_text = "{" + clean_text + "}"

    raw_data = json.loads(clean_text)
    configs = raw_data.get("sshfs.configs", [])

    groups = sorted(list(set(c.get("group", "Default") for c in configs if c.get("group"))))

    hosts = []
    for c in configs:
        host_item = {
            "label": c.get("label") or c.get("name"),
            "hostname": c.get("host"),
            "port": int(c.get("port", 22)),
            "username": c.get("username"),
            "auth_type": "password",
            "password": c.get("password"),
            "repo_path": c.get("root") or "/var/www/html",
            "git_branch": c.get("git_branch"),
            "group_name": c.get("group"),
            "git_user": None,
            "git_pass": None
        }
        hosts.append(host_item)

    # 1. Versi 1.json format Terbius Unencrypted (Bisa langsung di-import di DO.MBA Pull Manager tanpa passphrase)
    terbius_plain = {
        "terbius_version": "1.0",
        "encrypted": False,
        "data": {
            "groups": groups,
            "hosts": hosts
        }
    }

    with open(versi1_path, "w", encoding="utf-8") as f:
        json.dump(terbius_plain, f, indent=2, ensure_ascii=False)

    # 2. Versi 1_encrypted.json format Terbius Encrypted (Sama persis struktur Versi 2.txt dengan passphrase: 'password' atau '123456')
    encrypted_export = export_data(
        hosts=hosts,
        groups=[{"name": g} for g in groups],
        include_ssh_pass=True,
        include_git_creds=False,
        passphrase="password"
    )

    encrypted_path = os.path.join(base_dir, "Versi 1_encrypted.json")
    with open(encrypted_path, "w", encoding="utf-8") as f:
        json.dump(encrypted_export, f, indent=2, ensure_ascii=False)

    print(f"Berhasil mengonversi {len(hosts)} host dan {len(groups)} group:")
    for g in groups:
        count = sum(1 for h in hosts if h.get("group_name") == g)
        print(f"  - Group '{g}': {count} host")

if __name__ == "__main__":
    main()
