import os
import sqlite3
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet


class DatabaseManager:
    def __init__(self, db_path: str = "pullman.db", key_path: str = ".master.key"):
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

            # Credential Git global untuk seluruh eksekusi Git Pull.
            # Nama tabel dipisah agar tidak berbenturan dengan skema lama pengguna.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_git_credential (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,  -- Encrypted personal access token/password
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Tabel Hosts (satu baris = satu server SSH). Kolom db_* opsional: kalau terisi,
            # host ini SEKALIGUS dipakai sebagai koneksi DB Blast (SSH + DB dalam satu baris yang sama).
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
                    db_type TEXT,              -- Diisi jika host ini juga dipakai di DB Blast
                    db_host TEXT,
                    db_port INTEGER DEFAULT 3306,
                    db_username TEXT,
                    db_password TEXT,          -- Encrypted
                    db_database_name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (key_id) REFERENCES ssh_keys(id) ON DELETE SET NULL,
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
                );
            """)
            conn.commit()

            # Migrasi skema ringan jika file database lama belum memiliki kolom repo_path atau git_branch
            self._ensure_repo_path_column(cursor)
            self._ensure_db_blast_merge(cursor)
            conn.commit()

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

    def _ensure_db_blast_merge(self, cursor: sqlite3.Cursor) -> None:
        """Pastikan kolom db_* ada di tabel hosts, lalu gabungkan (dan hapus) tabel db_connections lama
        yang berasal dari skema sebelumnya (baik yang masih punya ssh_* sendiri, maupun yang sudah pakai
        ssh_host_id), sehingga satu host = satu baris yang dipakai bersama oleh Pull Blast dan DB Blast."""
        cursor.execute("PRAGMA table_info(hosts);")
        host_columns = [row["name"] for row in cursor.fetchall()]
        for col, ddl in (
            ("db_type", "ALTER TABLE hosts ADD COLUMN db_type TEXT;"),
            ("db_host", "ALTER TABLE hosts ADD COLUMN db_host TEXT;"),
            ("db_port", "ALTER TABLE hosts ADD COLUMN db_port INTEGER DEFAULT 3306;"),
            ("db_username", "ALTER TABLE hosts ADD COLUMN db_username TEXT;"),
            ("db_password", "ALTER TABLE hosts ADD COLUMN db_password TEXT;"),
            ("db_database_name", "ALTER TABLE hosts ADD COLUMN db_database_name TEXT;"),
        ):
            if col not in host_columns:
                cursor.execute(ddl)

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='db_connections';")
        if not cursor.fetchone():
            return

        cursor.execute("PRAGMA table_info(db_connections);")
        db_conn_columns = [row["name"] for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM db_connections;")
        rows = cursor.fetchall()

        for row in rows:
            r = dict(row)
            # Skema lama (dua kemungkinan): sudah punya ssh_host_id, atau masih simpan ssh_* sendiri.
            host_id = r.get("ssh_host_id")
            if not host_id and "ssh_host" in db_conn_columns and r.get("ssh_host"):
                host_id = self._find_or_create_host_row(
                    cursor,
                    hostname=r["ssh_host"],
                    port=r.get("ssh_port") or 22,
                    username=r.get("ssh_username") or "root",
                    password=self._decrypt(r["ssh_password"]) if r.get("ssh_password") else None,
                    key_filename=r.get("ssh_key_filename"),
                    label=r.get("name"),
                )
            if not host_id:
                # Koneksi DB langsung tanpa SSH tunnel: tetap dibuatkan Host agar datanya tidak hilang,
                # menggunakan alamat DB-nya sendiri sebagai target host.
                host_id = self._find_or_create_host_row(
                    cursor,
                    hostname=r.get("host") or "localhost",
                    port=22,
                    username=r.get("username") or "root",
                    password=None,
                    key_filename=None,
                    label=r.get("name"),
                )

            cursor.execute("""
                UPDATE hosts SET
                    db_type = ?, db_host = ?, db_port = ?, db_username = ?, db_password = ?, db_database_name = ?
                WHERE id = ?;
            """, (
                r.get("db_type") or "MYSQL",
                r.get("host") or "localhost",
                int(r.get("port") or 3306),
                r.get("username") or "root",
                r.get("password"),  # sudah dalam bentuk terenkripsi, langsung dipindah apa adanya
                r.get("database_name"),
                host_id,
            ))

        cursor.execute("DROP TABLE db_connections;")

    def _find_or_create_host_row(
        self,
        cursor: sqlite3.Cursor,
        hostname: str,
        port: Optional[int],
        username: str,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        label: Optional[str] = None,
    ) -> int:
        """Cari Host Pull Blast yang cocok (hostname+port+username); jika tidak ada, buat baru di tabel hosts."""
        clean_port = int(port) if port else 22
        cursor.execute(
            "SELECT id FROM hosts WHERE LOWER(hostname) = LOWER(?) AND port = ? AND LOWER(username) = LOWER(?);",
            (hostname, clean_port, username)
        )
        row = cursor.fetchone()
        if row:
            return row["id"]

        auth_type = "password" if password else "key"
        key_id = None
        if auth_type == "key" and key_filename:
            cursor.execute(
                "INSERT INTO ssh_keys (title, private_key_path) VALUES (?, ?);",
                (label or f"{username}@{hostname}", key_filename)
            )
            key_id = cursor.lastrowid

        clean_label = label or f"{hostname} (from DB Blast)"
        cursor.execute("""
            INSERT INTO hosts (label, hostname, port, username, auth_type, password, key_id)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            clean_label, hostname, clean_port, username, auth_type,
            self._encrypt(password) if password else None, key_id
        ))
        return cursor.lastrowid

    def find_or_create_ssh_host(
        self,
        hostname: str,
        port: Optional[int] = 22,
        username: str = "root",
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        label: Optional[str] = None,
    ) -> int:
        """API publik: cari/buat Host Pull Blast yang cocok, dipakai saat import koneksi DB Blast."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            host_id = self._find_or_create_host_row(cursor, hostname, port, username, password, key_filename, label)
            conn.commit()
            return host_id

    def get_host_by_id(self, host_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT h.*, g.name as group_name, k.title as key_title, k.private_key_path as key_private_key_path
                FROM hosts h
                LEFT JOIN groups g ON h.group_id = g.id
                LEFT JOIN ssh_keys k ON h.key_id = k.id
                WHERE h.id = ?;
            """, (host_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            if item.get("password"):
                item["password"] = self._decrypt(item["password"])
            if item.get("git_pass"):
                item["git_pass"] = self._decrypt(item["git_pass"])
            if item.get("key_private_key_path"):
                item["key_filename"] = item["key_private_key_path"]
            return item

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

    # ==================== GLOBAL GIT CREDENTIAL API ====================

    def save_global_git_credential(self, username: str, password: str) -> None:
        """Simpan satu Git username/token global dalam bentuk terenkripsi."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO global_git_credential (id, username, password, updated_at)
                VALUES (1, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    username = excluded.username,
                    password = excluded.password,
                    updated_at = CURRENT_TIMESTAMP;
            """, (username.strip(), self._encrypt(password)))
            conn.commit()

    def get_global_git_credential(self) -> Optional[Dict[str, Any]]:
        """Ambil credential Git global dan dekripsi token hanya saat diperlukan."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM global_git_credential WHERE id = 1;").fetchone()
            if not row:
                return None
            credential = dict(row)
            credential["password"] = self._decrypt(credential["password"])
            return credential

    def delete_global_git_credential(self) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM global_git_credential WHERE id = 1;")
            conn.commit()

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

    def get_all_hosts(self, decrypt_passwords: bool = False) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT h.*, g.name as group_name, k.title as key_title, k.private_key_path as key_private_key_path
                FROM hosts h
                LEFT JOIN groups g ON h.group_id = g.id
                LEFT JOIN ssh_keys k ON h.key_id = k.id
                ORDER BY h.label ASC;
            """)
            hosts = []
            for row in cursor.fetchall():
                item = dict(row)
                if decrypt_passwords:
                    if item.get("password"):
                        item["password"] = self._decrypt(item["password"])
                    if item.get("git_pass"):
                        item["git_pass"] = self._decrypt(item["git_pass"])
                if item.get("key_private_key_path"):
                    item["key_filename"] = item["key_private_key_path"]
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

    # ==================== DB CONNECTIONS (DB BLAST) ====================
    # Sejak penggabungan skema, DB Blast tidak punya tabel sendiri lagi: DB Blast menampilkan baris
    # `hosts` yang kolom db_host-nya terisi, memakai SSH + info DB dari baris yang SAMA dengan Pull Blast.
    # Menghapus/mengedit dari salah satu menu otomatis tercermin di menu lainnya karena satu baris yang sama.

    def _query_db_blast_hosts(self, cursor: sqlite3.Cursor, extra_where: str = "", params: tuple = (), decrypt_passwords: bool = False) -> List[Dict[str, Any]]:
        cursor.execute(f"""
            SELECT h.*, g.name as group_name, k.private_key_path as key_private_key_path
            FROM hosts h
            LEFT JOIN groups g ON h.group_id = g.id
            LEFT JOIN ssh_keys k ON h.key_id = k.id
            WHERE h.db_host IS NOT NULL AND h.db_host != '' {extra_where}
            ORDER BY h.label ASC;
        """, params)
        rows = []
        for row in cursor.fetchall():
            item = dict(row)
            if decrypt_passwords and item.get("password"):
                item["password"] = self._decrypt(item["password"])
            rows.append(item)
        return rows

    def _host_row_to_db_connection(self, host: Dict[str, Any], decrypt_passwords: bool) -> Dict[str, Any]:
        """Bentuk satu baris hosts (yang punya db_host terisi) jadi dict ala 'db_connections' lama,
        supaya kode UI DB Blast yang sudah ada tetap bisa dipakai tanpa perubahan."""
        item = {
            "id": host["id"],
            "name": host["label"],
            "db_type": host.get("db_type") or "MYSQL",
            "host": host.get("db_host") or "localhost",
            "port": host.get("db_port") or 3306,
            "username": host.get("db_username") or "root",
            "password": None,
            "database_name": host.get("db_database_name"),
            "use_ssh": 1,
            "ssh_host_id": host["id"],
            "group_name": host.get("group_name") or "Default",
            "ssh_host": host["hostname"],
            "ssh_port": host["port"],
            "ssh_username": host["username"],
            "ssh_password": None,
            "ssh_key_filename": None,
            "ssh_host_label": host["label"],
        }
        if decrypt_passwords:
            item["password"] = self._decrypt(host.get("db_password"))
            item["ssh_password"] = host.get("password")  # get_all_hosts/_query_db_blast_hosts sudah mendekripsi
            if host.get("auth_type") == "key":
                item["ssh_key_filename"] = host.get("key_private_key_path")
        return item

    def get_all_db_connections(self, decrypt_passwords: bool = False) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            hosts = self._query_db_blast_hosts(cursor, decrypt_passwords=decrypt_passwords)
            return [self._host_row_to_db_connection(h, decrypt_passwords) for h in hosts]

    def get_db_connections_by_ids(self, ids: List[int]) -> List[Dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            hosts = self._query_db_blast_hosts(cursor, f"AND h.id IN ({placeholders})", tuple(ids), decrypt_passwords=True)
            return [self._host_row_to_db_connection(h, True) for h in hosts]

    def get_db_connection_by_id(self, conn_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            hosts = self._query_db_blast_hosts(cursor, "AND h.id = ?", (conn_id,), decrypt_passwords=True)
            if not hosts:
                return None
            return self._host_row_to_db_connection(hosts[0], True)

    def _resolve_group_id(self, cursor: sqlite3.Cursor, group_name: Optional[str]) -> Optional[int]:
        if not group_name or not group_name.strip():
            return None
        clean = group_name.strip()
        cursor.execute("SELECT id FROM groups WHERE LOWER(name) = LOWER(?);", (clean,))
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute("INSERT INTO groups (name) VALUES (?);", (clean,))
        return cursor.lastrowid

    def set_host_db_info(
        self,
        host_id: int,
        db_type: str = "MYSQL",
        host: str = "localhost",
        port: int = 3306,
        username: str = "root",
        password: Optional[str] = None,
        database_name: Optional[str] = None,
        group_name: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        """Tempelkan (atau perbarui) info koneksi database pada Host Pull Blast yang sudah ada.
        Ini adalah satu-satunya cara DB Blast 'menyimpan' koneksi: menulis ke baris hosts yang sama."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            group_id = self._resolve_group_id(cursor, group_name)
            clean_name = name.strip() if name and name.strip() else None

            updates = [
                "db_type = ?",
                "db_host = ?",
                "db_port = ?",
                "db_username = ?",
                "db_password = ?",
                "db_database_name = ?",
            ]
            params: List[Any] = [
                db_type,
                host,
                int(port) if port else 3306,
                username,
                self._encrypt(password),
                database_name,
            ]

            if clean_name is not None:
                updates.append("label = ?")
                params.append(clean_name)

            if group_id is not None:
                updates.append("group_id = ?")
                params.append(group_id)

            params.append(host_id)
            query = f"UPDATE hosts SET {', '.join(updates)} WHERE id = ?;"
            cursor.execute(query, tuple(params))
            conn.commit()

    def add_db_connection(
        self,
        name: str,
        db_type: str = "MYSQL",
        host: str = "localhost",
        port: int = 3306,
        username: str = "root",
        password: Optional[str] = None,
        database_name: Optional[str] = None,
        use_ssh: bool = True,
        ssh_host_id: Optional[int] = None,
        group_name: str = "Default"
    ) -> int:
        clean_name = name.strip() if name and name.strip() else "Unnamed DB"
        if not ssh_host_id:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                ssh_host_id = self._find_or_create_host_row(
                    cursor,
                    hostname=host or "localhost",
                    port=22,
                    username=username or "root",
                    password=None,
                    key_filename=None,
                    label=clean_name,
                )
                conn.commit()

        self.set_host_db_info(ssh_host_id, db_type, host, port, username, password, database_name, group_name, name=clean_name)
        return ssh_host_id

    def update_db_connection(
        self,
        conn_id: int,
        name: str,
        db_type: str = "MYSQL",
        host: str = "localhost",
        port: int = 3306,
        username: str = "root",
        password: Optional[str] = None,
        database_name: Optional[str] = None,
        use_ssh: bool = True,
        ssh_host_id: Optional[int] = None,
        group_name: str = "Default"
    ) -> None:
        self.set_host_db_info(conn_id, db_type, host, port, username, password, database_name, group_name, name=name)

    def delete_db_connection(self, conn_id: int) -> None:
        """Menghapus entri DB Blast = menghapus Host Pull Blast yang sama (satu tabel, satu baris)."""
        self.delete_host(conn_id)

    def bulk_import_db_connections(self, connections: List[Dict[str, Any]]) -> int:
        """Import koneksi DB (Navicat/DBeaver/generik). SSH & DB-nya disimpan ke satu baris Host yang sama
        (dicari/dibuatkan lewat _find_or_create_host_row bila belum ada)."""
        count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for c in connections:
                name = c.get("name") or c.get("ConnectionName") or "Unnamed DB"
                ssh_host = c.get("ssh_host")
                has_ssh = bool(c.get("use_ssh", True)) and bool(ssh_host)

                if has_ssh:
                    host_id = self._find_or_create_host_row(
                        cursor,
                        hostname=ssh_host,
                        port=c.get("ssh_port") or 22,
                        username=c.get("ssh_username") or c.get("ssh_user") or "root",
                        password=c.get("ssh_password"),
                        key_filename=c.get("ssh_key") or c.get("ssh_key_filename"),
                        label=name,
                    )
                else:
                    # Tidak ada SSH tunnel di data import: tetap dibuatkan Host agar datanya tersimpan,
                    # memakai alamat DB-nya sendiri sebagai target host.
                    host_id = self._find_or_create_host_row(
                        cursor,
                        hostname=c.get("host") or "localhost",
                        port=22,
                        username=c.get("username") or c.get("user") or "root",
                        password=None,
                        key_filename=None,
                        label=name,
                    )

                group_id = self._resolve_group_id(cursor, c.get("group") or c.get("group_name") or "Default")
                cursor.execute("""
                    UPDATE hosts SET
                        db_type = ?, db_host = ?, db_port = ?, db_username = ?, db_password = ?,
                        db_database_name = ?, group_id = ?
                    WHERE id = ?;
                """, (
                    c.get("db_type") or c.get("type") or "MYSQL",
                    c.get("host") or "localhost",
                    int(c.get("port") or 3306),
                    c.get("username") or c.get("user") or "root",
                    self._encrypt(c.get("password")),
                    c.get("database") or c.get("database_name"),
                    group_id,
                    host_id,
                ))
                count += 1
            conn.commit()
        return count


# ==================== CONTOH PENGGUNAAN ====================
if __name__ == "__main__":
    db = DatabaseManager("pullman_test.db")

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
