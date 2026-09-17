import os
import sqlite3
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet


class DatabaseManager:
    def __init__(self, db_path: str = "terbius.db", key_path: str = ".master.key"):
        self.db_path = db_path
        self.key_path = key_path
        self.fernet = self._load_or_generate_key()
        self._init_db()

    def _load_or_generate_key(self) -> Fernet:
        """Memuat master key untuk enkripsi, atau buat baru jika belum ada."""
        if not os.path.exists(self.key_path):
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as f:
                f.write(key)
            os.chmod(self.key_path, 0o600)  # Hak akses terbatas
        else:
            with open(self.key_path, "rb") as f:
                key = f.read()
        return Fernet(key)

    def _encrypt(self, text: Optional[str]) -> Optional[str]:
        """Menenkripsi string sensitif."""
        if text is None:
            return None
        return self.fernet.encrypt(text.encode("utf-8")).decode("utf-8")

    def _decrypt(self, cipher_text: Optional[str]) -> Optional[str]:
        """Mendekripsi string sensitif."""
        if cipher_text is None:
            return None
        return self.fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Inisialisasi tabel SQLite jika belum ada."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Tabel Group
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Tabel SSH Keys / Identities
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ssh_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    private_key_path TEXT,
                    private_key_content TEXT,  -- Encrypted
                    passphrase TEXT,           -- Encrypted
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Tabel Hosts (Dilengkapi repo_path dan git_branch)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hosts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    hostname TEXT NOT NULL,
                    port INTEGER DEFAULT 22,
                    username TEXT NOT NULL,
                    auth_type TEXT NOT NULL CHECK(auth_type IN ('password', 'key')),
                    password TEXT,             -- Encrypted
                    repo_path TEXT DEFAULT '/var/www/html',
                    git_branch TEXT,           -- Git Branch (optional)
                    git_user TEXT,             -- Git Username / Email
                    git_pass TEXT,             -- Encrypted Git Password / Personal Access Token
                    key_id INTEGER,
                    group_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (key_id) REFERENCES ssh_keys(id) ON DELETE SET NULL,
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
                );
            """)
            conn.commit()

            # Migrasi skema ringan jika file database lama belum memiliki kolom repo_path atau git_branch
            self._ensure_repo_path_column(cursor)

    def _ensure_repo_path_column(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute("PRAGMA table_info(hosts);")
        columns = [row["name"] for row in cursor.fetchall()]
        if "repo_path" not in columns:
            cursor.execute("ALTER TABLE hosts ADD COLUMN repo_path TEXT DEFAULT '/var/www/html';")
        if "git_branch" not in columns:
            cursor.execute("ALTER TABLE hosts ADD COLUMN git_branch TEXT;")
        if "git_user" not in columns:
            cursor.execute("ALTER TABLE hosts ADD COLUMN git_user TEXT;")
        if "git_pass" not in columns:
            cursor.execute("ALTER TABLE hosts ADD COLUMN git_pass TEXT;")

    # ==================== GROUPS API ====================

    def add_group(self, name: str) -> int:
        clean_name = name.strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM groups WHERE LOWER(name) = LOWER(?);", (clean_name,))
            row = cursor.fetchone()
            if row:
                return row["id"]
            cursor.execute("INSERT INTO groups (name) VALUES (?);", (clean_name,))
            conn.commit()
            return cursor.lastrowid

    def get_groups(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM groups ORDER BY name ASC;")
            return [dict(row) for row in cursor.fetchall()]

    # ==================== SSH KEYS API ====================

    def add_ssh_key(
        self,
        title: str,
        private_key_path: Optional[str] = None,
        private_key_content: Optional[str] = None,
        passphrase: Optional[str] = None
    ) -> int:
        encrypted_content = self._encrypt(private_key_content)
        encrypted_passphrase = self._encrypt(passphrase)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ssh_keys (title, private_key_path, private_key_content, passphrase)
                VALUES (?, ?, ?, ?);
            """, (title, private_key_path, encrypted_content, encrypted_passphrase))
            conn.commit()
            return cursor.lastrowid

    def get_ssh_key(self, key_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ssh_keys WHERE id = ?;", (key_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["private_key_content"] = self._decrypt(data["private_key_content"])
            data["passphrase"] = self._decrypt(data["passphrase"])
            return data

    def get_all_ssh_keys(self) -> List[Dict[str, Any]]:
        """Mengembalikan semua SSH key yang tersimpan (tanpa mendekripsi konten)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, private_key_path, created_at FROM ssh_keys ORDER BY title ASC;")
            return [dict(row) for row in cursor.fetchall()]

    # ==================== HOSTS API ====================

    def add_host(
        self,
        label: str,
        hostname: str,
        username: str,
        port: int = 22,
        auth_type: str = "password",
        password: Optional[str] = None,
        repo_path: str = "/var/www/html",
        git_branch: Optional[str] = None,
        git_user: Optional[str] = None,
        git_pass: Optional[str] = None,
        key_id: Optional[int] = None,
        group_id: Optional[int] = None
    ) -> int:
        encrypted_password = self._encrypt(password) if auth_type == "password" else None
        encrypted_git_pass = self._encrypt(git_pass) if git_pass else None
        clean_repo_path = repo_path.strip() if repo_path and repo_path.strip() else "/var/www/html"
        clean_git_branch = git_branch.strip() if git_branch and git_branch.strip() else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO hosts (label, hostname, port, username, auth_type, password, repo_path, git_branch, git_user, git_pass, key_id, group_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (label, hostname, port, username, auth_type, encrypted_password, clean_repo_path, clean_git_branch, git_user, encrypted_git_pass, key_id, group_id))
            conn.commit()
            return cursor.lastrowid

    def get_hosts(self) -> List[Dict[str, Any]]:
        return self.get_all_hosts()

    def get_all_hosts(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT h.*, g.name as group_name, k.title as key_title
                FROM hosts h
                LEFT JOIN groups g ON h.group_id = g.id
                LEFT JOIN ssh_keys k ON h.key_id = k.id
                ORDER BY h.label ASC;
            """)
            hosts = []
            for row in cursor.fetchall():
                item = dict(row)
                if item["password"]:
                    item["password"] = self._decrypt(item["password"])
                if item["git_pass"]:
                    item["git_pass"] = self._decrypt(item["git_pass"])
                hosts.append(item)
            return hosts

    def update_repo_path(self, host_id: int, new_repo_path: str) -> None:
        """Memperbarui repo_path spesifik pada host tertentu."""
        clean_path = new_repo_path.strip() if new_repo_path and new_repo_path.strip() else "/var/www/html"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE hosts SET repo_path = ? WHERE id = ?;", (clean_path, host_id))
            conn.commit()
            
    def update_host(
        self,
        host_id: int,
        label: str,
        hostname: str,
        username: str,
        port: int = 22,
        auth_type: str = "password",
        password: Optional[str] = None,
        repo_path: str = "/var/www/html",
        git_branch: Optional[str] = None,
        git_user: Optional[str] = None,
        git_pass: Optional[str] = None,
        key_id: Optional[int] = None,
        group_id: Optional[int] = None
    ) -> None:
        encrypted_password = self._encrypt(password) if auth_type == "password" else None
        encrypted_git_pass = self._encrypt(git_pass) if git_pass else None
        clean_repo_path = repo_path.strip() if repo_path and repo_path.strip() else "/var/www/html"
        clean_git_branch = git_branch.strip() if git_branch and git_branch.strip() else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE hosts
                SET label = ?, hostname = ?, port = ?, username = ?, auth_type = ?, 
                    password = ?, repo_path = ?, git_branch = ?, git_user = ?, git_pass = ?, key_id = ?, group_id = ?
                WHERE id = ?;
            """, (label, hostname, port, username, auth_type, encrypted_password, clean_repo_path, clean_git_branch, git_user, encrypted_git_pass, key_id, group_id, host_id))
            conn.commit()

    def delete_host(self, host_id: int) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM hosts WHERE id = ?;", (host_id,))
            conn.commit()


# ==================== CONTOH PENGGUNAAN ====================
if __name__ == "__main__":
    db = DatabaseManager("terbius_test.db")

    prod_group_id = db.add_group("Production Staging")

    # Tambah Host dengan Repo Path Spesifik
    db.add_host(
        label="V-TAX Staging Server",
        hostname="192.168.1.100",
        username="root",
        auth_type="password",
        password="SuperSecretPassword123!",
        repo_path="/var/www/v-tax-staging",
        group_id=prod_group_id
    )

    print("\n--- DAFTAR HOST IN DATABASE ---")
    for host in db.get_all_hosts():
        print(f"ID: {host['id']} | Label: {host['label']}")
        print(f"Target: {host['username']}@{host['hostname']}:{host['port']}")
        print(f"Repo Path: {host['repo_path']}")
        print("-" * 50)