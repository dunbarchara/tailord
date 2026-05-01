"""Unit tests for experience_chunker.

All DB interactions are mocked — no real session or models are instantiated.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.experience_chunker import (
    _github_repo_chunks,
    _resume_chunks,
    chunk_github_repo,
    chunk_resume,
    delete_github_chunks,
    delete_resume_chunks,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_experience(extracted_profile: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), extracted_profile=extracted_profile)


def _make_db() -> MagicMock:
    db = MagicMock()
    added: list = []
    db.add.side_effect = lambda obj: added.append(obj)
    db._added = added
    return db


# ---------------------------------------------------------------------------
# _resume_chunks — pure function tests
# ---------------------------------------------------------------------------


def test_resume_chunks_summary():
    profile = {"summary": "Experienced engineer.", "work_experience": [], "skills": {}}
    chunks = _resume_chunks(profile)
    assert any(
        c["claim_type"] == "other" and c["content"] == "Experienced engineer." for c in chunks
    )


def test_resume_chunks_work_experience_bullets():
    profile = {
        "work_experience": [
            {
                "title": "SWE",
                "company": "ACME",
                "duration": "2020-2023",
                "bullets": ["Built a thing", "Fixed another thing"],
            }
        ]
    }
    chunks = _resume_chunks(profile)
    we = [c for c in chunks if c["claim_type"] == "work_experience"]
    assert len(we) == 2
    assert we[0]["date_range"] == "2020-2023"
    assert we[0]["content"] == "Built a thing"
    assert we[0]["group_key"] == "ACME | SWE"
    assert we[1]["group_key"] == "ACME | SWE"


def test_resume_chunks_skills():
    profile = {"skills": {"technical": ["Python", "SQL"], "soft": ["Communication"]}}
    chunks = _resume_chunks(profile)
    skill_contents = {c["content"] for c in chunks if c["claim_type"] == "skill"}
    assert skill_contents == {"Python", "SQL", "Communication"}


def test_resume_chunks_projects_with_technologies():
    profile = {
        "projects": [
            {"name": "MyApp", "description": "A web app", "technologies": ["React", "FastAPI"]}
        ]
    }
    chunks = _resume_chunks(profile)
    proj = [c for c in chunks if c["claim_type"] == "project"]
    assert len(proj) == 1
    assert proj[0]["content"] == "A web app"
    assert proj[0]["technologies"] == ["React", "FastAPI"]
    assert proj[0]["group_key"] == "MyApp"


def test_resume_chunks_education():
    profile = {
        "education": [{"degree": "BSc Computer Science", "institution": "MIT", "year": "2019"}]
    }
    chunks = _resume_chunks(profile)
    edu = [c for c in chunks if c["claim_type"] == "education"]
    assert len(edu) == 1
    assert "MIT" in edu[0]["content"]
    assert edu[0]["date_range"] == "2019"
    assert edu[0]["group_key"] == "BSc Computer Science | MIT"


def test_resume_chunks_certifications():
    profile = {"certifications": ["AWS Solutions Architect"]}
    chunks = _resume_chunks(profile)
    certs = [c for c in chunks if c["claim_type"] == "other" and "AWS" in c["content"]]
    assert len(certs) == 1


def test_resume_chunks_skips_empty_strings():
    profile = {
        "summary": "  ",
        "work_experience": [{"bullets": ["", "  "], "duration": "2020"}],
        "skills": {"technical": ["", "Python"]},
    }
    chunks = _resume_chunks(profile)
    assert all(c["content"].strip() for c in chunks)


# ---------------------------------------------------------------------------
# _github_repo_chunks — pure function tests
# ---------------------------------------------------------------------------


def test_github_repo_chunks_readme_and_stack():
    repo = {
        "name": "myrepo",
        "readme_summary": "A deployment tool for Kubernetes.",
        "detected_stack": ["Python", "Docker", "Kubernetes"],
    }
    chunks = _github_repo_chunks(repo)
    project_chunks = [c for c in chunks if c["claim_type"] == "project"]
    skill_chunks = [c for c in chunks if c["claim_type"] == "skill"]

    assert len(project_chunks) == 1
    assert project_chunks[0]["content"] == "A deployment tool for Kubernetes."
    assert len(skill_chunks) == 3
    assert {c["content"] for c in skill_chunks} == {"Python", "Docker", "Kubernetes"}
    # All chunks for a repo share the same group_key for rendering
    assert all(c["group_key"] == "myrepo" for c in chunks)


def test_github_repo_chunks_empty_repo():
    chunks = _github_repo_chunks({"name": "empty"})
    assert chunks == []


def test_github_repo_chunks_skips_empty_stack_items():
    repo = {"readme_summary": "Summary.", "detected_stack": ["", "  ", "Go"]}
    chunks = _github_repo_chunks(repo)
    skill_chunks = [c for c in chunks if c["claim_type"] == "skill"]
    assert len(skill_chunks) == 1
    assert skill_chunks[0]["content"] == "Go"


# ---------------------------------------------------------------------------
# chunk_resume — DB interaction
# ---------------------------------------------------------------------------


def test_chunk_resume_inserts_chunks():
    profile = {
        "summary": "Great engineer.",
        "work_experience": [{"bullets": ["Did stuff"], "duration": "2021-2022"}],
        "skills": {"technical": ["Python"], "soft": []},
    }
    exp = _make_experience(extracted_profile={"resume": profile})
    db = _make_db()

    count = chunk_resume(db, exp)

    assert count == 3  # summary + 1 bullet + 1 skill
    assert db.add.call_count == 3
    added = db._added
    assert any(a.claim_type == "other" for a in added)
    assert any(a.claim_type == "work_experience" for a in added)
    assert any(a.claim_type == "skill" for a in added)


def test_chunk_resume_sets_correct_source_fields():
    profile = {"summary": "Hello world."}
    exp = _make_experience(extracted_profile={"resume": profile})
    db = _make_db()

    chunk_resume(db, exp)

    chunk = db._added[0]
    assert chunk.source_type == "resume"
    assert chunk.source_ref is None
    assert chunk.experience_id == exp.id


def test_chunk_resume_positions_are_sequential():
    profile = {
        "summary": "s",
        "work_experience": [{"bullets": ["b1", "b2"], "duration": ""}],
    }
    exp = _make_experience(extracted_profile={"resume": profile})
    db = _make_db()

    chunk_resume(db, exp)

    positions = [a.position for a in db._added]
    assert positions == list(range(len(positions)))


def test_chunk_resume_noop_when_no_resume_profile():
    exp = _make_experience(extracted_profile={"github": {}})
    db = _make_db()

    count = chunk_resume(db, exp)

    assert count == 0
    db.add.assert_not_called()


def test_chunk_resume_noop_when_extracted_profile_none():
    exp = _make_experience(extracted_profile=None)
    db = _make_db()

    count = chunk_resume(db, exp)

    assert count == 0
    db.add.assert_not_called()


# ---------------------------------------------------------------------------
# chunk_github_repo — DB interaction
# ---------------------------------------------------------------------------


def test_chunk_github_repo_inserts_chunks():
    profile = {
        "github": {
            "repos": [
                {
                    "name": "tailord",
                    "readme_summary": "AI tailoring tool.",
                    "detected_stack": ["Python", "FastAPI"],
                }
            ]
        }
    }
    exp = _make_experience(extracted_profile=profile)
    db = _make_db()

    count = chunk_github_repo(db, exp, "tailord")

    assert count == 3  # 1 project + 2 skills
    for chunk in db._added:
        assert chunk.source_type == "github"
        assert chunk.source_ref == "tailord"
        assert chunk.experience_id == exp.id


def test_chunk_github_repo_noop_when_repo_not_found():
    profile = {"github": {"repos": [{"name": "other-repo"}]}}
    exp = _make_experience(extracted_profile=profile)
    db = _make_db()

    count = chunk_github_repo(db, exp, "nonexistent")

    assert count == 0
    db.add.assert_not_called()


def test_chunk_github_repo_positions_are_sequential():
    profile = {
        "github": {
            "repos": [
                {
                    "name": "repo",
                    "readme_summary": "Summary.",
                    "detected_stack": ["Go", "Docker"],
                }
            ]
        }
    }
    exp = _make_experience(extracted_profile=profile)
    db = _make_db()

    chunk_github_repo(db, exp, "repo")

    positions = [a.position for a in db._added]
    assert positions == list(range(len(positions)))


# ---------------------------------------------------------------------------
# delete helpers
# ---------------------------------------------------------------------------


def test_delete_resume_chunks_filters_correctly():
    exp_id = uuid.uuid4()
    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.delete.return_value = 3
    db.query.return_value.filter.return_value.delete.return_value = 3

    delete_resume_chunks(db, exp_id)

    db.query.assert_called_once()


def test_delete_github_chunks_all_repos():
    exp_id = uuid.uuid4()
    db = MagicMock()
    db.query.return_value.filter.return_value.delete.return_value = 5

    delete_github_chunks(db, exp_id, repo_name=None)

    db.query.assert_called_once()


def test_delete_github_chunks_single_repo():
    exp_id = uuid.uuid4()
    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.delete.return_value = 2

    delete_github_chunks(db, exp_id, repo_name="tailord")

    db.query.assert_called_once()
