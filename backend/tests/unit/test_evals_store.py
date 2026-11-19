import pytest

from evals.schema import LabelRecord, Provenance, item_id
from evals.store import content_hash, read_artifact, read_labels, write_artifact, write_labels


def _prov(**kw):
    base = dict(producer_kind="code", producer_task="chunking", producer="abc123")
    return Provenance(**{**base, **kw})


def test_hash_is_order_and_key_order_sensitive_but_deterministic():
    a = [{"id": "1", "x": 1}, {"id": "2", "x": 2}]
    assert content_hash(a) == content_hash([{"x": 1, "id": "1"}, {"x": 2, "id": "2"}])
    assert content_hash(a) != content_hash(list(reversed(a)))


def test_artifact_roundtrip(tmp_path):
    items = [{"id": "p1:0", "text": "héllo"}, {"id": "p1:1", "text": "wörld"}]
    header = write_artifact(tmp_path / "chunks.jsonl", "chunks", items, _prov(provisional=True))
    got_header, got_items = read_artifact(tmp_path / "chunks.jsonl")
    assert got_items == items
    assert got_header.content_hash == header.content_hash
    assert got_header.provenance.provisional is True


def test_hand_edited_artifact_is_rejected(tmp_path):
    path = tmp_path / "a.jsonl"
    write_artifact(path, "a", [{"id": "1", "v": "x"}], _prov())
    path.write_text(path.read_text().replace('"v":"x"', '"v":"y"'))
    with pytest.raises(ValueError, match="hash"):
        read_artifact(path)


def test_labels_roundtrip(tmp_path):
    recs = [
        LabelRecord(
            task="semantic_type",
            item_id=item_id("p1", 0),
            label="legal",
            label_source="silver:sonnet-5-5",
        )
    ]
    assert write_labels(tmp_path / "l.jsonl", recs) == 1
    assert read_labels(tmp_path / "l.jsonl")[0].item_id == "p1:0"


def test_item_id_joins_natural_key():
    assert item_id("gh-01", 14, "alex") == "gh-01:14:alex"
