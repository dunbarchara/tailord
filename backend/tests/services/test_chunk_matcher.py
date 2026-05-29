"""Unit tests for chunk_matcher.enrich_job_chunks and re_enrich_single_chunk.

Both functions create their own DB sessions internally, so SessionLocal is
patched at app.clients.database.SessionLocal. extract_chunks and
_format_sourced_profile are also patched to keep tests self-contained.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.schemas.matching import ChunkMatchBatch, ChunkMatchResult
from app.services.chunk_matcher import (
    _build_candidate_header,
    _build_grouped_context,
    _derive_evaluation_status,
    enrich_job_chunks,
    re_enrich_single_chunk,
    resolve_chunk_flags,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk(position, content="requirement text", chunk_type="bullet", section="Requirements"):
    return SimpleNamespace(
        position=position,
        content=content,
        chunk_type=chunk_type,
        section=section,
    )


def _run_enrich(job_id, chunks, llm_result, mock_db=None):
    """Run enrich_job_chunks with all external dependencies mocked.

    Returns (added_objects, mock_db) where added_objects is the list of
    JobChunk instances passed to db.add().
    """
    if mock_db is None:
        mock_db = MagicMock()
    added = []
    mock_db.add.side_effect = lambda obj: added.append(obj)

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.extract_chunks", return_value=chunks):
            with patch("app.services.chunk_matcher.llm_parse_with_retry", return_value=llm_result):
                with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                    with patch(
                        "app.services.chunk_matcher.format_sourced_profile",
                        return_value="formatted profile",
                    ):
                        enrich_job_chunks(job_id, "# Job\n\nContent", {})

    return added, mock_db


# ---------------------------------------------------------------------------
# enrich_job_chunks — score paths
# ---------------------------------------------------------------------------


def test_score_0_chunk_persisted():
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "Kubernetes experience")]
    llm_result = ChunkMatchBatch(results=[ChunkMatchResult(score=0, rationale="No match")])

    added, _ = _run_enrich(job_id, chunks, llm_result)

    assert len(added) == 1
    assert added[0].match_score == 0


def test_score_1_chunk_persisted():
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "Python experience")]
    llm_result = ChunkMatchBatch(
        results=[
            ChunkMatchResult(score=1, rationale="Some Python", advocacy_blurb="Has some Python")
        ]
    )

    added, _ = _run_enrich(job_id, chunks, llm_result)

    assert len(added) == 1
    assert added[0].match_score == 1
    assert added[0].advocacy_blurb == "Has some Python"


def test_score_2_chunk_persisted():
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "Python 5+ years")]
    llm_result = ChunkMatchBatch(
        results=[
            ChunkMatchResult(
                score=2, rationale="Strong Python", advocacy_blurb="Excellent Python engineer"
            )
        ]
    )

    added, _ = _run_enrich(job_id, chunks, llm_result)

    assert len(added) == 1
    assert added[0].match_score == 2
    assert added[0].advocacy_blurb == "Excellent Python engineer"


def test_header_chunks_get_minus_one_score():
    """Header chunks bypass LLM — persisted with score=-1."""
    job_id = uuid.uuid4()
    chunks = [
        _chunk(0, "Requirements", chunk_type="header", section=None),
        _chunk(1, "Python experience"),
    ]
    llm_result = ChunkMatchBatch(
        results=[ChunkMatchResult(score=2, rationale="Strong", advocacy_blurb="Great Python")]
    )

    added, _ = _run_enrich(job_id, chunks, llm_result)

    scores = {c.content: c.match_score for c in added}
    assert scores["Requirements"] == -1
    assert scores["Python experience"] == 2


# ---------------------------------------------------------------------------
# enrich_job_chunks — batch error telemetry
# ---------------------------------------------------------------------------


def test_batch_error_increments_error_count():
    """LLM failure → batch_errors=1 merged into generation_telemetry JSONB."""
    job_id = uuid.uuid4()
    chunks = [_chunk(0), _chunk(1), _chunk(2)]
    mock_db = MagicMock()

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.extract_chunks", return_value=chunks):
            with patch(
                "app.services.chunk_matcher.llm_parse_with_retry",
                side_effect=RuntimeError("LLM down"),
            ):
                with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                    with patch(
                        "app.services.chunk_matcher.format_sourced_profile",
                        return_value="profile",
                    ):
                        enrich_job_chunks(job_id, "# Job\n\nContent", {})

    # Telemetry is now written via db.execute(text(...), params) to merge into JSONB.
    # Find the telemetry update call among all execute() calls (skip single-arg SET LOCAL call).
    telemetry_params = next(
        (
            c.args[1]
            for c in mock_db.execute.call_args_list
            if len(c.args) > 1 and isinstance(c.args[1], dict) and "error_count" in c.args[1]
        ),
        None,
    )
    assert telemetry_params is not None, "Expected db.execute telemetry call not found"
    assert telemetry_params["error_count"] == 1


def test_batch_error_pads_chunks_with_minus_one():
    """On LLM failure, all chunks in the failed batch are persisted with score=-1."""
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "req A"), _chunk(1, "req B")]
    mock_db = MagicMock()
    added = []
    mock_db.add.side_effect = lambda obj: added.append(obj)

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.extract_chunks", return_value=chunks):
            with patch(
                "app.services.chunk_matcher.llm_parse_with_retry",
                side_effect=RuntimeError("LLM down"),
            ):
                with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                    with patch(
                        "app.services.chunk_matcher.format_sourced_profile",
                        return_value="profile",
                    ):
                        enrich_job_chunks(job_id, "# Job\n\nContent", {})

    assert len(added) == 2
    assert all(c.match_score == -1 for c in added)


# ---------------------------------------------------------------------------
# re_enrich_single_chunk
# ---------------------------------------------------------------------------


def test_re_enrich_updates_chunk_fields_in_place():
    mock_chunk = MagicMock()
    mock_chunk.section = "Requirements"
    mock_chunk.chunk_type = "bullet"
    mock_chunk.content = "Python experience"

    mock_db = MagicMock()
    mock_db.get.return_value = mock_chunk

    llm_result = ChunkMatchBatch(
        results=[
            ChunkMatchResult(
                score=2,
                rationale="Strong Python",
                advocacy_blurb="Expert Python engineer",
                experience_sources=["resume"],
                should_render=True,
            )
        ]
    )

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.llm_parse_with_retry", return_value=llm_result):
            with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                with patch(
                    "app.services.chunk_matcher.format_sourced_profile",
                    return_value="profile",
                ):
                    re_enrich_single_chunk("fake-chunk-id", {})

    assert mock_chunk.match_score == 2
    assert mock_chunk.match_rationale == "Strong Python"
    assert mock_chunk.advocacy_blurb == "Expert Python engineer"
    assert mock_chunk.experience_sources == ["resume"]
    assert mock_chunk.should_render is True
    mock_db.commit.assert_called_once()


def test_re_enrich_chunk_not_found_does_not_crash():
    mock_db = MagicMock()
    mock_db.get.return_value = None

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        re_enrich_single_chunk("nonexistent-chunk-id", {})

    mock_db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# _build_candidate_header
# ---------------------------------------------------------------------------


def test_build_candidate_header_name_and_pronouns():
    result = _build_candidate_header("Alex Chen", "they/them")
    assert "[CANDIDATE]" in result
    assert "Name: Alex Chen" in result
    assert "they/them" in result


def test_build_candidate_header_name_only():
    result = _build_candidate_header("Jordan", None)
    assert "Name: Jordan" in result
    assert "Pronouns" not in result


def test_build_candidate_header_pronouns_only():
    result = _build_candidate_header(None, "she/her")
    assert "she/her" in result
    assert "Name" not in result


def test_build_candidate_header_neither_returns_empty():
    assert _build_candidate_header(None, None) == ""


# ---------------------------------------------------------------------------
# _build_grouped_context
# ---------------------------------------------------------------------------


def _exp_chunk(
    content,
    group_key=None,
    date_range=None,
    source_type="resume",
    source_ref=None,
    keywords=None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        group_key=group_key,
        date_range=date_range,
        source_type=source_type,
        source_ref=source_ref,
        keywords=keywords,
    )


def test_build_grouped_context_single_group():
    chunks = [
        _exp_chunk("Built REST APIs", group_key="ACME | SWE", date_range="2021–2024"),
        _exp_chunk("Led platform migration", group_key="ACME | SWE", date_range="2021–2024"),
    ]
    result = _build_grouped_context(chunks)
    assert "ACME | SWE" in result
    assert "2021–2024" in result
    assert "Built REST APIs" in result
    assert "Led platform migration" in result


def test_build_grouped_context_github_source_type():
    chunks = [
        _exp_chunk(
            "Full-stack web app",
            group_key="tailord",
            source_type="github",
            keywords=["Python", "FastAPI"],
        )
    ]
    result = _build_grouped_context(chunks)
    assert "GitHub: tailord" in result
    assert "Python" in result
    assert "FastAPI" in result


def test_build_grouped_context_ungrouped_skills():
    chunks = [_exp_chunk("TypeScript"), _exp_chunk("Go")]
    result = _build_grouped_context(chunks)
    assert "TypeScript" in result
    assert "Go" in result


def test_build_grouped_context_mixed():
    chunks = [
        _exp_chunk("Built APIs", group_key="ACME | SWE", date_range="2022–2024"),
        _exp_chunk("TypeScript"),  # ungrouped skill
    ]
    result = _build_grouped_context(chunks)
    assert "ACME | SWE" in result
    assert "TypeScript" in result


def test_build_grouped_context_empty():
    assert _build_grouped_context([]) == ""


# ---------------------------------------------------------------------------
# _build_grouped_context — FK-linked groups (parent_group_id set)
# ---------------------------------------------------------------------------


def _make_group(
    group_id, name, group_type="role", source_type="resume", parent_group_id=None, parent=None
):
    return SimpleNamespace(
        id=group_id,
        name=name,
        group_type=group_type,
        source_type=source_type,
        parent_group_id=parent_group_id,
        parent=parent,
    )


def _exp_chunk_fk(
    content, group_id, group, source_type="resume", source_ref=None, date_range=None, keywords=None
):
    return SimpleNamespace(
        content=content,
        group_id=group_id,
        group=group,
        group_key=None,
        date_range=date_range,
        source_type=source_type,
        source_ref=source_ref,
        keywords=keywords,
    )


def test_build_grouped_context_fk_single_group():
    """FK-bucketed claims appear under the group's name."""
    gid = uuid.uuid4()
    group = _make_group(gid, "Startup | CTO")
    chunks = [
        _exp_chunk_fk("Scaled infra to 10k users", gid, group, date_range="2022–2024"),
        _exp_chunk_fk("Hired engineering team", gid, group, date_range="2022–2024"),
    ]
    result = _build_grouped_context(chunks)
    assert "Startup | CTO" in result
    assert "Scaled infra" in result
    assert "Hired engineering team" in result


def test_build_grouped_context_fk_linked_repo_merges_under_parent():
    """A repo group with parent_group_id merges its claims under the parent's header."""
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    parent_group = _make_group(
        parent_id, "Tailord | Founder", group_type="role", source_type="resume"
    )
    child_group = _make_group(
        child_id,
        "tailord",
        group_type="repository",
        source_type="github",
        parent_group_id=parent_id,
        parent=parent_group,
    )

    resume_claim = _exp_chunk_fk(
        "Led product development",
        parent_id,
        parent_group,
        source_type="resume",
        date_range="2024–Present",
    )
    github_claim = _exp_chunk_fk(
        "Python",
        child_id,
        child_group,
        source_type="github",
        source_ref="tailord",
    )

    result = _build_grouped_context([resume_claim, github_claim])

    # Both appear under a single header (parent's name)
    assert "Tailord | Founder" in result
    assert "Led product development" in result
    assert "Python" in result
    # Source labels present since two source_types in same bucket
    assert "[resume]" in result
    assert "[github: tailord]" in result
    # The child group header does NOT appear as a separate section
    assert result.count("tailord") == result.count("[github: tailord]")


def test_build_grouped_context_fk_no_mixed_labels_when_single_source():
    """When all claims share the same source_type, no inline source labels are added."""
    gid = uuid.uuid4()
    group = _make_group(gid, "Corp | Engineer")
    chunks = [
        _exp_chunk_fk("Built CI pipeline", gid, group, source_type="resume"),
        _exp_chunk_fk("Reduced deploy time 50%", gid, group, source_type="resume"),
    ]
    result = _build_grouped_context(chunks)
    assert "[resume]" not in result
    assert "Built CI pipeline" in result


# ---------------------------------------------------------------------------
# enrich_job_chunks — vector dispatch
# ---------------------------------------------------------------------------


def _run_enrich_vector(job_id, chunks, llm_result, experience_id=None):
    """Run enrich_job_chunks in vector mode with all external deps mocked."""
    if experience_id is None:
        experience_id = uuid.uuid4()

    mock_db = MagicMock()
    added = []
    mock_db.add.side_effect = lambda obj: added.append(obj)

    # _retrieve_top_k_experience_chunks returns one dummy chunk so grouped_context is non-empty
    dummy_exp_chunk = _exp_chunk("Relevant experience bullet", group_key="ACME | SWE")

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.extract_chunks", return_value=chunks):
            with patch("app.services.chunk_matcher.llm_parse_with_retry", return_value=llm_result):
                with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                    with patch(
                        "app.services.chunk_matcher._retrieve_top_k_experience_chunks",
                        return_value=[dummy_exp_chunk],
                    ):
                        with patch(
                            "app.clients.embedding_client.embed_text", return_value=[0.1] * 1536
                        ):
                            with patch("app.services.chunk_matcher.settings") as mock_settings:
                                mock_settings.matching_mode = "vector"
                                mock_settings.vector_top_k = 8
                                mock_settings.llm_model = "gpt-4o-mini"
                                mock_settings.embedding_model = "text-embedding-3-small"
                                mock_settings.chunk_scorer_concurrency = 8
                                enrich_job_chunks(
                                    job_id,
                                    "# Job\n\nContent",
                                    {},
                                    user_id=experience_id,
                                )

    return added, mock_db


def test_vector_mode_scores_non_header_chunks():
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "TypeScript experience")]
    llm_result = ChunkMatchBatch(
        results=[ChunkMatchResult(score=2, rationale="Strong", advocacy_blurb="Excellent")]
    )

    added, _ = _run_enrich_vector(job_id, chunks, llm_result)

    assert len(added) == 1
    assert added[0].match_score == 2
    assert added[0].match_rationale
    assert "[vector" not in added[0].match_rationale


def test_vector_mode_header_chunks_get_minus_one():
    job_id = uuid.uuid4()
    chunks = [
        _chunk(0, "Requirements", chunk_type="header", section=None),
        _chunk(1, "TypeScript experience"),
    ]
    llm_result = ChunkMatchBatch(
        results=[ChunkMatchResult(score=2, rationale="Strong", advocacy_blurb="Excellent")]
    )

    added, _ = _run_enrich_vector(job_id, chunks, llm_result)

    scores = {c.content: c.match_score for c in added}
    assert scores["Requirements"] == -1
    assert scores["TypeScript experience"] == 2


def test_vector_mode_falls_back_to_llm_when_no_experience_id():
    """MATCHING_MODE=vector but experience_id=None → llm path used (no embed_text call)."""
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "Python experience")]
    llm_result = ChunkMatchBatch(results=[ChunkMatchResult(score=1, rationale="Partial")])

    mock_db = MagicMock()
    added = []
    mock_db.add.side_effect = lambda obj: added.append(obj)

    embed_text_mock = MagicMock()

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.extract_chunks", return_value=chunks):
            with patch("app.services.chunk_matcher.llm_parse_with_retry", return_value=llm_result):
                with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                    with patch(
                        "app.services.chunk_matcher.format_sourced_profile",
                        return_value="profile",
                    ):
                        with patch("app.clients.embedding_client.embed_text", embed_text_mock):
                            with patch("app.services.chunk_matcher.settings") as mock_settings:
                                mock_settings.matching_mode = "vector"
                                mock_settings.vector_top_k = 8
                                mock_settings.llm_model = "gpt-4o-mini"
                                mock_settings.embedding_model = "text-embedding-3-small"
                                mock_settings.chunk_scorer_concurrency = 8
                                # No experience_id — should fall back to llm path
                                enrich_job_chunks(job_id, "# Job\n\nContent", {})

    embed_text_mock.assert_not_called()
    assert len(added) == 1
    assert added[0].match_score == 1


# ---------------------------------------------------------------------------
# re_enrich_single_chunk — vector path
# ---------------------------------------------------------------------------


def test_re_enrich_vector_path_updates_chunk_fields():
    mock_chunk = MagicMock()
    mock_chunk.section = "Requirements"
    mock_chunk.chunk_type = "bullet"
    mock_chunk.content = "TypeScript experience"
    mock_chunk.embedding = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_chunk
    # _append_pinned_claims queries for claims linked via provenance_metadata; return empty
    # so the top-k list from the patched _retrieve_top_k_experience_chunks is unchanged.
    mock_db.query.return_value.filter.return_value.all.return_value = []

    dummy_exp_chunk = _exp_chunk("Built APIs in TypeScript", group_key="ACME | SWE")
    llm_result = ChunkMatchBatch(
        results=[
            ChunkMatchResult(
                score=2,
                rationale="Strong match",
                advocacy_blurb="Expert TypeScript engineer",
                should_render=True,
            )
        ]
    )

    experience_id = uuid.uuid4()

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.llm_parse_with_retry", return_value=llm_result):
            with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                with patch(
                    "app.services.chunk_matcher._retrieve_top_k_experience_chunks",
                    return_value=[dummy_exp_chunk],
                ):
                    with patch(
                        "app.clients.embedding_client.embed_text", return_value=[0.1] * 1536
                    ):
                        with patch("app.services.chunk_matcher.settings") as mock_settings:
                            mock_settings.matching_mode = "vector"
                            mock_settings.vector_top_k = 8
                            mock_settings.llm_model = "gpt-4o-mini"
                            mock_settings.embedding_model = "text-embedding-3-small"
                            re_enrich_single_chunk("fake-chunk-id", {}, user_id=experience_id)

    assert mock_chunk.match_score == 2
    assert mock_chunk.match_rationale
    assert "[vector" not in mock_chunk.match_rationale
    assert mock_chunk.advocacy_blurb == "Expert TypeScript engineer"
    # Embedding was null — should be populated opportunistically
    assert mock_chunk.embedding is not None
    mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# resolve_chunk_flags
# ---------------------------------------------------------------------------


def test_resolve_job_requirement_forces_include_in_scoring_true():
    """Even if LLM says include_in_scoring=False, job_requirement overrides to True."""
    result = ChunkMatchResult(
        score=0, rationale="Gap", semantic_type="job_requirement", include_in_scoring=False
    )
    resolved = resolve_chunk_flags(result)
    assert resolved.include_in_scoring is True
    assert resolved.should_render is True


def test_resolve_company_description_render_always_false():
    """company_description: should_render always False; include_in_scoring passes through."""
    result = ChunkMatchResult(
        score=-1,
        rationale="About us",
        semantic_type="company_description",
        include_in_scoring=True,
        should_render=True,
    )
    resolved = resolve_chunk_flags(result)
    assert resolved.should_render is False
    assert resolved.include_in_scoring is True  # LLM value preserved


def test_resolve_compensation_both_false():
    """compensation: both flags forced False regardless of LLM values."""
    result = ChunkMatchResult(
        score=-1,
        rationale="Salary",
        semantic_type="compensation",
        include_in_scoring=True,
        should_render=True,
    )
    resolved = resolve_chunk_flags(result)
    assert resolved.include_in_scoring is False
    assert resolved.should_render is False


def test_resolve_other_passes_through_llm_values():
    """other: LLM decides both flags."""
    result = ChunkMatchResult(
        score=-1,
        rationale="Misc",
        semantic_type="other",
        include_in_scoring=False,
        should_render=False,
    )
    resolved = resolve_chunk_flags(result)
    assert resolved.include_in_scoring is False
    assert resolved.should_render is False


# ---------------------------------------------------------------------------
# _derive_evaluation_status
# ---------------------------------------------------------------------------


def test_derive_evaluation_status_header_returns_skipped():
    match = ChunkMatchResult(score=-1, rationale="Section header")
    assert _derive_evaluation_status(match, "header") == "skipped"


def test_derive_evaluation_status_not_scored_returns_skipped():
    match = ChunkMatchResult(score=-1, rationale="Company perk", include_in_scoring=False)
    assert _derive_evaluation_status(match, "bullet") == "skipped"


def test_derive_evaluation_status_score_2_returns_scored():
    match = ChunkMatchResult(score=2, rationale="Strong", include_in_scoring=True)
    assert _derive_evaluation_status(match, "bullet") == "scored"


def test_derive_evaluation_status_error_rationale_returns_error():
    match = ChunkMatchResult(score=-1, rationale="LLM error occurred", include_in_scoring=True)
    assert _derive_evaluation_status(match, "bullet") == "error"


# ---------------------------------------------------------------------------
# enrich_job_chunks — evaluation_status and semantic_type
# ---------------------------------------------------------------------------


def test_enrich_sets_evaluation_status_scored():
    """enrich_job_chunks sets evaluation_status='scored' on score=2 chunk."""
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "Python 5+ years")]
    llm_result = ChunkMatchBatch(
        results=[
            ChunkMatchResult(
                score=2,
                rationale="Strong",
                advocacy_blurb="Expert",
                semantic_type="job_requirement",
            )
        ]
    )

    added, _ = _run_enrich(job_id, chunks, llm_result)

    assert added[0].evaluation_status == "scored"


def test_enrich_header_gets_evaluation_status_skipped():
    """Header chunks get evaluation_status='skipped'."""
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "Requirements", chunk_type="header", section=None)]
    llm_result = ChunkMatchBatch(results=[])

    added, _ = _run_enrich(job_id, chunks, llm_result)

    assert added[0].evaluation_status == "skipped"


def test_refresh_does_not_modify_semantic_type():
    """refresh_job_chunks must not touch semantic_type or include_in_scoring."""
    from app.services.chunk_matcher import refresh_job_chunks

    mock_chunk = MagicMock()
    mock_chunk.chunk_type = "bullet"
    mock_chunk.section = "Requirements"
    mock_chunk.content = "Python"
    mock_chunk.include_in_scoring = True
    mock_chunk.semantic_type = "job_requirement"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        mock_chunk
    ]

    llm_result = ChunkMatchBatch(
        results=[ChunkMatchResult(score=2, rationale="Strong", advocacy_blurb="Expert")]
    )

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.llm_parse_with_retry", return_value=llm_result):
            with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                with patch(
                    "app.services.chunk_matcher.format_sourced_profile",
                    return_value="profile",
                ):
                    refresh_job_chunks(uuid.uuid4(), "tailoring-id", {})

    # semantic_type must not have been assigned
    assert mock_chunk.semantic_type == "job_requirement"  # unchanged original value
