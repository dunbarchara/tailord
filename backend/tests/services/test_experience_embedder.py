"""Unit tests for experience_embedder.

DB interactions are mocked via MagicMock. embed_text is patched throughout.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    content: str = "Developed TypeScript microservices",
    embedding=None,
    embedding_model: str | None = None,
) -> SimpleNamespace:
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        embedding=embedding,
        embedding_model=embedding_model,
    )
    return chunk


def _make_db(chunks: list) -> MagicMock:
    """Return a mock DB whose query().filter().all() yields `chunks`."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = chunks
    return db


# ---------------------------------------------------------------------------
# embed_experience_chunks
# ---------------------------------------------------------------------------


def test_embeds_chunks_with_null_embedding():
    chunk = _make_chunk(embedding=None)
    db = _make_db([chunk])
    experience_id = uuid.uuid4()

    with patch(
        "app.services.experience_embedder.embed_text", return_value=[0.1, 0.2]
    ) as mock_embed:
        with patch("app.services.experience_embedder.settings.embedding_model", "test-model"):
            from app.services.experience_embedder import embed_experience_chunks

            embed_experience_chunks(experience_id, db)

    mock_embed.assert_called_once_with(chunk.content)
    assert chunk.embedding == [0.1, 0.2]
    assert chunk.embedding_model == "test-model"
    db.commit.assert_called_once()


def test_skips_chunks_with_no_stale_entries():
    """If query returns empty list, no embed calls and no commit."""
    db = _make_db([])
    experience_id = uuid.uuid4()

    with patch("app.services.experience_embedder.embed_text") as mock_embed:
        from app.services.experience_embedder import embed_experience_chunks

        embed_experience_chunks(experience_id, db)

    mock_embed.assert_not_called()
    db.commit.assert_not_called()


def test_continues_after_per_chunk_failure():
    """A failed embed on one chunk must not prevent others from being embedded."""
    chunk_a = _make_chunk(content="chunk A")
    chunk_b = _make_chunk(content="chunk B")
    db = _make_db([chunk_a, chunk_b])
    experience_id = uuid.uuid4()

    def _fail_on_a(text: str) -> list[float]:
        if text == "chunk A":
            raise RuntimeError("API error")
        return [0.9]

    with patch("app.services.experience_embedder.embed_text", side_effect=_fail_on_a):
        with patch("app.services.experience_embedder.settings.embedding_model", "test-model"):
            from app.services.experience_embedder import embed_experience_chunks

            embed_experience_chunks(experience_id, db)

    assert chunk_a.embedding is None
    assert chunk_b.embedding == [0.9]
    db.commit.assert_called_once()


def test_no_commit_when_all_chunks_fail():
    chunk = _make_chunk()
    db = _make_db([chunk])
    experience_id = uuid.uuid4()

    with patch("app.services.experience_embedder.embed_text", side_effect=RuntimeError("fail")):
        from app.services.experience_embedder import embed_experience_chunks

        embed_experience_chunks(experience_id, db)

    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# re_embed_chunk
# ---------------------------------------------------------------------------


def test_re_embed_chunk_updates_embedding():
    chunk_id = uuid.uuid4()
    chunk = _make_chunk(content="Led migration to TypeScript")
    mock_db = MagicMock()
    mock_db.get.return_value = chunk

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.experience_embedder.embed_text", return_value=[0.3, 0.4]):
            with patch("app.services.experience_embedder.settings.embedding_model", "test-model"):
                from app.services.experience_embedder import re_embed_chunk

                re_embed_chunk(chunk_id)

    assert chunk.embedding == [0.3, 0.4]
    assert chunk.embedding_model == "test-model"
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_re_embed_chunk_not_found_no_crash():
    chunk_id = uuid.uuid4()
    mock_db = MagicMock()
    mock_db.get.return_value = None

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        from app.services.experience_embedder import re_embed_chunk

        re_embed_chunk(chunk_id)  # must not raise

    mock_db.commit.assert_not_called()
    mock_db.close.assert_called_once()


def test_re_embed_chunk_closes_session_on_embed_failure():
    chunk_id = uuid.uuid4()
    chunk = _make_chunk()
    mock_db = MagicMock()
    mock_db.get.return_value = chunk

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.experience_embedder.embed_text", side_effect=RuntimeError("fail")):
            from app.services.experience_embedder import re_embed_chunk

            re_embed_chunk(chunk_id)  # must not raise

    mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# embed_job_chunks
# ---------------------------------------------------------------------------


def test_embed_job_chunks_embeds_all_null_chunks():
    job_id = uuid.uuid4()
    chunk = _make_chunk(content="5+ years TypeScript")
    db = _make_db([chunk])

    with patch("app.services.experience_embedder.embed_text", return_value=[0.7]):
        with patch("app.services.experience_embedder.settings.embedding_model", "test-model"):
            from app.services.experience_embedder import embed_job_chunks

            embed_job_chunks(job_id, db)

    assert chunk.embedding == [0.7]
    db.commit.assert_called_once()


def test_embed_job_chunks_no_chunks_no_commit():
    job_id = uuid.uuid4()
    db = _make_db([])

    with patch("app.services.experience_embedder.embed_text") as mock_embed:
        from app.services.experience_embedder import embed_job_chunks

        embed_job_chunks(job_id, db)

    mock_embed.assert_not_called()
    db.commit.assert_not_called()
