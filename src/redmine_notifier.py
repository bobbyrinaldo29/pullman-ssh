"""Deteksi perubahan task Redmine (status / update) untuk notifikasi desktop."""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional

from redmine_service import RedmineClient, RedmineError

OWNER_KEY = "redmine_notify_owner"
CURSOR_KEY = "redmine_notify_cursor"
SNAPSHOT_KEY = "redmine_notify_snapshot"

MAX_SNAPSHOT = 3000
# Batas issue yang detail journal-nya diambil per siklus, agar polling tetap ringan
MAX_DETAIL_FETCH = 10

DEFAULT_INTERVAL_SECONDS = 300
INTERVAL_OPTIONS = {
    "Realtime": 10,
    "1 menit": 60,
    "5 menit": 300,
    "10 menit": 600,
    "15 menit": 900,
    "30 menit": 1800,
}


NOTIFY_TYPE_OPTIONS = {
    "Sistem Operasi (OS)": "os",
    "Bawaan Aplikasi": "app",
    "Keduanya (OS & Aplikasi)": "both",
}


def notifications_enabled(db: Any) -> bool:
    return db.get_setting("redmine_notify_enabled", "1") == "1"


def notify_type(db: Any) -> str:
    """Mengembalikan tipe notifikasi yang aktif ('os', 'app', atau 'both')."""
    val = db.get_setting("redmine_notify_type", "os")
    return val if val in ("os", "app", "both") else "os"


def notify_interval_seconds(db: Any) -> int:
    try:
        val = int(db.get_setting("redmine_notify_interval", "300"))
        # Jika nilai lama tersimpan dalam format menit (1, 5, 10, 15):
        if val in (1, 5, 15):
            return val * 60
        if val == 30 and db.get_setting("redmine_notify_interval_unit") != "sec":
            return 1800
        return max(5, val)
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS


def notify_interval_minutes(db: Any) -> int:
    """Helper kompatibilitas."""
    return max(1, notify_interval_seconds(db) // 60)


def _user_name(user: Optional[Dict[str, Any]]) -> str:
    return (user or {}).get("name", "")


def _make_snapshot_entry(issue: Dict[str, Any]) -> Dict[str, Any]:
    status = issue.get("status") or {}
    assignee = issue.get("assigned_to") or {}
    priority = issue.get("priority") or {}
    return {
        "s": status.get("id"),
        "n": status.get("name", ""),
        "u": issue.get("updated_on", ""),
        "a": assignee.get("name", ""),
        "d": issue.get("done_ratio", 0),
        "p": priority.get("name", ""),
        "sub": issue.get("subject", ""),
    }


class RedmineNotifier:
    """Membandingkan task terbaru dengan snapshot terakhir yang tersimpan di app_settings."""

    def __init__(self, db: Any):
        self.db = db

    def check(self) -> List[Dict[str, Any]]:
        credential = self.db.get_redmine_credential()
        if not credential:
            return []
        client = RedmineClient(credential["base_url"], credential["api_key"])

        owner = hashlib.sha256(f"{client.base_url}|{credential['api_key']}".encode("utf-8")).hexdigest()[:16]
        cursor = self.db.get_setting(CURSOR_KEY)
        if cursor is None or self.db.get_setting(OWNER_KEY) != owner:
            self._build_initial_snapshot(client, owner)
            return []

        my_id = self._my_user_id(client, credential)
        snapshot: Dict[str, Dict[str, Any]] = json.loads(self.db.get_setting(SNAPSHOT_KEY, "{}") or "{}")
        issues = self._fetch_updated_since(client, cursor)

        changes: List[Dict[str, Any]] = []
        detail_budget = MAX_DETAIL_FETCH
        for issue in issues:
            key = str(issue["id"])
            updated_on = issue.get("updated_on", "")
            previous = snapshot.get(key)
            snapshot[key] = _make_snapshot_entry(issue)
            if previous and previous.get("u") == updated_on:
                continue

            change = self._describe_change(client, issue, previous, my_id, detail_budget > 0)
            detail_budget -= 1
            if change:
                changes.append(change)

        if issues:
            cursor = max(cursor, max(i.get("updated_on", "") for i in issues))
        self._save_state(owner, cursor, snapshot)
        return changes

    # ------------------------------------------------------------------

    def _build_initial_snapshot(self, client: RedmineClient, owner: str) -> None:
        issues = client.list_my_issues("open")
        snapshot = {
            str(i["id"]): _make_snapshot_entry(i)
            for i in issues
        }
        cursor = max((i.get("updated_on", "") for i in issues), default="") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._save_state(owner, cursor, snapshot)

    def _fetch_updated_since(self, client: RedmineClient, cursor: str) -> List[Dict[str, Any]]:
        params = {"assigned_to_id": "me", "status_id": "*", "sort": "updated_on:desc"}
        if cursor:
            params["updated_on"] = f">={cursor}"
        try:
            issues, _ = client.list_issues(params, limit=50)
            if not issues and cursor:
                # Fallback jika filter updated_on kosong karena clock skew/format date: ambil 50 issue terbaru
                params_fallback = {"assigned_to_id": "me", "status_id": "*", "sort": "updated_on:desc"}
                issues, _ = client.list_issues(params_fallback, limit=50)
        except RedmineError:
            params_fallback = {"assigned_to_id": "me", "status_id": "*", "sort": "updated_on:desc"}
            issues, _ = client.list_issues(params_fallback, limit=50)
        return issues

    def _my_user_id(self, client: RedmineClient, credential: Dict[str, Any]) -> Optional[int]:
        if credential.get("user_id"):
            return int(credential["user_id"])
        user = client.get_current_user()
        if user.get("id"):
            self.db.set_setting("redmine_user_id", str(user["id"]))
        return user.get("id")

    def _describe_change(
        self, client: RedmineClient, issue: Dict[str, Any], previous: Optional[Dict[str, Any]],
        my_id: Optional[int], fetch_detail: bool
    ) -> Optional[Dict[str, Any]]:
        status = issue.get("status") or {}
        new_status_name = status.get("name") or "?"
        old_status_name = (previous.get("n") if previous else None) or ""
        status_changed = bool(previous and previous.get("s") != status.get("id"))

        change = {
            "issue_id": issue["id"],
            "subject": issue.get("subject", ""),
            "project": (issue.get("project") or {}).get("name", ""),
            "status": new_status_name,
            "old_status": old_status_name if status_changed else "",
            "updated_on": issue.get("updated_on", ""),
            "actor": "",
            "notes": "",
            "kind": "update",
            "detail_text": "",
        }

        # Kasus 1: Task baru ditugaskan ke user
        if not previous:
            change["kind"] = "assigned"
            author = issue.get("author") or {}
            actor_name = _user_name(author)
            change["actor"] = actor_name
            change["detail_text"] = "Task baru ditugaskan ke Anda"
            return change

        # Ambil detail journals jika budget mencukupi
        detail = {}
        if fetch_detail:
            try:
                detail = client.get_issue(issue["id"], include="journals")
            except RedmineError:
                detail = {}

        journals = detail.get("journals") or []
        target_journal = None
        if journals:
            sorted_journals = sorted(
                journals,
                key=lambda j: j.get("created_on") or str(j.get("id", 0))
            )
            # Ambil journal terakhir
            target_journal = sorted_journals[-1]

        if target_journal:
            actor_user = target_journal.get("user") or {}
            actor_id = actor_user.get("id")
            actor_name = _user_name(actor_user)
            if my_id and actor_id == my_id:
                change["actor"] = f"{actor_name} (Anda)" if actor_name else "Anda"
            else:
                change["actor"] = actor_name
            change["notes"] = (target_journal.get("notes") or "").strip()

            # Periksa detail perubahan atribut dalam journal
            details_list = target_journal.get("details") or []
            attr_descriptions = []
            for d in details_list:
                prop = d.get("property")
                name = d.get("name")
                if prop == "attr":
                    if name == "status_id":
                        status_changed = True
                    elif name == "done_ratio":
                        attr_descriptions.append(f"Progress diubah: {d.get('old_value', '0')}% → {d.get('new_value', '0')}%")
                    elif name == "assigned_to_id":
                        attr_descriptions.append("Assignee diubah")
                    elif name == "priority_id":
                        attr_descriptions.append("Prioritas diubah")
                elif prop == "attachment":
                    att_name = d.get("new_value") or "baru"
                    attr_descriptions.append(f"Lampiran ditambahkan ({att_name})")

            if attr_descriptions:
                change["detail_text"] = ", ".join(attr_descriptions)

        elif detail:
            author_user = detail.get("author") or {}
            author_id = author_user.get("id")
            author_name = _user_name(author_user)
            if my_id and actor_id == my_id:
                change["actor"] = f"{author_name} (Anda)" if actor_name else "Anda"
            else:
                change["actor"] = author_name

        # Tentukan tipe/kind perubahan
        if status_changed:
            change["kind"] = "status"
        elif change["notes"]:
            change["kind"] = "notes"
        elif change["detail_text"]:
            change["kind"] = "update"
        else:
            # Bandingkan dengan snapshot sebelumnya jika journal tidak didapatkan
            if previous.get("d") is not None and previous.get("d") != issue.get("done_ratio"):
                change["detail_text"] = f"Progress diubah: {previous.get('d', 0)}% → {issue.get('done_ratio', 0)}%"
            elif previous.get("a") and previous.get("a") != (issue.get("assigned_to") or {}).get("name", ""):
                change["detail_text"] = f"Assignee: {(issue.get('assigned_to') or {}).get('name', '')}"
            elif previous.get("p") and previous.get("p") != (issue.get("priority") or {}).get("name", ""):
                change["detail_text"] = f"Prioritas diubah ke {(issue.get('priority') or {}).get('name', '')}"
            else:
                change["detail_text"] = "Task diperbarui"

        return change

    def _save_state(self, owner: str, cursor: str, snapshot: Dict[str, Dict[str, Any]]) -> None:
        if len(snapshot) > MAX_SNAPSHOT:
            newest = sorted(snapshot.items(), key=lambda kv: kv[1].get("u", ""), reverse=True)[:MAX_SNAPSHOT]
            snapshot = dict(newest)
        self.db.set_setting(OWNER_KEY, owner)
        self.db.set_setting(CURSOR_KEY, cursor)
        self.db.set_setting(SNAPSHOT_KEY, json.dumps(snapshot, separators=(",", ":")))


def format_change(change: Dict[str, Any]) -> Dict[str, str]:
    """Ubah data perubahan menjadi judul & pesan notifikasi yang siap ditampilkan."""
    title = f"#{change['issue_id']} · {change['subject']}"
    actor = f" oleh {change['actor']}" if change.get("actor") else ""
    kind = change.get("kind", "")
    notes = (change.get("notes") or "").strip()
    old_status = change.get("old_status")
    new_status = change.get("status")

    if kind == "assigned":
        message = f"Task baru ditugaskan ke Anda{actor}"
    elif old_status and new_status and old_status != new_status:
        message = f"Status: {old_status} → {new_status}{actor}"
        if notes:
            clean_notes = notes.replace("\r\n", " ").replace("\n", " ").strip()
            if len(clean_notes) > 50:
                clean_notes = clean_notes[:49] + "…"
            message += f" · \"{clean_notes}\""
    elif notes:
        clean_notes = notes.replace("\r\n", " ").replace("\n", " ").strip()
        if len(clean_notes) > 70:
            clean_notes = clean_notes[:69] + "…"
        actor_prefix = f"{change['actor']}: " if change.get("actor") else "Catatan baru: "
        message = f"{actor_prefix}\"{clean_notes}\""
    elif change.get("detail_text"):
        message = f"{change['detail_text']}{actor}"
    else:
        message = f"Task diperbarui{actor}"

    return {"title": title, "message": message}


class NotificationCenter:
    """Riwayat notifikasi di memori + jumlah yang belum dibaca, dibagikan ke sidebar & view."""

    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self.items: List[Dict[str, Any]] = []
        self.unread = 0
        self._listeners: List[Any] = []

    def subscribe(self, callback) -> None:
        self._listeners.append(callback)

    def add(self, changes: List[Dict[str, Any]]) -> None:
        now = datetime.now()
        for change in changes:
            self.items.insert(0, {**change, **format_change(change), "received_at": now})
        del self.items[self.max_items:]
        self.unread += len(changes)
        self._emit()

    def mark_all_read(self) -> None:
        self.unread = 0
        self._emit()

    def clear(self) -> None:
        self.items.clear()
        self.mark_all_read()

    def _emit(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                pass
