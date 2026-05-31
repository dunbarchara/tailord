"""Unit tests for SSRF protection in playwright_helper._assert_public_url.

All tests are pure-Python — no network access, no browser launch.
DNS resolution is patched so tests are hermetic.
"""

import socket
from unittest.mock import patch

import httpx
import pytest

from app.core.playwright_helper import _assert_public_url, _validate_request_hook


def _mock_getaddrinfo(ip: str):
    """Return a getaddrinfo patcher that resolves any hostname to *ip*."""
    return patch(
        "app.core.playwright_helper.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0))],
    )


# ── Scheme checks ─────────────────────────────────────────────────────────────


def test_http_scheme_allowed():
    with _mock_getaddrinfo("93.184.216.34"):  # example.com (public)
        _assert_public_url("http://example.com/jobs/123")  # must not raise


def test_https_scheme_allowed():
    with _mock_getaddrinfo("93.184.216.34"):
        _assert_public_url("https://example.com/jobs/123")


def test_file_scheme_rejected():
    with pytest.raises(ValueError, match="http/https"):
        _assert_public_url("file:///etc/passwd")


def test_ftp_scheme_rejected():
    with pytest.raises(ValueError, match="http/https"):
        _assert_public_url("ftp://example.com/file")


def test_gopher_scheme_rejected():
    with pytest.raises(ValueError, match="http/https"):
        _assert_public_url("gopher://example.com/")


# ── Internal hostname checks (before DNS) ────────────────────────────────────


def test_localhost_rejected():
    with pytest.raises(ValueError, match="Internal hostname"):
        _assert_public_url("http://localhost/admin")


def test_dot_local_rejected():
    with pytest.raises(ValueError, match="Internal hostname"):
        _assert_public_url("http://myservice.local/")


def test_dot_internal_rejected():
    with pytest.raises(ValueError, match="Internal hostname"):
        _assert_public_url("http://metadata.azure.internal/")


# ── Private / reserved IP checks (via DNS resolution) ────────────────────────


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "127.0.0.2",  # loopback range
        "10.0.0.1",  # RFC 1918
        "10.255.255.255",  # RFC 1918
        "172.16.0.1",  # RFC 1918
        "172.31.255.255",  # RFC 1918
        "192.168.0.1",  # RFC 1918
        "192.168.255.255",  # RFC 1918
        "169.254.169.254",  # AWS/Azure/GCP metadata endpoint
        "169.254.0.1",  # link-local
        "100.64.0.1",  # shared address space (RFC 6598)
        "0.0.0.1",  # "this" network
        "224.0.0.1",  # multicast
    ],
)
def test_private_ip_rejected(ip: str):
    with _mock_getaddrinfo(ip):
        with pytest.raises(ValueError, match="reserved/private"):
            _assert_public_url("http://evil.example.com/")


def test_ipv6_loopback_rejected():
    with patch(
        "app.core.playwright_helper.socket.getaddrinfo",
        return_value=[(socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("::1", 0, 0, 0))],
    ):
        with pytest.raises(ValueError, match="reserved/private"):
            _assert_public_url("http://evil.example.com/")


def test_public_ip_allowed():
    with _mock_getaddrinfo("8.8.8.8"):  # Google DNS — public
        _assert_public_url("https://jobs.somecompany.io/role/456")  # must not raise


# ── DNS resolution failure ────────────────────────────────────────────────────


def test_unresolvable_hostname_rejected():
    with patch(
        "app.core.playwright_helper.socket.getaddrinfo",
        side_effect=socket.gaierror("Name or service not known"),
    ):
        with pytest.raises(ValueError, match="Could not resolve"):
            _assert_public_url("https://this-does-not-exist.invalid/")


# ── Missing hostname ──────────────────────────────────────────────────────────


def test_url_without_hostname_rejected():
    with pytest.raises(ValueError, match="hostname"):
        _assert_public_url("https:///no-host")


# ── Redirect hop validation (_validate_request_hook) ─────────────────────────
# The hook is registered as an httpx event_hook["request"] so it fires for
# every hop httpx makes, including after following a redirect. These tests
# verify that a redirect to a private IP is caught even if the initial URL
# resolved to a public IP.


def test_redirect_hook_blocks_private_ip():
    """Hook must reject a redirect destination that resolves to a private IP."""
    request = httpx.Request("GET", "http://169.254.169.254/latest/meta-data/")
    with _mock_getaddrinfo("169.254.169.254"):
        with pytest.raises(ValueError, match="reserved/private"):
            _validate_request_hook(request)


def test_redirect_hook_allows_public_ip():
    """Hook must pass through a redirect destination with a public IP."""
    request = httpx.Request("GET", "https://careers.example.com/job/456")
    with _mock_getaddrinfo("93.184.216.34"):
        _validate_request_hook(request)  # must not raise


def test_redirect_hook_blocks_loopback_redirect():
    """Open redirect to localhost must be caught on the redirect hop."""
    request = httpx.Request("GET", "http://127.0.0.1/admin")
    with _mock_getaddrinfo("127.0.0.1"):
        with pytest.raises(ValueError, match="reserved/private"):
            _validate_request_hook(request)
