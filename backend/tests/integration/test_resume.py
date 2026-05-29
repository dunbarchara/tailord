"""Integration tests for the resume export endpoints."""

from unittest.mock import AsyncMock, patch

from tests.conftest import AUTH_HEADERS, make_claim, make_group, make_job, make_tailoring

# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


def test_generate_resume_no_claims(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    res = client.post(
        f"/tailorings/{tailoring.id}/resume/generate",
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 422
    assert res.json()["detail"] == "no_active_claims"


def test_generate_resume_success(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    group = make_group(db, approved_user, group_type="role", name="Acme")
    make_claim(db, approved_user, group=group, content="Led API redesign reducing latency by 30%.")
    make_claim(db, approved_user, group=group, content="Shipped auth service used by 50k users.")

    with patch("app.services.resume_selector._retrieve_top_k_experience_chunks", return_value=[]):
        res = client.post(
            f"/tailorings/{tailoring.id}/resume/generate",
            headers=AUTH_HEADERS,
        )

    assert res.status_code == 200
    body = res.json()
    assert "sections" in body
    assert "generated_at" in body

    # Confirm resume_draft persisted in DB
    from app.models.database import Tailoring
    from tests.integration.conftest import _TestSession

    with _TestSession() as s:
        t = s.get(Tailoring, tailoring.id)
        assert t.resume_draft is not None


def test_generate_resume_no_resume_source_warns(client, approved_user, db):
    """Should succeed with no_resume_source warning when claims exist but no resume source."""
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    make_claim(db, approved_user, content="Designed distributed caching layer.")

    with patch("app.services.resume_selector._retrieve_top_k_experience_chunks", return_value=[]):
        res = client.post(
            f"/tailorings/{tailoring.id}/resume/generate",
            headers=AUTH_HEADERS,
        )

    assert res.status_code == 200
    assert "no_resume_source" in res.json()["warnings"]


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_resume_not_generated(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    res = client.get(f"/tailorings/{tailoring.id}/resume", headers=AUTH_HEADERS)
    assert res.status_code == 404
    assert res.json()["detail"] == "not_generated"


def test_get_resume_after_generate(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    make_claim(db, approved_user, content="Built CI/CD pipeline cutting deploy time in half.")

    with patch("app.services.resume_selector._retrieve_top_k_experience_chunks", return_value=[]):
        client.post(f"/tailorings/{tailoring.id}/resume/generate", headers=AUTH_HEADERS)

    res = client.get(f"/tailorings/{tailoring.id}/resume", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert "sections" in res.json()


# ---------------------------------------------------------------------------
# patch
# ---------------------------------------------------------------------------


def test_patch_resume_exclude_section(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    group = make_group(db, approved_user, group_type="role", name="Corp")
    make_claim(db, approved_user, group=group, content="Architected real-time analytics pipeline.")

    with patch("app.services.resume_selector._retrieve_top_k_experience_chunks", return_value=[]):
        gen_res = client.post(f"/tailorings/{tailoring.id}/resume/generate", headers=AUTH_HEADERS)
    assert gen_res.status_code == 200
    draft = gen_res.json()

    # Patch first section to included=False
    if draft["sections"]:
        patch_body = {"sections": [{**draft["sections"][0], "included": False}]}
        patch_res = client.patch(
            f"/tailorings/{tailoring.id}/resume",
            json=patch_body,
            headers=AUTH_HEADERS,
        )
        assert patch_res.status_code == 200
        updated = patch_res.json()
        gid = draft["sections"][0]["group_id"]
        matching = [s for s in updated["sections"] if s["group_id"] == gid]
        assert matching[0]["included"] is False


def test_patch_resume_contact_override(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    make_claim(db, approved_user, content="Reduced infrastructure cost by 20%.")

    with patch("app.services.resume_selector._retrieve_top_k_experience_chunks", return_value=[]):
        client.post(f"/tailorings/{tailoring.id}/resume/generate", headers=AUTH_HEADERS)

    patch_res = client.patch(
        f"/tailorings/{tailoring.id}/resume",
        json={
            "contact_override": {"linkedin_url": "https://linkedin.com/in/test", "location": "NYC"}
        },
        headers=AUTH_HEADERS,
    )
    assert patch_res.status_code == 200
    body = patch_res.json()
    assert body["contact_override"]["linkedin_url"] == "https://linkedin.com/in/test"
    assert body["contact_override"]["location"] == "NYC"


def test_patch_resume_before_generate_returns_404(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    res = client.patch(
        f"/tailorings/{tailoring.id}/resume",
        json={"contact_override": {"location": "SF"}},
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# pdf
# ---------------------------------------------------------------------------


def test_export_pdf(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    make_claim(db, approved_user, content="Shipped payments integration used by 10k users.")

    with patch("app.services.resume_selector._retrieve_top_k_experience_chunks", return_value=[]):
        client.post(f"/tailorings/{tailoring.id}/resume/generate", headers=AUTH_HEADERS)

    with patch(
        "app.api.resume.render_resume_pdf",
        new=AsyncMock(return_value=b"%PDF-1.4 fake pdf bytes"),
    ):
        res = client.post(f"/tailorings/{tailoring.id}/resume/pdf", headers=AUTH_HEADERS)

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert len(res.content) > 0


def test_export_pdf_not_generated_returns_404(client, approved_user, db):
    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    res = client.post(f"/tailorings/{tailoring.id}/resume/pdf", headers=AUTH_HEADERS)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# snapshot fallback
# ---------------------------------------------------------------------------


def test_resume_renders_from_snapshot_after_claims_deleted(client, approved_user, db):
    """Existing resume_draft snapshots should still render after all claims are deleted/rechunked."""
    from app.models.database import ExperienceClaim

    job = make_job(db, approved_user)
    tailoring = make_tailoring(db, approved_user, job)
    group = make_group(db, approved_user, group_type="role", name="Snapshot Corp")
    make_claim(
        db,
        approved_user,
        group=group,
        content="Reduced p99 latency by 40% via query optimisation.",
    )

    with patch("app.services.resume_selector._retrieve_top_k_experience_chunks", return_value=[]):
        gen_res = client.post(
            f"/tailorings/{tailoring.id}/resume/generate",
            headers=AUTH_HEADERS,
        )
    assert gen_res.status_code == 200
    draft = gen_res.json()

    # Snapshots must be populated at generation time
    for section in draft["sections"]:
        for cid in section["claim_ids"]:
            assert cid in section["bullet_snapshots"], f"snapshot missing for claim {cid}"

    # Simulate rechunk: delete all claims for this user
    db.query(ExperienceClaim).filter(ExperienceClaim.user_id == approved_user.id).delete()
    db.commit()

    # Render HTML — should fall back to snapshots, not blank
    with patch(
        "app.api.resume.render_resume_pdf",
        new=AsyncMock(return_value=b"%PDF-1.4 fake"),
    ):
        html_res = client.get(
            f"/tailorings/{tailoring.id}/resume/html",
            headers=AUTH_HEADERS,
        )

    assert html_res.status_code == 200
    html = html_res.text
    assert "Reduced p99 latency" in html, "snapshot content missing from rendered HTML"
    assert "Snapshot Corp" in html, "group name missing from rendered HTML"
