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

    def get_installation_account(self, installation_id: str) -> dict:
        """Return the account (user or org) associated with an App installation.

        Uses the App JWT — no user token required. Useful when the installation
        callback does not include an OAuth code.
        """
        app_jwt = self._generate_app_jwt()
        resp = requests.get(
            f"{_API_BASE}/app/installations/{installation_id}",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("account", {})

    def delete_installation(self, installation_id: str) -> None:
        """Uninstall the GitHub App from a user's account.

        Calls DELETE /app/installations/{id} using the App JWT. After this call:
        - All existing access tokens for the installation are immediately revoked
        - GitHub stops sending webhook events for that installation
        - No new access tokens can be generated for that installation_id, ever
        - Our private key cannot restore access — the installation no longer exists

        Raises on HTTP error. If the installation is already deleted (404), that
        is treated as success — the goal (no access) is already achieved.
        """
        app_jwt = self._generate_app_jwt()
        resp = requests.delete(
            f"{_API_BASE}/app/installations/{installation_id}",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            timeout=15,
        )
        if resp.status_code == 404:
            # Already uninstalled — goal achieved
            return
        resp.raise_for_status()

    def get_installation_repositories(self, installation_id: str) -> list[dict]:
        """Fetch all repositories accessible to a GitHub App installation.

        Uses a per-installation access token. Returns the full GitHub repo objects
        for repos the user granted the App access to during installation.
        Raises on HTTP error.
        """
        token = self.get_installation_token(installation_id)
        resp = requests.get(
            f"{_API_BASE}/installation/repositories",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            params={"per_page": 100},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("repositories", [])

    def get_repo_pull_requests(
        self, owner: str, repo: str, installation_id: str, limit: int = 25
    ) -> list[dict]:
        """Fetch recent closed PRs for a repo using a per-installation token.

        Returns raw GitHub PR objects (closed, sorted by updated desc).
        Caller is responsible for filtering to merged-only.
        """
        token = self.get_installation_token(installation_id)
        resp = requests.get(
            f"{_API_BASE}/repos/{owner}/{repo}/pulls",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": limit},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

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
