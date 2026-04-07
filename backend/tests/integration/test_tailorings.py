"""Integration tests for tailoring CRUD, sharing, and public access."""

from tests.conftest import API_HEADERS, AUTH_HEADERS, make_job, make_tailoring, make_user

# ---------------------------------------------------------------------------
# GET /tailorings
# ---------------------------------------------------------------------------


def test_list_tailorings_empty(client, approved_user):
    response = client.get("/tailorings", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_list_tailorings_returns_own(client, approved_user, db):
    job = make_job(db, approved_user)
    make_tailoring(db, approved_user, job)
    response = client.get("/tailorings", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["company"] == "Acme"
    assert data[0]["title"] == "Engineer"


def test_list_tailorings_excludes_other_users(client, approved_user, db):
    other = make_user(db, google_sub="other-sub")
    job = make_job(db, other)
    make_tailoring(db, other, job)
    response = client.get("/tailorings", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /tailorings/{id}
# ---------------------------------------------------------------------------


def test_get_tailoring(client, approved_user, db):
    job = make_job(db, approved_user, extracted_job={"title": "SWE", "company": "Corp"})
    tailoring = make_tailoring(db, approved_user, job)
    response = client.get(f"/tailorings/{tailoring.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(tailoring.id)
    assert data["title"] == "SWE"
    assert data["company"] == "Corp"
    assert data["generation_status"] == "ready"


def test_get_tailoring_not_found(client, approved_user):
    import uuid

    fake_id = uuid.uuid4()
    response = client.get(f"/tailorings/{fake_id}", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_get_tailoring_other_user_returns_404(client, approved_user, db):
    other = make_user(db, google_sub="other-sub")
    job = make_job(db, other)
    tailoring = make_tailoring(db, other, job)
    response = client.get(f"/tailorings/{tailoring.id}", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /tailorings/{id}
# ---------------------------------------------------------------------------


def test_delete_tailoring(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    response = client.delete(f"/tailorings/{tailoring.id}", headers=AUTH_HEADERS)
    assert response.status_code == 204
    # Confirm it's gone
    get_response = client.get(f"/tailorings/{tailoring.id}", headers=AUTH_HEADERS)
    assert get_response.status_code == 404


def test_delete_tailoring_other_user_returns_404(client, approved_user, db):
    other = make_user(db, google_sub="other-sub")
    job = make_job(db, other)
    tailoring = make_tailoring(db, other, job)
    response = client.delete(f"/tailorings/{tailoring.id}", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /tailorings/{id}/share  +  DELETE /tailorings/{id}/share
# ---------------------------------------------------------------------------


def test_share_tailoring_generates_slug(client, approved_user, db):
    job = make_job(db, approved_user, extracted_job={"title": "Eng", "company": "Co"})
    tailoring = make_tailoring(db, approved_user, job)
    response = client.post(
        f"/tailorings/{tailoring.id}/share",
        json={"letter": True, "posting": False},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["letter_public"] is True
    assert data["posting_public"] is False
    assert data["public_slug"] is not None


def test_share_tailoring_idempotent_slug(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    r1 = client.post(
        f"/tailorings/{tailoring.id}/share", json={"letter": True}, headers=AUTH_HEADERS
    )
    slug1 = r1.json()["public_slug"]
    r2 = client.post(
        f"/tailorings/{tailoring.id}/share", json={"letter": True}, headers=AUTH_HEADERS
    )
    slug2 = r2.json()["public_slug"]
    assert slug1 == slug2  # slug is not regenerated once set


def test_unshare_tailoring(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    client.post(f"/tailorings/{tailoring.id}/share", json={"letter": True}, headers=AUTH_HEADERS)
    response = client.delete(f"/tailorings/{tailoring.id}/share", headers=AUTH_HEADERS)
    assert response.status_code == 204
    # Verify flags are cleared
    detail = client.get(f"/tailorings/{tailoring.id}", headers=AUTH_HEADERS).json()
    assert detail["letter_public"] is False
    assert detail["is_public"] is False


# ---------------------------------------------------------------------------
# GET /tailorings/public/{username_slug}/{tailoring_slug}
# ---------------------------------------------------------------------------


def test_get_public_tailoring_not_shared_returns_404(client, approved_user, db):
    job = make_job(db, approved_user)
    make_tailoring(db, approved_user, job, public_slug="some-slug")
    # Not shared (letter_public and posting_public default to False)
    response = client.get(
        f"/tailorings/public/{approved_user.username_slug}/some-slug", headers=API_HEADERS
    )
    assert response.status_code == 404


def test_get_public_tailoring_after_share(client, approved_user, db):
    job = make_job(db, approved_user, extracted_job={"title": "Dev", "company": "Co"})
    tailoring = make_tailoring(db, approved_user, job)
    share_resp = client.post(
        f"/tailorings/{tailoring.id}/share", json={"letter": True}, headers=AUTH_HEADERS
    )
    slug = share_resp.json()["public_slug"]
    response = client.get(
        f"/tailorings/public/{approved_user.username_slug}/{slug}", headers=API_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Dev"
    assert data["company"] == "Co"
    assert data["letter_public"] is True


def test_get_public_tailoring_wrong_user_returns_404(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    client.post(f"/tailorings/{tailoring.id}/share", json={"letter": True}, headers=AUTH_HEADERS)
    slug = client.get(f"/tailorings/{tailoring.id}", headers=AUTH_HEADERS).json()["public_slug"]
    response = client.get(f"/tailorings/public/nonexistent-user/{slug}", headers=API_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------


def test_pending_user_gets_403(client, db):
    # No pre-created user → get_current_user creates one with status="pending"
    pending_headers = {
        "X-API-Key": "test-key",
        "X-User-Id": "pending-google-sub",
        "X-User-Email": "pending@example.com",
    }
    response = client.get("/tailorings", headers=pending_headers)
    assert response.status_code == 403


def test_missing_api_key_returns_422(client):
    # No headers at all → required X-API-Key and X-User-Id both missing → 422
    response = client.get("/tailorings")
    assert response.status_code == 422


def test_invalid_api_key_returns_401(client):
    response = client.get(
        "/tailorings",
        headers={"X-API-Key": "wrong-key", "X-User-Id": "test", "X-User-Email": "t@t.com"},
    )
    assert response.status_code == 401
