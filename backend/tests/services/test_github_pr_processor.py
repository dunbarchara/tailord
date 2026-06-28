"""
Unit tests for github_pr_processor.process_github_pr_signal.

Uses mocked DB, GitHub client, LLM, and embedding so no real I/O occurs.
"""

import uuid
from unittest.mock import MagicMock

import pytest


def _make_signal(user_id=None, pr_url="https://github.com/owner/repo/pull/1"):
    sig = MagicMock()
    sig.id = uuid.uuid4()
    sig.user_id = user_id or uuid.uuid4()
    sig.source_ref = pr_url
    sig.source_type = "github_pr"
    sig.status = "pending"
    sig.skip_reason = None
    sig.processed_at = None
    sig.raw_data = {
        "action": "closed",
        "installation": {"id": 123},
        "pull_request": {
            "number": 1,
            "title": "Add feature X",
            "body": "Implemented caching layer reducing latency by 40%.",
            "html_url": pr_url,
            "merged": True,
            "user": {"login": "testuser", "type": "User"},
            "base": {"ref": "main"},
            "labels": [],
        },
        "repository": {
            "name": "my-repo",
            "owner": {"login": "owner"},
        },
    }
    return sig


def _make_source(installation_id="123", username="testuser"):
    src = MagicMock()
    src.user_id = uuid.uuid4()
    src.config = {"installation_id": installation_id, "username": username}
    return src


def _make_commits(login="testuser"):
    return [
        {
            "author": {"login": login},
            "commit": {
                "message": "Add caching layer\n\nMore details here.",
                "author": {"name": login},
            },
        }
    ]


def _run_processor(signal_id, db):
    """Call _process directly with all dependencies mocked."""
    from sqlalchemy import func

    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        PRClaimExtractionResult,
    )
    from app.services.github_pr_processor import _process

    _process(
        signal_id=signal_id,
        db=db,
        embed_text=db._mock_embed_text,
        get_github_client=db._mock_get_github_client,
        get_llm_client=db._mock_get_llm_client,
        llm_parse_with_retry=db._mock_llm_parse_with_retry,
        settings=db._mock_settings,
        SYSTEM=SYSTEM,
        USER_TEMPLATE=USER_TEMPLATE,
        TEMPERATURE=TEMPERATURE,
        PROMPT_NAME=PROMPT_NAME,
        PRClaimExtractionResult=PRClaimExtractionResult,
        CaptureSignal=CaptureSignal,
        ExperienceClaim=ExperienceClaim,
        ExperienceSource=ExperienceSource,
        is_duplicate_claim=db._mock_is_duplicate_claim,
        _get_or_create_group=db._mock_get_or_create_group,
        func=func,
    )


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """A mock db session with all dependency callables attached as attributes."""
    from app.prompts.github_pr_extraction import ClaimDraft, PRClaimExtractionResult

    db = MagicMock()

    # Default: signal found, source found, commits returned, LLM extracts 1 claim
    signal = _make_signal()
    source = _make_source()
    source.user_id = signal.user_id

    db.query.return_value.filter.return_value.first.return_value = signal

    # LLM result with one claim
    claim_draft = ClaimDraft(
        content="Implemented caching layer reducing latency by 40%.",
        claim_type="work_experience",
        confidence="high",
        technologies=["Redis", "Python"],
    )
    llm_result = PRClaimExtractionResult(claims=[claim_draft], skip_reason=None)

    db._mock_embed_text = MagicMock(return_value=[0.1] * 1536)
    db._mock_get_github_client = MagicMock(
        return_value=MagicMock(get_pr_commits=MagicMock(return_value=_make_commits()))
    )
    db._mock_get_llm_client = MagicMock(return_value=MagicMock())
    db._mock_llm_parse_with_retry = MagicMock(return_value=llm_result)
    db._mock_settings = MagicMock(llm_model="gpt-4o-mini", embedding_model="text-embedding-3-small")
    db._mock_is_duplicate_claim = MagicMock(return_value=False)
    db._mock_get_or_create_group = MagicMock(return_value=MagicMock(id=uuid.uuid4()))

    # Queries: signal, source, max position
    def query_side_effect(model):
        from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource

        m = MagicMock()
        if model is CaptureSignal:
            m.filter.return_value.first.return_value = signal
        elif model is ExperienceSource:
            m.filter.return_value.first.return_value = source
        elif model is ExperienceClaim:
            # For func.max(position) query
            scalar_m = MagicMock()
            scalar_m.filter.return_value.scalar.return_value = 5
            return scalar_m
        return m

    db.query.side_effect = query_side_effect
    db._signal = signal
    db._source = source
    return db


# ── Tests ───────────────────────────────────────────────────────────────────


def test_signal_not_found_exits_cleanly():
    from sqlalchemy import func

    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        PRClaimExtractionResult,
    )
    from app.services.github_pr_processor import _process

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db._mock_embed_text = MagicMock()
    db._mock_get_github_client = MagicMock()
    db._mock_get_llm_client = MagicMock()
    db._mock_llm_parse_with_retry = MagicMock()
    db._mock_settings = MagicMock(llm_model="gpt-4o-mini", embedding_model="text-embedding-3-small")
    db._mock_is_duplicate_claim = MagicMock()
    db._mock_get_or_create_group = MagicMock()

    _process(
        signal_id=uuid.uuid4(),
        db=db,
        embed_text=db._mock_embed_text,
        get_github_client=db._mock_get_github_client,
        get_llm_client=db._mock_get_llm_client,
        llm_parse_with_retry=db._mock_llm_parse_with_retry,
        settings=db._mock_settings,
        SYSTEM=SYSTEM,
        USER_TEMPLATE=USER_TEMPLATE,
        TEMPERATURE=TEMPERATURE,
        PROMPT_NAME=PROMPT_NAME,
        PRClaimExtractionResult=PRClaimExtractionResult,
        CaptureSignal=CaptureSignal,
        ExperienceClaim=ExperienceClaim,
        ExperienceSource=ExperienceSource,
        is_duplicate_claim=db._mock_is_duplicate_claim,
        _get_or_create_group=db._mock_get_or_create_group,
        func=func,
    )

    # Should return without error; no commit, no crash
    db.commit.assert_not_called()


def test_no_experience_source_marks_signal_failed():
    from sqlalchemy import func

    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        PRClaimExtractionResult,
    )
    from app.services.github_pr_processor import _process

    signal = _make_signal()
    db = MagicMock()

    def query_side_effect(model):
        m = MagicMock()
        if model is CaptureSignal:
            m.filter.return_value.first.return_value = signal
        elif model is ExperienceSource:
            m.filter.return_value.first.return_value = None  # not found
        return m

    db.query.side_effect = query_side_effect
    db._mock_embed_text = MagicMock()
    db._mock_get_github_client = MagicMock()
    db._mock_get_llm_client = MagicMock()
    db._mock_llm_parse_with_retry = MagicMock()
    db._mock_settings = MagicMock(llm_model="gpt-4o-mini", embedding_model="text-embedding-3-small")
    db._mock_is_duplicate_claim = MagicMock()
    db._mock_get_or_create_group = MagicMock()

    _process(
        signal_id=signal.id,
        db=db,
        embed_text=db._mock_embed_text,
        get_github_client=db._mock_get_github_client,
        get_llm_client=db._mock_get_llm_client,
        llm_parse_with_retry=db._mock_llm_parse_with_retry,
        settings=db._mock_settings,
        SYSTEM=SYSTEM,
        USER_TEMPLATE=USER_TEMPLATE,
        TEMPERATURE=TEMPERATURE,
        PROMPT_NAME=PROMPT_NAME,
        PRClaimExtractionResult=PRClaimExtractionResult,
        CaptureSignal=CaptureSignal,
        ExperienceClaim=ExperienceClaim,
        ExperienceSource=ExperienceSource,
        is_duplicate_claim=db._mock_is_duplicate_claim,
        _get_or_create_group=db._mock_get_or_create_group,
        func=func,
    )

    assert signal.status == "failed"
    assert signal.skip_reason == "no_matched_source"
    db.commit.assert_called_once()


def test_github_api_error_marks_signal_failed():
    from sqlalchemy import func

    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        PRClaimExtractionResult,
    )
    from app.services.github_pr_processor import _process

    signal = _make_signal()
    source = _make_source()
    source.user_id = signal.user_id

    db = MagicMock()

    def query_side_effect(model):
        m = MagicMock()
        if model is CaptureSignal:
            m.filter.return_value.first.return_value = signal
        elif model is ExperienceSource:
            m.filter.return_value.first.return_value = source
        return m

    db.query.side_effect = query_side_effect

    github_client = MagicMock()
    github_client.get_pr_commits.side_effect = Exception("API rate limit exceeded")

    db._mock_embed_text = MagicMock()
    db._mock_get_github_client = MagicMock(return_value=github_client)
    db._mock_get_llm_client = MagicMock()
    db._mock_llm_parse_with_retry = MagicMock()
    db._mock_settings = MagicMock(llm_model="gpt-4o-mini", embedding_model="text-embedding-3-small")
    db._mock_is_duplicate_claim = MagicMock()
    db._mock_get_or_create_group = MagicMock()

    _process(
        signal_id=signal.id,
        db=db,
        embed_text=db._mock_embed_text,
        get_github_client=db._mock_get_github_client,
        get_llm_client=db._mock_get_llm_client,
        llm_parse_with_retry=db._mock_llm_parse_with_retry,
        settings=db._mock_settings,
        SYSTEM=SYSTEM,
        USER_TEMPLATE=USER_TEMPLATE,
        TEMPERATURE=TEMPERATURE,
        PROMPT_NAME=PROMPT_NAME,
        PRClaimExtractionResult=PRClaimExtractionResult,
        CaptureSignal=CaptureSignal,
        ExperienceClaim=ExperienceClaim,
        ExperienceSource=ExperienceSource,
        is_duplicate_claim=db._mock_is_duplicate_claim,
        _get_or_create_group=db._mock_get_or_create_group,
        func=func,
    )

    assert signal.status == "failed"
    assert signal.skip_reason == "commit_fetch_error"


def test_llm_skip_reason_marks_signal_skipped():
    from sqlalchemy import func

    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        PRClaimExtractionResult,
    )
    from app.services.github_pr_processor import _process

    signal = _make_signal()
    source = _make_source()
    source.user_id = signal.user_id

    db = MagicMock()

    def query_side_effect(model):
        m = MagicMock()
        if model is CaptureSignal:
            m.filter.return_value.first.return_value = signal
        elif model is ExperienceSource:
            m.filter.return_value.first.return_value = source
        return m

    db.query.side_effect = query_side_effect

    llm_result = PRClaimExtractionResult(claims=[], skip_reason="dependency bump")

    db._mock_embed_text = MagicMock()
    db._mock_get_github_client = MagicMock(
        return_value=MagicMock(get_pr_commits=MagicMock(return_value=_make_commits()))
    )
    db._mock_get_llm_client = MagicMock()
    db._mock_llm_parse_with_retry = MagicMock(return_value=llm_result)
    db._mock_settings = MagicMock(llm_model="gpt-4o-mini", embedding_model="text-embedding-3-small")
    db._mock_is_duplicate_claim = MagicMock()
    db._mock_get_or_create_group = MagicMock()

    _process(
        signal_id=signal.id,
        db=db,
        embed_text=db._mock_embed_text,
        get_github_client=db._mock_get_github_client,
        get_llm_client=db._mock_get_llm_client,
        llm_parse_with_retry=db._mock_llm_parse_with_retry,
        settings=db._mock_settings,
        SYSTEM=SYSTEM,
        USER_TEMPLATE=USER_TEMPLATE,
        TEMPERATURE=TEMPERATURE,
        PROMPT_NAME=PROMPT_NAME,
        PRClaimExtractionResult=PRClaimExtractionResult,
        CaptureSignal=CaptureSignal,
        ExperienceClaim=ExperienceClaim,
        ExperienceSource=ExperienceSource,
        is_duplicate_claim=db._mock_is_duplicate_claim,
        _get_or_create_group=db._mock_get_or_create_group,
        func=func,
    )

    assert signal.status == "skipped"
    assert signal.skip_reason == "dependency bump"
    assert signal.processed_at is not None


def test_happy_path_inserts_claims(mock_db):
    from sqlalchemy import func

    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        PRClaimExtractionResult,
    )
    from app.services.github_pr_processor import _process

    signal = mock_db._signal

    _process(
        signal_id=signal.id,
        db=mock_db,
        embed_text=mock_db._mock_embed_text,
        get_github_client=mock_db._mock_get_github_client,
        get_llm_client=mock_db._mock_get_llm_client,
        llm_parse_with_retry=mock_db._mock_llm_parse_with_retry,
        settings=mock_db._mock_settings,
        SYSTEM=SYSTEM,
        USER_TEMPLATE=USER_TEMPLATE,
        TEMPERATURE=TEMPERATURE,
        PROMPT_NAME=PROMPT_NAME,
        PRClaimExtractionResult=PRClaimExtractionResult,
        CaptureSignal=CaptureSignal,
        ExperienceClaim=ExperienceClaim,
        ExperienceSource=ExperienceSource,
        is_duplicate_claim=mock_db._mock_is_duplicate_claim,
        _get_or_create_group=mock_db._mock_get_or_create_group,
        func=func,
    )

    assert signal.status == "processed"
    assert signal.processed_at is not None
    # One claim was inserted (not duplicate)
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_semantic_dedup_skips_duplicate_claim(mock_db):
    from sqlalchemy import func

    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        ClaimDraft,
        PRClaimExtractionResult,
    )
    from app.services.github_pr_processor import _process

    # LLM returns 2 claims; first is a duplicate, second is not
    claim1 = ClaimDraft(
        content="Built caching layer.",
        claim_type="work_experience",
        confidence="high",
        technologies=["Redis"],
    )
    claim2 = ClaimDraft(
        content="Migrated auth to OAuth 2.0.",
        claim_type="work_experience",
        confidence="medium",
        technologies=["OAuth"],
    )
    mock_db._mock_llm_parse_with_retry.return_value = PRClaimExtractionResult(
        claims=[claim1, claim2], skip_reason=None
    )

    # First call to is_duplicate_claim → True (skip); second → False (insert)
    mock_db._mock_is_duplicate_claim.side_effect = [True, False]

    signal = mock_db._signal

    _process(
        signal_id=signal.id,
        db=mock_db,
        embed_text=mock_db._mock_embed_text,
        get_github_client=mock_db._mock_get_github_client,
        get_llm_client=mock_db._mock_get_llm_client,
        llm_parse_with_retry=mock_db._mock_llm_parse_with_retry,
        settings=mock_db._mock_settings,
        SYSTEM=SYSTEM,
        USER_TEMPLATE=USER_TEMPLATE,
        TEMPERATURE=TEMPERATURE,
        PROMPT_NAME=PROMPT_NAME,
        PRClaimExtractionResult=PRClaimExtractionResult,
        CaptureSignal=CaptureSignal,
        ExperienceClaim=ExperienceClaim,
        ExperienceSource=ExperienceSource,
        is_duplicate_claim=mock_db._mock_is_duplicate_claim,
        _get_or_create_group=mock_db._mock_get_or_create_group,
        func=func,
    )

    # Only one claim should be added (the non-duplicate)
    assert mock_db.add.call_count == 1
    assert signal.status == "processed"


def test_embed_text_failure_inserts_claim_without_embedding(mock_db):
    from sqlalchemy import func

    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        PRClaimExtractionResult,
    )
    from app.services.github_pr_processor import _process

    mock_db._mock_embed_text.side_effect = Exception("OpenAI API error")
    signal = mock_db._signal

    _process(
        signal_id=signal.id,
        db=mock_db,
        embed_text=mock_db._mock_embed_text,
        get_github_client=mock_db._mock_get_github_client,
        get_llm_client=mock_db._mock_get_llm_client,
        llm_parse_with_retry=mock_db._mock_llm_parse_with_retry,
        settings=mock_db._mock_settings,
        SYSTEM=SYSTEM,
        USER_TEMPLATE=USER_TEMPLATE,
        TEMPERATURE=TEMPERATURE,
        PROMPT_NAME=PROMPT_NAME,
        PRClaimExtractionResult=PRClaimExtractionResult,
        CaptureSignal=CaptureSignal,
        ExperienceClaim=ExperienceClaim,
        ExperienceSource=ExperienceSource,
        is_duplicate_claim=mock_db._mock_is_duplicate_claim,
        _get_or_create_group=mock_db._mock_get_or_create_group,
        func=func,
    )

    # Claim should still be inserted, signal should be processed
    mock_db.add.assert_called_once()
    assert signal.status == "processed"

    # Verify the claim was inserted with embedding=None
    added_claim = mock_db.add.call_args[0][0]
    assert added_claim.embedding is None
    assert added_claim.embedding_model is None


def test_commit_filtering_only_includes_user_commits(mock_db):
    """Only commits by the github user are included in the LLM prompt."""
    from sqlalchemy import func

    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        PRClaimExtractionResult,
    )
    from app.services.github_pr_processor import _process

    # Commits from mixed authors — only testuser should be included
    mixed_commits = [
        {
            "author": {"login": "testuser"},
            "commit": {"message": "feat: add caching", "author": {"name": "testuser"}},
        },
        {
            "author": {"login": "dependabot[bot]"},
            "commit": {"message": "chore: bump deps", "author": {"name": "dependabot"}},
        },
        {
            "author": {"login": "colleague"},
            "commit": {"message": "fix: typo in README", "author": {"name": "Alice"}},
        },
    ]
    mock_db._mock_get_github_client.return_value.get_pr_commits.return_value = mixed_commits

    signal = mock_db._signal

    _process(
        signal_id=signal.id,
        db=mock_db,
        embed_text=mock_db._mock_embed_text,
        get_github_client=mock_db._mock_get_github_client,
        get_llm_client=mock_db._mock_get_llm_client,
        llm_parse_with_retry=mock_db._mock_llm_parse_with_retry,
        settings=mock_db._mock_settings,
        SYSTEM=SYSTEM,
        USER_TEMPLATE=USER_TEMPLATE,
        TEMPERATURE=TEMPERATURE,
        PROMPT_NAME=PROMPT_NAME,
        PRClaimExtractionResult=PRClaimExtractionResult,
        CaptureSignal=CaptureSignal,
        ExperienceClaim=ExperienceClaim,
        ExperienceSource=ExperienceSource,
        is_duplicate_claim=mock_db._mock_is_duplicate_claim,
        _get_or_create_group=mock_db._mock_get_or_create_group,
        func=func,
    )

    # Check the USER_TEMPLATE was rendered with only the user's commits
    call_kwargs = mock_db._mock_llm_parse_with_retry.call_args
    messages = call_kwargs[0][2]  # positional arg: messages
    user_message = next(m["content"] for m in messages if m["role"] == "user")
    assert "feat: add caching" in user_message
    assert "chore: bump deps" not in user_message
    assert "fix: typo in README" not in user_message
