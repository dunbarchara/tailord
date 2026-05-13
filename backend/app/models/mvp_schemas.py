import ipaddress
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, model_validator

# ── SSRF protection for job_url ───────────────────────────────────────────────
#
# Playwright fetches whatever URL it's given, so we must reject URLs that point
# at internal infrastructure before the request leaves the process.
#
# Always blocked (both local and production):
#   169.254.169.254 — Azure IMDS / AWS EC2 instance metadata (exposes managed
#                     identity tokens and instance credentials)
#   168.63.129.16   — Azure wire server (DHCP, health probes)
#
# Blocked in production only (localhost allowed in local dev for mock testing):
#   localhost, 127.x.x.x, ::1 — loopback
#
# IP ranges blocked in both environments (RFC 1918 + link-local):
#   10/8, 172.16/12, 192.168/16 — private LAN
#   169.254/16                   — link-local (covers IMDS by range too)
#   fc00::/7                     — IPv6 unique local
#
# Known gap: DNS-based SSRF (a public hostname that resolves to a private IP)
# is not blocked here. Mitigate at the infra layer via Azure Container App
# egress policies or a VNet with no route to private subnets.

_SSRF_ALWAYS_BLOCKED_HOSTS = frozenset(
    {
        "169.254.169.254",
        "168.63.129.16",
    }
)

_SSRF_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
]

_SSRF_LOOPBACK_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
]


def _validate_job_url(url: str, is_local: bool) -> None:
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("Invalid URL.")

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Job URL must use http or https.")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("Job URL has no host.")

    if host in _SSRF_ALWAYS_BLOCKED_HOSTS:
        raise ValueError("That URL is not allowed.")

    # Localhost by name — allowed in local dev for mock page testing, blocked in prod
    if not is_local and host == "localhost":
        raise ValueError("That URL is not allowed.")

    # IP address range checks
    try:
        addr = ipaddress.ip_address(host)
        networks = list(_SSRF_PRIVATE_NETWORKS)
        if not is_local:
            networks += _SSRF_LOOPBACK_NETWORKS
        for network in networks:
            if addr in network:
                raise ValueError("That URL points to an internal or private address.")
    except ValueError as exc:
        if "internal" in str(exc) or "not allowed" in str(exc):
            raise
        # host is not an IP literal — fine, it's a regular hostname


class ProfileInput(BaseModel):
    resume_text: str
    github_username: str


class JobInput(BaseModel):
    job_url: str


class GenerateInput(BaseModel):
    job_id: str


class GeneratedOutput(BaseModel):
    content: str


class TailoringCreate(BaseModel):
    job_url: str | None = None
    company: str | None = None
    title: str | None = None
    description: str | None = None
    skip_validation: bool = False

    @model_validator(mode="after")
    def check_input(self) -> "TailoringCreate":
        has_url = bool(self.job_url and self.job_url.strip())
        has_manual = bool(self.company and self.title and self.description)
        if not has_url and not has_manual:
            raise ValueError("Provide a job URL or fill in company, title, and description.")
        return self


class TailoringResponse(BaseModel):
    id: str
    title: Optional[str]
    company: Optional[str]
    job_url: str
    generated_output: str
    created_at: str


class TailoringListItem(BaseModel):
    id: str
    title: Optional[str]
    company: Optional[str]
    created_at: str
