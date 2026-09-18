"""Check published GitHub releases without adding third-party dependencies."""

from dataclasses import dataclass
import json
from typing import Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GITHUB_RELEASES_URL = "https://github.com/bobbyrinaldo29/pullman-ssh/releases"
GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/bobbyrinaldo29/pullman-ssh/releases/latest"


@dataclass(frozen=True)
class UpdateCheckResult:
    latest_version: str
    release_url: str
    update_available: bool


def _version_tuple(version: str) -> Tuple[int, ...]:
    """Convert tags such as v1.2.0 into a comparable numeric tuple."""
    clean_version = version.strip().lower().lstrip("v")
    numeric_part = clean_version.split("-", 1)[0]
    if not numeric_part or not all(part.isdigit() for part in numeric_part.split(".")):
        raise ValueError(f"Tag release tidak memakai format versi numerik: {version}")
    return tuple(int(part) for part in numeric_part.split("."))


def _is_newer(latest: str, current: str) -> bool:
    latest_parts = _version_tuple(latest)
    current_parts = _version_tuple(current)
    length = max(len(latest_parts), len(current_parts))
    return latest_parts + (0,) * (length - len(latest_parts)) > current_parts + (0,) * (length - len(current_parts))


def check_for_update(current_version: str, timeout: int = 8) -> UpdateCheckResult:
    """Read the latest stable GitHub Release and compare it with local version."""
    request = Request(
        GITHUB_LATEST_RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "DO.MBA-Pull-Manager"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            release = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            raise RuntimeError("Belum ada GitHub Release yang dipublikasikan.") from error
        raise RuntimeError(f"GitHub tidak dapat diakses (HTTP {error.code}).") from error
    except URLError as error:
        raise RuntimeError("Tidak dapat terhubung ke GitHub. Periksa koneksi internet.") from error

    latest_version = release.get("tag_name")
    if not latest_version:
        raise RuntimeError("GitHub Release tidak memiliki tag versi.")

    return UpdateCheckResult(
        latest_version=latest_version,
        release_url=release.get("html_url") or GITHUB_RELEASES_URL,
        update_available=_is_newer(latest_version, current_version),
    )
