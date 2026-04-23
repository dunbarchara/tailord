"""Integration tests for admin user management endpoints."""

from tests.conftest import ADMIN_AUTH_HEADERS, ADMIN_GOOGLE_SUB, AUTH_HEADERS, make_user

# Non-admin auth headers (re-use the standard test user)
_NON_ADMIN_HEADERS = AUTH_HEADERS


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_admin(db):
    return make_user(db, google_sub=ADMIN_GOOGLE_SUB, is_admin=True)


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------


def test_admin_list_users(client, db):
    admin = _make_admin(db)
    make_user(db, google_sub="user-a")
    make_user(db, google_sub="user-b", status="pending")
    response = client.get("/admin/users", headers=ADMIN_AUTH_HEADERS)
    assert response.status_code == 200
    users = response.json()
    assert len(users) == 3  # admin + two users
    ids = {u["id"] for u in users}
    assert str(admin.id) in ids


def test_admin_list_users_non_admin_returns_403(client, db):
    make_user(db)  # approved but not admin
    response = client.get("/admin/users", headers=_NON_ADMIN_HEADERS)
    assert response.status_code == 403


def test_admin_list_users_unauthenticated_returns_401(client):
    response = client.get("/admin/users", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /admin/users/{id}/approve
# ---------------------------------------------------------------------------


def test_admin_approve_user(client, db):
    _make_admin(db)
    pending = make_user(db, google_sub="pending-sub", status="pending")
    response = client.post(f"/admin/users/{pending.id}/approve", headers=ADMIN_AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_admin_approve_user_not_found(client, db):
    import uuid

    _make_admin(db)
    response = client.post(f"/admin/users/{uuid.uuid4()}/approve", headers=ADMIN_AUTH_HEADERS)
    assert response.status_code == 404


def test_admin_approve_user_invalid_uuid(client, db):
    _make_admin(db)
    response = client.post("/admin/users/not-a-uuid/approve", headers=ADMIN_AUTH_HEADERS)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /admin/users/{id}/revoke
# ---------------------------------------------------------------------------


def test_admin_revoke_user(client, db):
    _make_admin(db)
    user = make_user(db, google_sub="revokable-sub", status="approved")
    response = client.post(f"/admin/users/{user.id}/revoke", headers=ADMIN_AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_admin_revoke_admin_account_returns_400(client, db):
    admin = _make_admin(db)
    response = client.post(f"/admin/users/{admin.id}/revoke", headers=ADMIN_AUTH_HEADERS)
    assert response.status_code == 400


def test_admin_revoke_user_not_found(client, db):
    import uuid

    _make_admin(db)
    response = client.post(f"/admin/users/{uuid.uuid4()}/revoke", headers=ADMIN_AUTH_HEADERS)
    assert response.status_code == 404


def test_admin_revoke_user_invalid_uuid(client, db):
    _make_admin(db)
    response = client.post("/admin/users/not-a-uuid/revoke", headers=ADMIN_AUTH_HEADERS)
    assert response.status_code == 400
