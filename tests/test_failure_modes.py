"""Block 2 failure-mode breakdown aggregation."""
import json

from core.annotation import AnnotationRecord, save_annotations
from core.failure_modes import UNTAGGED_LABEL, failure_mode_breakdown


def _eval(path, mapping):
    from core.phosita_eval import PROMPT_VERSION
    with open(path, "w", encoding="utf-8") as f:
        for rid, v in mapping.items():
            f.write(json.dumps({"run_id": rid, "verdict": v,
                                "config": {"prompt_version": PROMPT_VERSION}}) + "\n")


def _taxonomy(path):
    path.write_text(json.dumps({"failure_categories": [
        {"id": "citation_text", "name": "Citation Text"},
        {"id": "absent_phosita_reasoning", "name": "Absent PHOSITA Reasoning"},
    ]}), encoding="utf-8")


def test_breakdown_counts_modes_and_untagged(tmp_path):
    # live set eval files: r1/r2/r3 FAIL on phosita; r4 PASS
    _eval(tmp_path / "phosita_eval_full.jsonl",
          {"r1": "FAIL", "r2": "FAIL", "r3": "FAIL", "r4": "PASS"})
    _eval(tmp_path / "citation_text_eval_full.jsonl",
          {"r1": "FAIL", "r2": "PASS", "r3": "PASS", "r4": "PASS"})
    tax = tmp_path / "tax.json"; _taxonomy(tax)
    anns = tmp_path / "ann.jsonl"
    save_annotations(anns, {
        "r1": AnnotationRecord(run_id="r1", phase=3, verdict="FAIL",
                               failure_modes=["citation_text"], comment="x"),
        "r2": AnnotationRecord(run_id="r2", phase=3, verdict="FAIL",
                               failure_modes=["absent_phosita_reasoning"], comment="x"),
        # r3 is an eval FAIL with NO annotation -> untagged
    })
    out = failure_mode_breakdown(tmp_path, "live", annotations_path=anns,
                                 taxonomy_path=tax)
    d = dict(out)
    assert d["Citation Text"] == 1
    assert d["Absent PHOSITA Reasoning"] == 1
    assert d[UNTAGGED_LABEL] == 1          # r3
    assert out[-1][0] == UNTAGGED_LABEL    # untagged sorted last


def test_breakdown_empty_when_no_fails(tmp_path):
    _eval(tmp_path / "phosita_eval_full.jsonl", {"r1": "PASS"})
    tax = tmp_path / "tax.json"; _taxonomy(tax)
    out = failure_mode_breakdown(tmp_path, "live",
                                 annotations_path=tmp_path / "none.jsonl",
                                 taxonomy_path=tax)
    assert out == []
