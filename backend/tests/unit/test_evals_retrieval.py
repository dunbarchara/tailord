from types import SimpleNamespace

from evals import retrieval


def _claim(content, claim_type="work_experience"):
    return SimpleNamespace(content=content, claim_type=claim_type)


def test_cosine_distance_basics():
    assert retrieval.cosine_distance([1, 0], [1, 0]) == 0
    assert abs(retrieval.cosine_distance([1, 0], [0, 1]) - 1) < 1e-9
    assert retrieval.cosine_distance([0, 0], [1, 0]) == 1.0


def test_retrieve_takes_top_k_substantive_plus_separate_skill_pass():
    claims = [_claim(f"w{i}") for i in range(10)] + [_claim(f"s{i}", "skill") for i in range(10)]
    # Every claim sits on a different angle from the query [1, 0]; index i = distance rank.
    vecs = [[1, i * 0.1] for i in range(10)] + [[1, i * 0.1] for i in range(10)]
    got = retrieval.retrieve([1, 0], claims, vecs, k=3)
    contents = [c.content for c, _ in got]
    assert contents[:3] == ["w0", "w1", "w2"]
    assert contents[3:] == [f"s{i}" for i in range(retrieval.K_SKILLS)]


def test_profile_claims_use_production_derivation():
    _, sourced = retrieval.load_profile(retrieval.DEFAULT_PROFILE)
    claims = retrieval.profile_claims(sourced)
    types = {c.claim_type for c in claims}
    assert {"work_experience", "skill", "education"} <= types
    assert all(c.source_type in ("resume", "github") for c in claims)
    assert any(c.source_type == "github" and c.source_ref for c in claims)


def test_scoreable_chunks_excludes_headers_pre_post_and_bare_links():
    base = {"section": None, "position": 0, "posting_id": "p"}
    chunks = [
        {**base, "id": "a", "region": "core", "chunk_type": "bullet", "content": "Python"},
        {**base, "id": "b", "region": "core", "chunk_type": "header", "content": "About"},
        {**base, "id": "c", "region": "pre", "chunk_type": "bullet", "content": "Nav"},
        {
            **base,
            "id": "d",
            "region": "core",
            "chunk_type": "paragraph",
            "content": "[Apply](https://x.example.com)",
        },
    ]
    assert [c["id"] for c in retrieval.scoreable_chunks(chunks)] == ["a"]


def test_estimate_cost_uses_pricing_and_handles_unpriced():
    tokens, cost = retrieval.estimate_cost(["hello world"] * 10, "text-embedding-3-small")
    assert tokens > 0 and cost is not None and cost > 0
    assert retrieval.estimate_cost(["x"], "no-such-model")[1] is None


def test_committed_retrieval_artifact_is_intact_and_chained_to_chunks():
    from evals.stages import CHUNKS_PATH
    from evals.store import read_artifact

    chunks_header, chunks = read_artifact(CHUNKS_PATH)
    header, items = read_artifact(retrieval.RETRIEVAL_PATH)  # verifies the content hash
    assert header.provenance.upstream_hash == chunks_header.content_hash, (
        "retrieval is stale against chunks: rerun `python -m evals.retrieval`"
    )
    assert header.provenance.params["k"] == retrieval.TOP_K
    assert {i["chunk_id"] for i in items} == {c["id"] for c in retrieval.scoreable_chunks(chunks)}
    assert all("RELEVANT EXPERIENCE" in i["user_prompt"] for i in items)
