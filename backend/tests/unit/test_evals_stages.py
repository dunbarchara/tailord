import pytest

from evals import stages
from evals.store import read_artifact

MD = "a\nb\nc\nd\ne"


def test_apply_line_bounds_splits_pre_core_post():
    assert stages.apply_line_bounds(MD, (2, 4)) == ("a", "b\nc\nd", "e")
    assert stages.apply_line_bounds(MD, (1, 5)) == ("", MD, "")


def test_no_bounds_is_the_production_fallback():
    assert stages.apply_line_bounds(MD, None) == ("", MD, "")


@pytest.mark.parametrize("bounds", [(0, 2), (3, 2), (2, 6)])
def test_invalid_bounds_rejected(bounds):
    with pytest.raises(ValueError):
        stages.apply_line_bounds(MD, bounds)


def test_numbered_view():
    assert stages.numbered("x\ny") == "   1| x\n   2| y"


@pytest.fixture
def built(tmp_path):
    md, ck = tmp_path / "markdown.jsonl", tmp_path / "chunks.jsonl"
    stages.build_markdown_artifact(md)
    return md, ck


def test_stages_are_deterministic_and_chained(built):
    md, ck = built
    h1 = stages.build_chunks_artifact(md, ck)
    h2 = stages.build_chunks_artifact(md, ck)
    assert h1 == h2
    md_header, postings = read_artifact(md)
    ck_header, chunks = read_artifact(ck)
    assert ck_header.provenance.upstream_hash == md_header.content_hash
    assert ck_header.provenance.provisional is True
    assert len(postings) == 30
    assert len({c["id"] for c in chunks}) == len(chunks)
    assert all(c["region"] == "core" for c in chunks)  # no bounds: everything is core
    assert all(p["line_count"] > 0 for p in postings)


def test_bounds_mark_regions_and_keep_positions_sequential(built):
    md, ck = built
    _, postings = read_artifact(md)
    target = postings[0]
    n = target["line_count"]
    stages.build_chunks_artifact(md, ck, {target["id"]: (n // 3, 2 * n // 3)}, "test")
    _, chunks = read_artifact(ck)
    mine = [c for c in chunks if c["posting_id"] == target["id"]]
    assert [c["position"] for c in mine] == list(range(len(mine)))
    regions = [c["region"] for c in mine]
    assert regions == sorted(regions, key=["pre", "core", "post"].index)
    assert {"pre", "core", "post"} >= set(regions) and "core" in regions
    assert len(stages.core_chunks(mine)) < len(mine)


def test_postings_stay_under_production_truncation_limit(built):
    md, _ = built
    _, postings = read_artifact(md)
    assert max(len(p["markdown"]) for p in postings) < 12_000 * 3  # ~12k tokens


def test_committed_artifacts_are_current(built):
    """Frozen inputs must match what the code stages produce from the committed postings
    (and, once label round 1 is agreed, the agreed bounds)."""
    from evals.labeling import labels_path
    from evals.store import read_labels

    md, ck = built
    agreed = labels_path("job_bounds", "agreed")
    bounds = None
    if agreed.exists():
        bounds = {r.item_id: (r.label["start"], r.label["end"]) for r in read_labels(agreed)}
    stages.build_chunks_artifact(md, ck, bounds_by_posting=bounds)
    for committed, fresh in ((stages.MARKDOWN_PATH, md), (stages.CHUNKS_PATH, ck)):
        assert read_artifact(committed)[0].content_hash == read_artifact(fresh)[0].content_hash, (
            f"stale {committed.name}: run `uv run python -m evals.stages` or "
            "`python -m evals.labeling rebuild-chunks`"
        )
