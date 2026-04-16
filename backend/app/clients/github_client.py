import base64
import logging
import time
from datetime import datetime, timedelta, timezone
from threading import Lock

import jwt
import requests

from app.config import settings

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_API_VERSION = "2022-11-28"
_README_VARIANTS = ["README.md", "README.rst", "README.txt", "readme.md"]
_README_MAX_CHARS = 3000
_MANIFEST_PATHS = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "Dockerfile",
]
# Refresh the installation token this many seconds before it expires (1hr validity).
_TOKEN_REFRESH_BUFFER = 300


class GitHubClient:
    """
    GitHub API client authenticated as the Tailord GitHub App.

    Auth flow: signs a short-lived JWT with the App's RSA private key →
    exchanges it for an Installation Access Token → uses that for API calls.
    Token is cached in-process and refreshed automatically before expiry.
    """

    def __init__(self) -> None:
        self._private_key: str = self._load_private_key()
        self._app_id: str = settings.github_app_id  # type: ignore[assignment]
        self._installation_id: str = settings.github_app_installation_id  # type: ignore[assignment]
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._lock = Lock()
        self._request_count: int = 0

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _load_private_key(self) -> str:
        if settings.github_app_private_key:
            return settings.github_app_private_key
        if settings.github_app_private_key_path:
            with open(settings.github_app_private_key_path) as f:
                return f.read()
        raise RuntimeError(
            "GitHub App not configured. "
            "Set GITHUB_APP_PRIVATE_KEY (PEM content) or GITHUB_APP_PRIVATE_KEY_PATH."
        )

    def _generate_app_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - 60,  # backdate 60s to absorb clock skew
            "exp": now + 540,  # 9 minutes (GitHub max is 10)
            "iss": self._app_id,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def _get_token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._token_expires_at - _TOKEN_REFRESH_BUFFER:
                return self._token

            app_jwt = self._generate_app_jwt()
            resp = requests.post(
                f"{_API_BASE}/app/installations/{self._installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": _API_VERSION,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["token"]
            expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            self._token_expires_at = expires_at.timestamp()
            logger.debug(
                "github_client: installation token refreshed, expires=%s", data["expires_at"]
            )
            return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
        }

    def _get(self, path: str, params: dict | None = None) -> requests.Response:
        self._request_count += 1
        return requests.get(
            f"{_API_BASE}{path}",
            headers=self._headers(),
            params=params or {},
            timeout=15,
        )

    @property
    def request_count(self) -> int:
        return self._request_count

    # ── Repo discovery ────────────────────────────────────────────────────────

    def get_user_repos(self, username: str) -> list[dict]:
        """
        Returns up to 20 non-fork, non-archived repos pushed within the last 2 years,
        sorted by most recently pushed.
        """
        resp = self._get(f"/users/{username}/repos", {"per_page": 100, "sort": "pushed"})
        if resp.status_code == 404:
            raise ValueError(f"GitHub user '{username}' not found")
        resp.raise_for_status()

        cutoff = datetime.now(timezone.utc) - timedelta(days=730)
        result = []
        for r in resp.json():
            if r.get("fork") or r.get("archived"):
                continue
            pushed = r.get("pushed_at")
            if pushed and datetime.fromisoformat(pushed.replace("Z", "+00:00")) < cutoff:
                continue
            result.append(r)
        return result[:20]

    # ── Per-repo signals ──────────────────────────────────────────────────────

    def get_languages(self, owner: str, repo: str) -> dict[str, int]:
        resp = self._get(f"/repos/{owner}/{repo}/languages")
        return resp.json() if resp.status_code == 200 else {}

    def get_topics(self, owner: str, repo: str) -> list[str]:
        resp = self._get(f"/repos/{owner}/{repo}/topics")
        return resp.json().get("names", []) if resp.status_code == 200 else []

    def get_file_content(self, owner: str, repo: str, path: str) -> str | None:
        """Returns decoded UTF-8 file content or None if not found / not base64-encoded."""
        resp = self._get(f"/repos/{owner}/{repo}/contents/{path}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("encoding") != "base64":
            return None
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except Exception:
            return None

    def get_readme(self, owner: str, repo: str) -> str | None:
        """Tries common README filenames in order. Returns truncated content or None."""
        for path in _README_VARIANTS:
            content = self.get_file_content(owner, repo, path)
            if content:
                return content[:_README_MAX_CHARS]
        return None

    def get_manifests(self, owner: str, repo: str) -> dict[str, str]:
        """Fetches whichever manifest/config files exist. Returns {filename: content}."""
        result = {}
        for path in _MANIFEST_PATHS:
            content = self.get_file_content(owner, repo, path)
            if content:
                result[path] = content[:2000]
        return result

    def get_first_workflow(self, owner: str, repo: str) -> str | None:
        """Returns the content of the first .github/workflows/*.yml file, if any."""
        resp = self._get(f"/repos/{owner}/{repo}/contents/.github/workflows")
        if resp.status_code != 200:
            return None
        files = resp.json()
        if not isinstance(files, list):
            return None
        yml = next((f for f in files if f.get("name", "").endswith((".yml", ".yaml"))), None)
        if not yml:
            return None
        content = self.get_file_content(owner, repo, f".github/workflows/{yml['name']}")
        return content[:1000] if content else None


# ── Module-level singleton ─────────────────────────────────────────────────────
# Shared across all requests so the installation token is cached and reused
# rather than exchanged on every call.

_client: "GitHubClient | None" = None
_client_lock = Lock()


def get_github_client() -> "GitHubClient":
    """
    Returns the process-wide GitHubClient instance.
    Thread-safe; initialised on first call.
    Returns None-safe: if GitHub App is not configured, raises RuntimeError.
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = GitHubClient()
    return _client
