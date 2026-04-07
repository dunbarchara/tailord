"""Integration tests for user CRUD and public profile endpoints."""

from tests.conftest import API_HEADERS, AUTH_HEADERS, make_user

# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------


def test_get_me_returns_user(client, approved_user):
    response = client.get("/users/me", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert (
        data["email"] == "test@example.com"
    )  # get_current_user updates email from X-User-Email header
    assert data["username_slug"] == "test-google-sub"
    assert data["status"] == "approved"


def test_get_me_upserts_new_user(client, db):
    # User doesn't exist in DB yet — get_current_user creates them
    headers = {
        "X-API-Key": "test-key",
        "X-User-Id": "brand-new-sub",
        "X-User-Email": "new@example.com",
        "X-User-Name": "New User",
    }
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "new@example.com"
    assert data["username_slug"] is not None


# ---------------------------------------------------------------------------
# PATCH /users/me
# ---------------------------------------------------------------------------


def test_patch_me_updates_slug(client, approved_user):
    response = client.patch(
        "/users/me", json={"username_slug": "my-new-slug"}, headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["username_slug"] == "my-new-slug"


def test_patch_me_slug_taken_returns_409(client, approved_user, db):
    make_user(db, google_sub="other-sub", username_slug="taken-slug")
    response = client.patch("/users/me", json={"username_slug": "taken-slug"}, headers=AUTH_HEADERS)
    assert response.status_code == 409


def test_patch_me_reserved_slug_returns_422(client, approved_user):
    response = client.patch("/users/me", json={"username_slug": "admin"}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_patch_me_slug_too_short_returns_422(client, approved_user):
    response = client.patch("/users/me", json={"username_slug": "ab"}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_patch_me_updates_profile_public(client, approved_user):
    response = client.patch("/users/me", json={"profile_public": True}, headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["profile_public"] is True


def test_patch_me_updates_pronouns(client, approved_user):
    response = client.patch("/users/me", json={"pronouns": "they/them"}, headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["pronouns"] == "they/them"


# ---------------------------------------------------------------------------
# GET /users/check-username/{slug}
# ---------------------------------------------------------------------------


def test_check_username_available(client, approved_user):
    response = client.get("/users/check-username/free-slug", headers=API_HEADERS)
    assert response.status_code == 200
    assert response.json()["available"] is True


def test_check_username_taken(client, approved_user, db):
    make_user(db, google_sub="other-sub", username_slug="taken")
    response = client.get("/users/check-username/taken", headers=API_HEADERS)
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_check_username_reserved(client):
    response = client.get("/users/check-username/admin", headers=API_HEADERS)
    assert response.json()["available"] is False


def test_check_username_too_short(client):
    response = client.get("/users/check-username/ab", headers=API_HEADERS)
    assert response.json()["available"] is False


# ---------------------------------------------------------------------------
# GET /users/public/{username_slug}
# ---------------------------------------------------------------------------


def test_get_public_user_not_public_returns_404(client, approved_user):
    # approved_user has profile_public=False (default)
    response = client.get(f"/users/public/{approved_user.username_slug}", headers=API_HEADERS)
    assert response.status_code == 404


def test_get_public_user_when_public(client, approved_user):
    client.patch("/users/me", json={"profile_public": True}, headers=AUTH_HEADERS)
    response = client.get(f"/users/public/{approved_user.username_slug}", headers=API_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["username_slug"] == approved_user.username_slug


def test_get_public_user_nonexistent_returns_404(client):
    response = client.get("/users/public/nobody-here", headers=API_HEADERS)
    assert response.status_code == 404
