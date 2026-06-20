import base64
import time
from datetime import datetime, timedelta, timezone
from threading import Lock

import jwt
import requests
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

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


class GitHubClient:
    """
    GitHub API client authenticated as the Tailord GitHub App.

    Auth flow: signs a short-lived JWT with the App's RSA private key →
    exchanges it for a per-installation Access Token → uses that for API calls.

    All calls are per-installation (per-user). There is no global cached token;
    each webhook-driven call obtains a fresh token for the specific installation.
    """

    def __init__(self) -> None:
        self._private_key: str = self._load_private_key()
        self._app_id: str = settings.github_app_id  # type: ignore[assignment]
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

    @property
    def request_count(self) -> int:
        return self._request_count

    def _get(self, path: str, params: dict | None = None) -> requests.Response:
        """Unauthenticated GET for public GitHub API endpoints (repo discovery, enrichment)."""
        self._request_count += 1
        return requests.get(
            f"{_API_BASE}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            params=params or {},
            timeout=15,
        )

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

    # ── Per-installation auth ──────────────────────────────────────────────────
    # These methods use a per-installation access token scoped to a specific user's
    # GitHub App installation. Used for webhook-driven calls and PR data fetches.

    def get_installation_token(self, installation_id: str) -> str:
        """Exchange an App JWT for a per-installation access token.

        Not cached — called once per PR webhook where frequency is low.
        Raises on HTTP error.
        """
        app_jwt = self._generate_app_jwt()
        resp = requests.post(
            f"{_API_BASE}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["token"]

    def get_pr_commits(
        self, owner: str, repo: str, pr_number: int, installation_id: str
    ) -> list[dict]:
        """Fetch commits for a pull request using a per-installation token.

        Uses get_installation_token() rather than the cached global token so that
        calls on behalf of user installations are properly scoped. Raises on HTTP error.
        """
        token = self.get_installation_token(installation_id)
        resp = requests.get(
            f"{_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/commits",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            params={"per_page": 100},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def exchange_oauth_code(self, code: str) -> dict:
        """Exchange a GitHub OAuth authorization code for user tokens.

        Requires GITHUB_APP_CLIENT_ID and GITHUB_APP_CLIENT_SECRET to be configured.
        Returns a dict containing access_token, expires_in, refresh_token,
        refresh_token_expires_in, token_type, and scope.
        Raises RuntimeError if client credentials are not configured.
        Raises requests.HTTPError on API failure.
        """
        if not settings.github_app_client_id or not settings.github_app_client_secret:
            raise RuntimeError(
                "GitHub App OAuth not configured. "
                "Set GITHUB_APP_CLIENT_ID and GITHUB_APP_CLIENT_SECRET."
            )
        resp = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={
                "client_id": settings.github_app_client_id,
                "client_secret": settings.github_app_client_secret,
                "code": code,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def refresh_user_token(self, refresh_token: str) -> dict:
        """Refresh an expired GitHub user access token.

        Returns a dict with the same shape as exchange_oauth_code.
        Raises RuntimeError if client credentials are not configured.
        Raises requests.HTTPError on API failure.
        """
        if not settings.github_app_client_id or not settings.github_app_client_secret:
            raise RuntimeError(
                "GitHub App OAuth not configured. "
                "Set GITHUB_APP_CLIENT_ID and GITHUB_APP_CLIENT_SECRET."
            )
        resp = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.github_app_client_id,
                "client_secret": settings.github_app_client_secret,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


# ── Module-level singleton ─────────────────────────────────────────────────────
# Shared across all requests. Per-installation tokens are obtained on demand
# (one call per webhook) — not cached here.

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
