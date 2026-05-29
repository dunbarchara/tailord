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


def _make_resume_source(extracted: dict | None = None) -> SimpleNamespace:
    """Minimal ExperienceSource(resume) stub for chunker tests."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_type="resume",
        source_data={"extracted": extracted} if extracted is not None else None,
    )


def _make_github_source(
    repos: list | None = None, repo_details: dict | None = None
) -> SimpleNamespace:
    """Minimal ExperienceSource(github) stub for chunker tests."""
    source_data: dict = {}
    if repos is not None:
        source_data["repos"] = repos
    if repo_details is not None:
        source_data["repo_details"] = repo_details
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_type="github",
        source_data=source_data if source_data else None,
    )


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
    # summary is intentionally skipped — it's always included in the formatted-profile
    # baseline context sent to the LLM, so embedding it would crowd cosine top-K results.
    profile = {"summary": "Experienced engineer.", "work_experience": [], "skills": {}}
    chunks = _resume_chunks(profile)
    assert not any(c["content"] == "Experienced engineer." for c in chunks)


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
    assert proj[0]["keywords"] == ["React", "FastAPI"]
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
    # readme_summary is intentionally skipped — always present in the formatted-profile
    # baseline context, so embedding it would crowd cosine top-K results.
    # Only detected_stack items produce skill chunks.
    repo = {
        "name": "myrepo",
        "readme_summary": "A deployment tool for Kubernetes.",
        "detected_stack": ["Python", "Docker", "Kubernetes"],
    }
    chunks = _github_repo_chunks(repo)
    project_chunks = [c for c in chunks if c["claim_type"] == "project"]
    skill_chunks = [c for c in chunks if c["claim_type"] == "skill"]

    assert len(project_chunks) == 0
    assert len(skill_chunks) == 3
    assert {c["content"] for c in skill_chunks} == {"Python", "Docker", "Kubernetes"}
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
        "summary": "Great engineer.",  # skipped — not embedded
        "work_experience": [{"bullets": ["Did stuff"], "duration": "2021-2022"}],
        "skills": {"technical": ["Python"], "soft": []},
    }
    exp = _make_resume_source(extracted=profile)
    db = _make_db()

    count = chunk_resume(db, exp)

    assert count == 2  # 1 bullet + 1 skill (summary is skipped)
    assert db.add.call_count == 2
    added = db._added
    assert any(a.claim_type == "work_experience" for a in added)
    assert any(a.claim_type == "skill" for a in added)


def test_chunk_resume_sets_correct_source_fields():
    profile = {"skills": {"technical": ["Python"]}}  # summary alone produces no chunks
    exp = _make_resume_source(extracted=profile)
    db = _make_db()

    chunk_resume(db, exp)

    chunk = db._added[0]
    assert chunk.source_type == "resume"
    assert chunk.source_ref is None
    assert chunk.user_id == exp.user_id


def test_chunk_resume_positions_are_sequential():
    profile = {
        "summary": "s",
        "work_experience": [{"bullets": ["b1", "b2"], "duration": ""}],
    }
    exp = _make_resume_source(extracted=profile)
    db = _make_db()

    chunk_resume(db, exp)

    positions = [a.position for a in db._added]
    assert positions == list(range(len(positions)))


def test_chunk_resume_noop_when_no_resume_profile():
    exp = _make_resume_source(extracted=None)
    db = _make_db()

    count = chunk_resume(db, exp)

    assert count == 0
    db.add.assert_not_called()


def test_chunk_resume_noop_when_extracted_profile_none():
    exp = _make_resume_source(extracted=None)
    db = _make_db()

    count = chunk_resume(db, exp)

    assert count == 0
    db.add.assert_not_called()


# ---------------------------------------------------------------------------
# chunk_github_repo — DB interaction
# ---------------------------------------------------------------------------


def test_chunk_github_repo_inserts_chunks():
    repos = [
        {
            "name": "tailord",
            "readme_summary": "AI tailoring tool.",  # skipped — not embedded
            "detected_stack": ["Python", "FastAPI"],
        }
    ]
    exp = _make_github_source(repos=repos)
    db = _make_db()

    count = chunk_github_repo(db, exp, "tailord")

    assert count == 2  # 2 skills from detected_stack (readme_summary is skipped)
    for chunk in db._added:
        assert chunk.source_type == "github"
        assert chunk.source_ref == "tailord"
        assert chunk.user_id == exp.user_id


def test_chunk_github_repo_noop_when_repo_not_found():
    exp = _make_github_source(repos=[{"name": "other-repo"}])
    db = _make_db()

    count = chunk_github_repo(db, exp, "nonexistent")

    assert count == 0
    db.add.assert_not_called()


def test_chunk_github_repo_positions_are_sequential():
    repos = [
        {
            "name": "repo",
            "readme_summary": "Summary.",
            "detected_stack": ["Go", "Docker"],
        }
    ]
    exp = _make_github_source(repos=repos)
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


# ---------------------------------------------------------------------------
# chunk_resume — ExperienceGroup creation + group_id assignment
# ---------------------------------------------------------------------------


def _make_mock_group(group_type: str, source_type: str, name: str = "test") -> SimpleNamespace:
    """Return a SimpleNamespace that passes the group_type string comparisons in chunk_resume."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        group_type=group_type,
        source_type=source_type,
        name=name,
        parent_group_id=None,
        type_meta=None,
    )


def test_chunk_resume_sets_group_id_on_work_experience_claims():
    """chunk_resume assigns the group's id to group_id on each created claim."""
    profile = {
        "work_experience": [
            {
                "title": "SWE",
                "company": "ACME",
                "duration": "2020–2023",
                "bullets": ["Built REST APIs"],
            }
        ]
    }
    exp = _make_resume_source(extracted=profile)
    db = _make_db()
    mock_group = _make_mock_group("role", "resume", "ACME | SWE")
    db.query.return_value.filter.return_value.first.return_value = mock_group
    db.query.return_value.filter.return_value.all.return_value = []

    chunk_resume(db, exp)

    # Only the ExperienceClaim is added (group was "found" by mock)
    assert len(db._added) == 1
    assert db._added[0].group_id == mock_group.id


def test_chunk_resume_creates_group_when_not_found():
    """When no existing group is found, chunk_resume creates a new ExperienceGroup via db.add."""
    from app.models.database import ExperienceClaim, ExperienceGroup

    profile = {
        "work_experience": [
            {"title": "Dev", "company": "Corp", "duration": "", "bullets": ["Did work"]}
        ]
    }
    exp = _make_resume_source(extracted=profile)
    db = _make_db()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []

    chunk_resume(db, exp)

    added_groups = [a for a in db._added if isinstance(a, ExperienceGroup)]
    added_claims = [a for a in db._added if isinstance(a, ExperienceClaim)]
    assert len(added_groups) == 1
    assert added_groups[0].group_type == "role"
    assert added_groups[0].source_type == "resume"
    assert len(added_claims) == 1


# ---------------------------------------------------------------------------
# chunk_github_repo — ExperienceGroup creation + group_id assignment
# ---------------------------------------------------------------------------


def test_chunk_github_repo_sets_group_id_on_claims():
    """chunk_github_repo assigns the repo group's id to group_id on each created claim."""
    repos = [{"name": "myrepo", "detected_stack": ["Python", "FastAPI"]}]
    exp = _make_github_source(repos=repos)
    db = _make_db()
    mock_group = _make_mock_group("repository", "github", "myrepo")
    db.query.return_value.filter.return_value.first.return_value = mock_group
    db.query.return_value.filter.return_value.all.return_value = []

    count = chunk_github_repo(db, exp, "myrepo")

    assert count == 2  # 2 skills from detected_stack
    assert all(c.group_id == mock_group.id for c in db._added)


def test_chunk_github_repo_creates_repository_group():
    """When no existing group is found, chunk_github_repo creates a 'repository' ExperienceGroup."""
    from app.models.database import ExperienceGroup

    repos = [{"name": "myrepo", "detected_stack": ["Go"]}]
    exp = _make_github_source(repos=repos)
    db = _make_db()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []

    chunk_github_repo(db, exp, "myrepo")

    added_groups = [a for a in db._added if isinstance(a, ExperienceGroup)]
    assert len(added_groups) == 1
    assert added_groups[0].group_type == "repository"
    assert added_groups[0].source_type == "github"
    assert added_groups[0].name == "myrepo"
    assert added_groups[0].source_ref == "myrepo"
