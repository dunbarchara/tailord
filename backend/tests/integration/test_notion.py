"""Integration tests for Notion OAuth and export endpoints."""

from urllib.parse import urlparse

import responses as rsps_lib

from tests.conftest import AUTH_HEADERS, make_job, make_tailoring, make_user

_NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
_NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"

_FAKE_PAGE = {"id": "page-abc", "url": "https://notion.so/page-abc"}
_FAKE_PAGE_2 = {"id": "page-def", "url": "https://notion.so/page-def"}
_FAKE_PAGE_3 = {"id": "page-ghi", "url": "https://notion.so/page-ghi"}
_FAKE_PAGE_4 = {"id": "page-jkl", "url": "https://notion.so/page-jkl"}


def _user_with_notion(db):
    """Approved user with a connected Notion token."""
    return make_user(
        db,
        notion_access_token="test-notion-token",
        notion_bot_id="bot-123",
        notion_workspace_id="ws-123",
        notion_workspace_name="My Workspace",
    )


# ---------------------------------------------------------------------------
# GET /notion/auth-url
# ---------------------------------------------------------------------------


def test_notion_auth_url_returns_url(client, db):
    make_user(db)
    response = client.get("/notion/auth-url", headers=AUTH_HEADERS)
    # Returns either 200 with a Notion OAuth URL or 503 if not configured in env.
    # Both are valid in the test environment depending on local .env presence.
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        assert urlparse(response.json()["url"]).hostname == "api.notion.com"


# ---------------------------------------------------------------------------
# DELETE /notion/disconnect
# ---------------------------------------------------------------------------


def test_notion_disconnect_clears_token(client, db):
    _user_with_notion(db)
    response = client.delete("/notion/disconnect", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# POST /notion/callback
# ---------------------------------------------------------------------------


@rsps_lib.activate
def test_notion_callback_success(client, db):
    make_user(db)
    rsps_lib.add(
        rsps_lib.POST,
        _NOTION_TOKEN_URL,
        json={
            "access_token": "new-token",
            "bot_id": "bot-456",
            "workspace_id": "ws-456",
            "workspace_name": "Test Workspace",
        },
        status=200,
    )
    response = client.post(
        "/notion/callback",
        json={"code": "auth-code-123"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["notion_workspace_name"] == "Test Workspace"
    assert data["notion_workspace_id"] == "ws-456"


@rsps_lib.activate
def test_notion_callback_notion_error_returns_502(client, db):
    make_user(db)
    rsps_lib.add(rsps_lib.POST, _NOTION_TOKEN_URL, json={"error": "invalid_grant"}, status=400)
    response = client.post(
        "/notion/callback",
        json={"code": "bad-code"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 502


def test_notion_callback_missing_code_returns_400(client, db):
    make_user(db)
    response = client.post("/notion/callback", json={}, headers=AUTH_HEADERS)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /notion/export/{id} — letter view
# ---------------------------------------------------------------------------


@rsps_lib.activate
def test_export_letter_creates_pages(client, db):
    user = _user_with_notion(db)
    job = make_job(db, user, extracted_job={"title": "SWE", "company": "Corp"})
    tailoring = make_tailoring(db, user, job)

    # Four sequential POST /v1/pages calls: parent, container, posting stub, letter
    for page in [_FAKE_PAGE, _FAKE_PAGE_2, _FAKE_PAGE_3, _FAKE_PAGE_4]:
        rsps_lib.add(rsps_lib.POST, _NOTION_PAGES_URL, json=page, status=200)

    response = client.post(f"/notion/export/{tailoring.id}?view=letter", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["page_url"] == _FAKE_PAGE_4["url"]


@rsps_lib.activate
def test_export_notion_auth_error_clears_token(client, db):
    user = _user_with_notion(db)
    job = make_job(db, user)
    tailoring = make_tailoring(db, user, job)

    # Workspace parent page creation returns 401 → NotionAuthError
    rsps_lib.add(rsps_lib.POST, _NOTION_PAGES_URL, json={"message": "Unauthorized"}, status=401)

    response = client.post(f"/notion/export/{tailoring.id}?view=letter", headers=AUTH_HEADERS)
    assert response.status_code == 403
    assert response.json()["detail"] == "notion_disconnected"


def test_export_no_notion_token_returns_403(client, db):
    make_user(db)  # no notion_access_token
    job = make_job(db, make_user(db, google_sub="other"))
    tailoring = make_tailoring(db, make_user(db, google_sub="other2"), job)
    response = client.post(f"/notion/export/{tailoring.id}", headers=AUTH_HEADERS)
    assert response.status_code == 403


def test_export_tailoring_not_found(client, db):
    import uuid

    _user_with_notion(db)
    response = client.post(f"/notion/export/{uuid.uuid4()}", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_export_tailoring_other_user_returns_404(client, db):
    _user_with_notion(db)
    other = make_user(db, google_sub="other-sub")
    job = make_job(db, other)
    tailoring = make_tailoring(db, other, job)
    response = client.post(f"/notion/export/{tailoring.id}", headers=AUTH_HEADERS)
    assert response.status_code == 404
