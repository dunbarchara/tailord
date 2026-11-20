import json

import pytest

from evals.probes import section_labels
from evals.tasks import TASKS
from evals.tasks import real as real_tasks


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Core Responsibilities", True),
        ("Required Qualifications:", True),
        ("SWE principles include:", True),
        ("A World-Changing Company", True),
        ("3+ years of Python experience.", False),
        ("We are looking for an engineer to build great things for our customers today", False),
        ("Excellent communication skills.", False),
    ],
)
def test_label_heuristic(text, expected):
    assert section_labels.looks_like_label(text) is expected


def test_real_tasks_are_registered_and_share_the_semantic_type_definition():
    assert {"real_semantic_type", "real_section_label"} <= set(TASKS)
    st, real = TASKS["semantic_type"], TASKS["real_semantic_type"]
    assert (real.labels, real.instructions) == (st.labels, st.instructions)
    assert set(TASKS["real_section_label"].labels) == {"section_label", "content"}


def test_real_items_exclude_headers_and_carry_no_labels(tmp_path, monkeypatch):
    chunks = [
        {
            "id": "r:0",
            "posting_id": "r",
            "position": 0,
            "chunk_type": "header",
            "section": None,
            "content": "About",
        },
        {
            "id": "r:1",
            "posting_id": "r",
            "position": 1,
            "chunk_type": "paragraph",
            "section": "About",
            "content": "Hello",
        },
    ]
    path = tmp_path / "chunks.json"
    path.write_text(json.dumps(chunks))
    monkeypatch.setattr(section_labels, "CHUNKS", path)
    items = real_tasks.load_real_items()
    assert [i.id for i in items] == ["r:1"] and items[0].labels == {}


def test_missing_local_data_gives_a_clear_instruction(tmp_path, monkeypatch):
    monkeypatch.setattr(section_labels, "CHUNKS", tmp_path / "nope.json")
    with pytest.raises(SystemExit, match="section_labels fetch"):
        real_tasks.load_real_items()


def test_summarize_counts_flagged_chunks_and_postings_without_printing_text(
    tmp_path, monkeypatch, capsys
):
    from evals import runner

    chunks = [
        {
            "id": f"r{p}:{n}",
            "posting_id": f"r{p}",
            "position": n,
            "chunk_type": "paragraph",
            "section": None,
            "content": f"text {p}{n}",
        }
        for p in (1, 2)
        for n in range(2)
    ]
    cpath = tmp_path / "chunks.json"
    cpath.write_text(json.dumps(chunks))
    ipath = tmp_path / "index.json"
    ipath.write_text(json.dumps({"r1": {}, "r2": {}}))
    monkeypatch.setattr(section_labels, "CHUNKS", cpath)
    monkeypatch.setattr(section_labels, "INDEX", ipath)
    task = TASKS["real_section_label"]
    store = runner.ResultStore(task.name, "jev-1.14.0", tmp_path)
    for item, p in zip(real_tasks.load_real_items(), (0.99, 0.6, 0.1, 0.2)):
        store.append(
            {
                "item_id": item.id,
                "run": 0,
                "input_hash": runner.input_hash(task, item),
                "error": None,
                "probabilities": {"section_label": p, "content": 1 - p},
            }
        )
    out = section_labels.summarize(root=tmp_path)
    assert out["answered"] == 4
    assert out["p>=0.5"] == {"chunks": 2, "postings": 1}  # both flags are in posting r1
    assert out["p>=0.9"] == {"chunks": 1, "postings": 1}
    assert "text 1" not in capsys.readouterr().out  # aggregates only
