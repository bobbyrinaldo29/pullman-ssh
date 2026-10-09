"""Klien REST API Redmine ringan tanpa dependency pihak ketiga."""

import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

# Batas maksimum task yang diambil sekaligus (dipakai notifier untuk snapshot awal)
MAX_ISSUES = 500
PAGE_SIZE = 100

# Grup status seperti Redmine web ("open" / "closed" / "all"); status spesifik ditambahkan dari API
STATUS_FILTERS = {
    "Semua Open": "open",
    "Semua Closed": "closed",
    "Semua Status": "*",
}
DEFAULT_STATUS_FILTER = "Semua Open"


class RedmineError(RuntimeError):
    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.code = code


def normalize_base_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


class RedmineClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 15):
        self.base_url = normalize_base_url(base_url)
        self.api_key = (api_key or "").strip()
        self.timeout = timeout

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urlencode(params)
        request = Request(
            url,
            headers={
                "X-Redmine-API-Key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "DO.MBA-Pull-Manager",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 401:
                raise RedmineError("API key Redmine tidak valid atau sudah kedaluwarsa.", 401) from error
            if error.code == 403:
                raise RedmineError("Akses ditolak oleh Redmine (HTTP 403). Pastikan REST API diaktifkan.", 403) from error
            if error.code == 404:
                raise RedmineError("Data tidak ditemukan di Redmine (HTTP 404). Periksa kembali URL Redmine.", 404) from error
            raise RedmineError(f"Redmine mengembalikan error HTTP {error.code}.", error.code) from error
        except URLError as error:
            raise RedmineError(f"Tidak dapat terhubung ke Redmine: {error.reason}") from error
        except (ValueError, json.JSONDecodeError) as error:
            raise RedmineError("Respons Redmine bukan JSON yang valid. Periksa kembali URL Redmine.") from error

    def _get_all(self, path: str, key: str, params: Optional[Dict[str, Any]] = None, max_items: int = MAX_ISSUES) -> List[Dict[str, Any]]:
        """Ambil seluruh halaman dari endpoint koleksi Redmine."""
        items: List[Dict[str, Any]] = []
        offset = 0
        while len(items) < max_items:
            data = self._get(path, {**(params or {}), "limit": PAGE_SIZE, "offset": offset})
            page = data.get(key, [])
            items.extend(page)
            offset += len(page)
            if not page or offset >= int(data.get("total_count", 0)):
                break
        return items[:max_items]

    def get_current_user(self) -> Dict[str, Any]:
        """Ambil profil user pemilik API key."""
        return self._get("/users/current.json").get("user", {})

    def list_issues(self, params: Dict[str, Any], limit: int = 25, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """Ambil satu halaman issue sesuai filter. Mengembalikan (issues, total_count)."""
        data = self._get("/issues.json", {**params, "limit": limit, "offset": offset})
        return data.get("issues", []), int(data.get("total_count", 0))

    def list_my_issues(self, status: str = "open") -> List[Dict[str, Any]]:
        """Ambil semua issue yang di-assign ke user pemilik API key."""
        return self._get_all("/issues.json", "issues", {
            "assigned_to_id": "me",
            "status_id": status,
            "sort": "updated_on:desc",
        })

    def get_issue(self, issue_id: int, include: str = "journals,attachments,children,relations,watchers") -> Dict[str, Any]:
        return self._get(f"/issues/{issue_id}.json", {"include": include}).get("issue", {})

    def list_statuses(self) -> List[Dict[str, Any]]:
        return self._get("/issue_statuses.json").get("issue_statuses", [])

    def list_trackers(self) -> List[Dict[str, Any]]:
        return self._get("/trackers.json").get("trackers", [])

    def list_priorities(self) -> List[Dict[str, Any]]:
        return self._get("/enumerations/issue_priorities.json").get("issue_priorities", [])

    def list_projects(self) -> List[Dict[str, Any]]:
        return self._get_all("/projects.json", "projects", max_items=1000)

    def resolve_url(self, url: str) -> str:
        return urljoin(self.base_url + "/", url)

    def download(self, url: str, max_bytes: int = 15 * 1024 * 1024) -> bytes:
        """Unduh file (mis. gambar lampiran). API key hanya dikirim ke host Redmine sendiri."""
        url = self.resolve_url(url)
        headers = {"User-Agent": "DO.MBA-Pull-Manager"}
        if urlparse(url).hostname == urlparse(self.base_url).hostname:
            headers["X-Redmine-API-Key"] = self.api_key
        try:
            with urlopen(Request(url, headers=headers), timeout=self.timeout) as response:
                data = response.read(max_bytes + 1)
        except HTTPError as error:
            raise RedmineError(f"Gagal mengunduh file (HTTP {error.code}).", error.code) from error
        except URLError as error:
            raise RedmineError(f"Gagal mengunduh file: {error.reason}") from error
        if len(data) > max_bytes:
            raise RedmineError("Ukuran file terlalu besar untuk ditampilkan.")
        return data

    def issue_url(self, issue_id: int) -> str:
        return f"{self.base_url}/issues/{issue_id}"
