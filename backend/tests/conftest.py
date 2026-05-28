"""
Top-level conftest: settings injection and factory helpers only.

Database fixtures live in tests/integration/conftest.py so that unit
tests never touch a database connection.
"""

import os

# Resolve test DB URL before app modules are imported
_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://app:app@localhost:5432/app_test",
)
os.environ.setdefault("DATABASE_URL", _TEST_DB_URL)

from app.config import settings  # noqa: E402

# Inject test secrets into the settings singleton
settings.api_key = "test-key"
settings.notion_client_id = "test-notion-client-id"
settings.notion_client_secret = "test-notion-client-secret"

# ---------------------------------------------------------------------------
# Auth header constants (used by both unit and integration tests)
# ---------------------------------------------------------------------------

TEST_GOOGLE_SUB = "test-google-sub"
ADMIN_GOOGLE_SUB = "admin-google-sub"

AUTH_HEADERS = {
    "X-API-Key": "test-key",
    "X-User-Id": TEST_GOOGLE_SUB,
    "X-User-Email": "test@example.com",
    "X-User-Name": "Test User",
}

ADMIN_AUTH_HEADERS = {
    "X-API-Key": "test-key",
    "X-User-Id": ADMIN_GOOGLE_SUB,
    "X-User-Email": "admin@example.com",
    "X-User-Name": "Admin User",
}

API_HEADERS = {"X-API-Key": "test-key"}  # for public endpoints (no user required)


# ---------------------------------------------------------------------------
# Factory helpers (plain functions — call with a db session from a fixture)
# ---------------------------------------------------------------------------


def make_user(db, google_sub=TEST_GOOGLE_SUB, status="approved", username_slug=None, **kwargs):
    from app.models.database import AuthIdentity, User, UserProfile

    user = User(
        email=f"{google_sub}@example.com",
        status=status,
        **kwargs,
    )
    db.add(user)
    db.flush()  # get id before creating dependents

    profile = UserProfile(
        user_id=user.id,
        username_slug=username_slug or google_sub[:20],
    )
    db.add(profile)

    identity = AuthIdentity(
        user_id=user.id,
        provider="google",
        subject=google_sub,
        email=f"{google_sub}@example.com",
    )
    db.add(identity)

    db.commit()
    db.refresh(user)
    return user


def make_job(db, user, extracted_job=None, job_url=None):
    from app.models.database import Job

    job = Job(
        user_id=user.id,
        job_url=job_url or "https://example.com/job",
        extracted_job=extracted_job or {"title": "Engineer", "company": "Acme"},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def make_tailoring(db, user, job, **kwargs):
    from app.models.database import Tailoring

    defaults = {
        "generated_output": "# Letter\n\nContent here.",
        "generation_status": "ready",
    }
    defaults.update(kwargs)
    tailoring = Tailoring(user_id=user.id, job_id=job.id, **defaults)
    db.add(tailoring)
    db.commit()
    db.refresh(tailoring)
    return tailoring


def make_chunk(db, job, position=0, **kwargs):
    from app.models.database import JobChunk

    defaults = {
        "chunk_type": "requirement",
        "content": "Experience with Python",
        "position": position,
        "section": "Requirements",
        "should_render": True,
    }
    defaults.update(kwargs)
    chunk = JobChunk(job_id=job.id, **defaults)
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def make_experience_source(db, user, source_type="resume", **kwargs):
    from datetime import datetime, timezone

    from app.models.database import ExperienceSource

    now = datetime.now(timezone.utc)
    defaults: dict = {
        "connection_status": "connected",
        "sync_status": "idle",
        "created_at": now,
        "updated_at": now,
    }
    if source_type == "resume" and "source_data" not in kwargs:
        defaults["source_data"] = {"extracted": {"work_experience": [{"title": "Engineer"}]}}
    defaults.update(kwargs)
    src = ExperienceSource(user_id=user.id, source_type=source_type, **defaults)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


# Backward-compat alias used by existing tests
def make_experience(db, user, **kwargs):
    return make_experience_source(db, user, source_type="resume", **kwargs)


def make_llm_trigger_log(db, user, n=1, event_type="tailoring_create"):
    from app.models.database import LlmTriggerLog

    logs = []
    for _ in range(n):
        log = LlmTriggerLog(user_id=user.id, event_type=event_type)
        db.add(log)
        logs.append(log)
    db.commit()
    return logs
