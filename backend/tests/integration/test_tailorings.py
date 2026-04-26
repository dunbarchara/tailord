"""Integration tests for tailoring CRUD, sharing, and public access."""

from tests.conftest import (
    API_HEADERS,
    AUTH_HEADERS,
    make_chunk,
    make_experience,
    make_job,
    make_llm_trigger_log,
    make_tailoring,
    make_user,
)

# ---------------------------------------------------------------------------
# GET /tailorings
# ---------------------------------------------------------------------------


def test_list_tailorings_empty(client, approved_user):
    response = client.get("/tailorings", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["tailorings"] == []
    assert data["rate_limit_warning"] is None


def test_list_tailorings_returns_own(client, approved_user, db):
    job = make_job(db, approved_user)
    make_tailoring(db, approved_user, job)
    response = client.get("/tailorings", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data["tailorings"]) == 1
    assert data["tailorings"][0]["company"] == "Acme"
    assert data["tailorings"][0]["title"] == "Engineer"


def test_list_tailorings_excludes_other_users(client, approved_user, db):
    other = make_user(db, google_sub="other-sub")
    job = make_job(db, other)
    make_tailoring(db, other, job)
    response = client.get("/tailorings", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["tailorings"] == []


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


# ---------------------------------------------------------------------------
# Rate limit warning on GET /tailorings
# ---------------------------------------------------------------------------


def test_list_tailorings_no_warning_below_threshold(client, approved_user, db):
    make_llm_trigger_log(db, approved_user, n=7)
    response = client.get("/tailorings", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["rate_limit_warning"] is None


def test_list_tailorings_warning_at_threshold(client, approved_user, db):
    make_llm_trigger_log(db, approved_user, n=8)
    response = client.get("/tailorings", headers=AUTH_HEADERS)
    assert response.status_code == 200
    warning = response.json()["rate_limit_warning"]
    assert warning is not None
    assert warning["triggers_used"] == 8
    assert warning["limit"] == 10


def test_list_tailorings_warning_at_limit(client, approved_user, db):
    make_llm_trigger_log(db, approved_user, n=9)
    response = client.get("/tailorings", headers=AUTH_HEADERS)
    assert response.status_code == 200
    warning = response.json()["rate_limit_warning"]
    assert warning is not None
    assert warning["triggers_used"] == 9


# ---------------------------------------------------------------------------
# GET /tailorings/{id}/chunks
# ---------------------------------------------------------------------------


def test_get_tailoring_chunks_empty(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    response = client.get(f"/tailorings/{tailoring.id}/chunks", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["chunks"] == []
    assert data["enrichment_status"] is not None


def test_get_tailoring_chunks_returns_seeded_chunks(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    make_chunk(db, job, position=0, content="Python experience")
    make_chunk(db, job, position=1, content="AWS knowledge")
    response = client.get(f"/tailorings/{tailoring.id}/chunks", headers=AUTH_HEADERS)
    assert response.status_code == 200
    chunks = response.json()["chunks"]
    assert len(chunks) == 2
    assert chunks[0]["content"] == "Python experience"
    assert chunks[1]["content"] == "AWS knowledge"


def test_get_tailoring_chunks_other_user_returns_404(client, approved_user, db):
    other = make_user(db, google_sub="other-sub")
    job = make_job(db, other)
    tailoring = make_tailoring(db, other, job)
    response = client.get(f"/tailorings/{tailoring.id}/chunks", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /tailorings/{id}/gap-answer
# ---------------------------------------------------------------------------

_GAP_ANALYSIS = {
    "gaps": [
        {
            "job_requirement": "CI/CD pipeline experience",
            "question_for_candidate": "Describe a CI/CD pipeline you built.",
            "context": "The role requires owning the pipeline.",
            "chunk_id": None,
        }
    ]
}


def test_submit_gap_answer_updates_experience(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job, gap_analysis=_GAP_ANALYSIS)
    make_experience(db, approved_user)
    response = client.post(
        f"/tailorings/{tailoring.id}/gap-answer",
        json={"gap_index": 0, "answer": "I built a GitHub Actions pipeline at my last job."},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"
    assert data["chunk_reenrichment_queued"] is False  # chunk_id is None


def test_submit_gap_answer_out_of_range(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job, gap_analysis=_GAP_ANALYSIS)
    make_experience(db, approved_user)
    response = client.post(
        f"/tailorings/{tailoring.id}/gap-answer",
        json={"gap_index": 5, "answer": "irrelevant"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


def test_submit_gap_answer_no_gap_analysis(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)  # no gap_analysis
    make_experience(db, approved_user)
    response = client.post(
        f"/tailorings/{tailoring.id}/gap-answer",
        json={"gap_index": 0, "answer": "some answer"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_submit_gap_answer_tailoring_not_found(client, approved_user, db):
    import uuid

    response = client.post(
        f"/tailorings/{uuid.uuid4()}/gap-answer",
        json={"gap_index": 0, "answer": "some answer"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /tailorings/{id}/debug-info
# ---------------------------------------------------------------------------


def test_get_debug_info_with_snapshot(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job, profile_snapshot="Snapshot text")
    response = client.get(f"/tailorings/{tailoring.id}/debug-info", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["formatted_profile"] == "Snapshot text"
    assert data["profile_snapshot_source"] == "snapshot"


def test_get_debug_info_reconstructed_without_snapshot(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)  # no profile_snapshot
    make_experience(db, approved_user)
    response = client.get(f"/tailorings/{tailoring.id}/debug-info", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["profile_snapshot_source"] == "reconstructed"
    assert "chunk_matching_system_prompt" in data


def test_get_debug_info_not_found(client, approved_user, db):
    import uuid

    response = client.get(f"/tailorings/{uuid.uuid4()}/debug-info", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_get_debug_info_other_user_returns_404(client, approved_user, db):
    other = make_user(db, google_sub="other-sub")
    job = make_job(db, other)
    tailoring = make_tailoring(db, other, job)
    response = client.get(f"/tailorings/{tailoring.id}/debug-info", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Share / unshare — wrong-user 404 paths
# ---------------------------------------------------------------------------


def test_share_tailoring_other_user_returns_404(client, approved_user, db):
    other = make_user(db, google_sub="other-sub")
    job = make_job(db, other)
    tailoring = make_tailoring(db, other, job)
    response = client.post(
        f"/tailorings/{tailoring.id}/share",
        json={"letter": True},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_unshare_tailoring_other_user_returns_404(client, approved_user, db):
    other = make_user(db, google_sub="other-sub")
    job = make_job(db, other)
    tailoring = make_tailoring(db, other, job)
    response = client.delete(f"/tailorings/{tailoring.id}/share", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /tailorings/public — posting_public with chunks
# ---------------------------------------------------------------------------


def test_get_public_tailoring_posting_includes_chunks(client, approved_user, db):
    job = make_job(db, approved_user, extracted_job={"title": "Dev", "company": "Co"})
    tailoring = make_tailoring(db, approved_user, job)
    make_chunk(db, job, position=0, match_score=2, should_render=True)
    share_resp = client.post(
        f"/tailorings/{tailoring.id}/share",
        json={"letter": True, "posting": True},
        headers=AUTH_HEADERS,
    )
    slug = share_resp.json()["public_slug"]
    response = client.get(
        f"/tailorings/public/{approved_user.username_slug}/{slug}", headers=API_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert data["posting_public"] is True
    assert "chunks" in data
    assert len(data["chunks"]) == 1
