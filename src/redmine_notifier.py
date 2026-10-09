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


def notifications_enabled(db: Any) -> bool:
    return db.get_setting("redmine_notify_enabled", "1") == "1"


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
            status = issue.get("status") or {}
            previous = snapshot.get(key)
            snapshot[key] = {"s": status.get("id"), "n": status.get("name", ""), "u": updated_on}
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
            str(i["id"]): {"s": (i.get("status") or {}).get("id"), "n": (i.get("status") or {}).get("name", ""), "u": i.get("updated_on", "")}
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
        # Hanya notifikasi jika status berubah dari snapshot sebelumnya
        if not previous or previous.get("s") == status.get("id"):
            return None

        old_status_name = previous.get("n") or "?"
        new_status_name = status.get("name") or "?"

        change = {
            "issue_id": issue["id"],
            "subject": issue.get("subject", ""),
            "project": (issue.get("project") or {}).get("name", ""),
            "status": new_status_name,
            "old_status": old_status_name,
            "updated_on": issue.get("updated_on", ""),
            "actor": "",
            "notes": "",
            "kind": "status",
        }

        if fetch_detail:
            try:
                detail = client.get_issue(issue["id"], include="journals")
            except RedmineError:
                detail = {}
            journals = detail.get("journals") or []
            if journals:
                # Urutkan berdasarkan waktu created_on atau id
                sorted_journals = sorted(
                    journals,
                    key=lambda j: j.get("created_on") or str(j.get("id", 0))
                )
                # Cari journal TERAKHIR yang spesifik mengubah status_id
                target_journal = None
                for j in reversed(sorted_journals):
                    details_list = j.get("details") or []
                    if any(d.get("name") == "status_id" for d in details_list):
                        target_journal = j
                        break

                # Jika tidak ditemukan detail spesifik status_id, ambil journal terakhir
                if target_journal is None:
                    target_journal = sorted_journals[-1]

                actor_user = target_journal.get("user") or {}
                actor_id = actor_user.get("id")
                actor_name = _user_name(actor_user)
                if my_id and actor_id == my_id:
                    change["actor"] = f"{actor_name} (Anda)" if actor_name else "Anda"
                else:
                    change["actor"] = actor_name
                change["notes"] = (target_journal.get("notes") or "").strip()
            elif detail:
                author_user = detail.get("author") or {}
                author_id = author_user.get("id")
                author_name = _user_name(author_user)
                if my_id and author_id == my_id:
                    change["actor"] = f"{author_name} (Anda)" if author_name else "Anda"
                else:
                    change["actor"] = author_name

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
    message = f"Status berubah: {change.get('old_status', '?')} → {change.get('status', '?')}{actor}"
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
