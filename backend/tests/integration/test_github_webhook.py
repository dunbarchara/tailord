"""
Integration tests for the GitHub App webhook endpoint.

POST /integrations/github/webhook
"""

import hashlib
import hmac
import json

from app.config import settings
from tests.conftest import make_experience_source

TEST_WEBHOOK_SECRET = "test-webhook-secret-1234567890abcdef"

# Inject webhook secret before tests run
settings.github_app_webhook_secret = TEST_WEBHOOK_SECRET


def _sig(body: bytes) -> str:
    """Compute the HMAC-SHA256 signature GitHub would send."""
    digest = hmac.new(TEST_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _pr_payload(
    action: str = "closed",
    merged: bool = True,
    user_type: str = "User",
    installation_id: int = 123,
    base_ref: str = "main",
    pr_url: str = "https://github.com/owner/repo/pull/1",
) -> dict:
    return {
        "action": action,
        "installation": {"id": installation_id},
        "pull_request": {
            "number": 1,
            "title": "Add feature X",
            "body": "This PR implements feature X with better performance.",
            "html_url": pr_url,
            "merged": merged,
            "user": {"login": "testuser", "type": user_type},
            "base": {"ref": base_ref},
            "labels": [],
        },
        "repository": {
            "name": "my-repo",
            "full_name": "owner/my-repo",
            "owner": {"login": "owner"},
        },
    }


def _post_webhook(client, payload: dict, extra_headers: dict | None = None) -> object:
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": _sig(body),
        "X-GitHub-Delivery": "test-delivery-id",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    return client.post("/integrations/github/webhook", content=body, headers=headers)


# ── Signature verification ──────────────────────────────────────────────────


def test_bad_signature_returns_401(client, db, approved_user):
    body = json.dumps(_pr_payload()).encode()
    resp = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=badbadbadbad",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


def test_missing_signature_returns_401(client, db, approved_user):
    body = json.dumps(_pr_payload()).encode()
    resp = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


# ── Event type and action filtering ────────────────────────────────────────


def test_non_pr_event_returns_204(client, db, approved_user):
    body = json.dumps({"ref": "refs/heads/main"}).encode()
    resp = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": _sig(body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 204


def test_pr_opened_action_returns_204(client, db, approved_user):
    resp = _post_webhook(client, _pr_payload(action="opened"))
    assert resp.status_code == 204


def test_pr_closed_not_merged_returns_204(client, db, approved_user):
    resp = _post_webhook(client, _pr_payload(action="closed", merged=False))
    assert resp.status_code == 204


def test_bot_authored_pr_returns_204(client, db, approved_user):
    resp = _post_webhook(client, _pr_payload(user_type="Bot"))
    assert resp.status_code == 204


# ── User resolution ─────────────────────────────────────────────────────────


def test_no_experience_source_returns_204(client, db, approved_user):
    """No ExperienceSource with matching installation_id → 204."""
    resp = _post_webhook(client, _pr_payload(installation_id=999))
    assert resp.status_code == 204


# ── Idempotency ─────────────────────────────────────────────────────────────


def test_duplicate_delivery_returns_204(client, db, approved_user):
    """A CaptureSignal already exists for this PR URL → 204."""
    from app.models.database import CaptureSignal

    make_experience_source(
        db,
        approved_user,
        source_type="github",
        config={"username": "testuser", "installation_id": "123"},
    )

    pr_url = "https://github.com/owner/repo/pull/42"
    existing = CaptureSignal(
        user_id=approved_user.id,
        source_type="github_pr",
        source_ref=pr_url,
        raw_data={},
        status="processed",
    )
    db.add(existing)
    db.commit()

    resp = _post_webhook(client, _pr_payload(installation_id=123, pr_url=pr_url))
    assert resp.status_code == 204


# ── Happy path ──────────────────────────────────────────────────────────────


def test_happy_path_creates_capture_signal(client, db, approved_user):
    """Valid merged PR + matching ExperienceSource → 202 + pending CaptureSignal."""
    from unittest.mock import patch

    from app.models.database import CaptureSignal

    make_experience_source(
        db,
        approved_user,
        source_type="github",
        config={
            "username": "testuser",
            "installation_id": "123",
            "repo_config": {"owner/my-repo": {"enabled": True, "pr_capture": True}},
        },
    )

    pr_url = "https://github.com/owner/repo/pull/7"

    with patch(
        "app.api.integrations.process_github_pr_signal",
        return_value=None,
    ):
        resp = _post_webhook(client, _pr_payload(installation_id=123, pr_url=pr_url))

    assert resp.status_code == 202

    signal = (
        db.query(CaptureSignal)
        .filter(
            CaptureSignal.user_id == approved_user.id,
            CaptureSignal.source_type == "github_pr",
            CaptureSignal.source_ref == pr_url,
        )
        .first()
    )
    assert signal is not None
    assert signal.status == "pending"
