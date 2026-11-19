import json

import pytest

from evals import labeling
from evals.schema import LabelRecord

BOUNDS_ITEMS = [
    {"id": "a", "line_count": 10, "markdown": "\n".join(f"l{i}" for i in range(10))},
    {"id": "b", "line_count": 5, "markdown": "\n".join(f"m{i}" for i in range(5))},
]
CHUNK_ITEMS = [{"id": f"p:{i}"} for i in range(4)]


@pytest.fixture
def fake_items(monkeypatch):
    def items_for(task):
        return BOUNDS_ITEMS if task == "job_bounds" else CHUNK_ITEMS

    monkeypatch.setattr(labeling, "items_for", items_for)


def _rec(task, iid, label, source="s"):
    return LabelRecord(task=task, item_id=iid, label=label, label_source=source)


def test_cohen_kappa_known_values():
    assert labeling.cohen_kappa(["x", "y", "x", "y"], ["x", "y", "x", "y"]) == 1.0
    # Always-disagree on a balanced binary labeling is -1.
    assert labeling.cohen_kappa(["x", "y", "x", "y"], ["y", "x", "y", "x"]) == -1.0
    # Textbook example: po=0.7, pe=0.5 -> kappa 0.4.
    a = ["y"] * 25 + ["y"] * 10 + ["n"] * 5 + ["n"] * 10 + ["y"] * 0
    b = ["y"] * 25 + ["n"] * 10 + ["y"] * 5 + ["n"] * 10
    assert labeling.cohen_kappa(a, b) == pytest.approx(
        (0.7 - ((35 * 30) + (15 * 20)) / 2500) / (1 - ((35 * 30) + (15 * 20)) / 2500)
    )


def test_parse_response_tolerates_fences_and_blank_lines():
    text = '```jsonl\n{"id": "p:0", "label": "legal"}\n\n{"id": "p:1", "label": "other"}\n```'
    assert [r["id"] for r in labeling.parse_response(text)] == ["p:0", "p:1"]


@pytest.mark.parametrize("bad", ["not json", '{"id": "x"}', "[1, 2]"])
def test_parse_response_rejects_malformed_lines(bad):
    with pytest.raises(ValueError, match="line 1"):
        labeling.parse_response(bad)


def test_import_semantic_type_requires_every_item_once_and_valid_labels(fake_items):
    ok = "\n".join(json.dumps({"id": f"p:{i}", "label": "other"}) for i in range(4))
    assert len(labeling.import_labels("semantic_type", ok, "silver:x")) == 4
    with pytest.raises(ValueError, match="unlabeled"):
        labeling.import_labels("semantic_type", '{"id": "p:0", "label": "other"}', "s")
    with pytest.raises(ValueError, match="unknown semantic_type"):
        labeling.import_labels("semantic_type", ok.replace("other", "bogus", 1), "s")
    with pytest.raises(ValueError, match="duplicate"):
        labeling.import_labels("semantic_type", ok + '\n{"id": "p:0", "label": "legal"}', "s")
    with pytest.raises(ValueError, match="unknown id"):
        labeling.import_labels("semantic_type", ok + '\n{"id": "zzz", "label": "legal"}', "s")


def test_bounds_validation_checks_range_against_line_count(fake_items):
    item = BOUNDS_ITEMS[0]
    assert labeling.validate_label("job_bounds", {"start": 1, "end": 10}, item) is None
    assert labeling.validate_label("job_bounds", {"start": 0, "end": 3}, item)
    assert labeling.validate_label("job_bounds", {"start": 5, "end": 11}, item)
    assert labeling.validate_label("job_bounds", {"start": 6, "end": 5}, item)
    assert labeling.validate_label("job_bounds", {"start": 1}, item)
    assert labeling.validate_label("job_bounds", {"start": True, "end": 3}, item)


def test_match_score_validation():
    assert labeling.validate_label("match_score", 2, {}) is None
    assert labeling.validate_label("match_score", -1, {}) is None
    assert labeling.validate_label("match_score", 3, {})
    assert labeling.validate_label("match_score", "2", {})
    assert labeling.validate_label("match_score", True, {})


def test_choice_agreement_and_agreed_labels(fake_items):
    a = [_rec("semantic_type", f"p:{i}", lab, "silver:a") for i, lab in enumerate("xxyy")]
    b = [_rec("semantic_type", f"p:{i}", lab, "silver:b") for i, lab in enumerate("xyyy")]
    rep = labeling.agreement("semantic_type", a, b)
    assert rep["n"] == 4 and rep["exact_match"] == 0.75
    assert [d["id"] for d in rep["disagreements"]] == ["p:1"]
    agreed = labeling.agreed_labels("semantic_type", a, b)  # a is primary
    assert [r.label for r in agreed] == list("xxyy")
    assert agreed[1].note and "disagreement" in agreed[1].note
    assert agreed[0].note is None and agreed[0].label_source == "agreed:silver:a"


def test_bounds_agreement_iou_and_line_kappa(fake_items):
    a = [
        _rec("job_bounds", "a", {"start": 1, "end": 10}),
        _rec("job_bounds", "b", {"start": 2, "end": 4}),
    ]
    b = [
        _rec("job_bounds", "a", {"start": 1, "end": 10}),
        _rec("job_bounds", "b", {"start": 2, "end": 3}),
    ]
    rep = labeling.agreement("job_bounds", a, b)
    assert rep["exact_match"] == 0.5
    assert rep["mean_iou"] == pytest.approx((1 + 2 / 3) / 2)
    assert 0 < rep["line_kappa"] < 1
    assert [d["id"] for d in rep["disagreements"]] == ["b"]


def test_requests_contain_no_labels_and_split_into_parts(tmp_path, monkeypatch):
    monkeypatch.setattr(labeling, "REQUESTS_DIR", tmp_path)
    paths = labeling.make_requests("job_bounds", per_part=10)
    assert len(paths) == 3
    text = "".join(p.read_text() for p in paths)
    assert '"start"' in text  # only in the instructions' example
    assert text.count("### POSTING") == 30
    silver = labeling.read_labels(labeling.labels_path("job_bounds", "silver:sonnet-5-5"))
    assert len(silver) == 30  # the committed round-1 silver labels cover every posting


def test_committed_silver_bounds_are_valid_for_current_markdown():
    items = {i["id"]: i for i in labeling.items_for("job_bounds")}
    for r in labeling.read_labels(labeling.labels_path("job_bounds", "silver:sonnet-5-5")):
        assert labeling.validate_label("job_bounds", r.label, items[r.item_id]) is None
