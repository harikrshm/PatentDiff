from pathlib import Path

from core.annotation import load_annotations
from app_unified.pages import eval_traces


def test_build_record_phase3_fail_carries_failure_modes():
    rec = eval_traces.build_record(
        run_id="r1", phase=3, verdict="FAIL",
        failure_modes_ids=["citation_text"], comment="paraphrased", reviewed=True,
        dimensions={"claim_type": "Method"},
    )
    assert rec.failure_modes == ["citation_text"]
    assert rec.verdict == "FAIL"
    assert rec.dimensions == {"claim_type": "Method"}


def test_validate_rejects_fail_without_modes():
    errs = eval_traces.validate_annotation("FAIL", [], comment="x")
    assert any("requires at least one failure mode" in e for e in errs)


def test_validate_rejects_pass_with_modes():
    errs = eval_traces.validate_annotation("PASS", ["citation_text"], comment="x")
    assert any("cannot have failure modes" in e for e in errs)


def test_save_round_trip(tmp_path):
    path = tmp_path / "ann.jsonl"
    rec = eval_traces.build_record(
        run_id="r1", phase=1, verdict="PASS",
        failure_modes_ids=[], comment="ok", reviewed=False, dimensions=None,
    )
    eval_traces.persist_record(path, {"r1": rec})
    loaded = load_annotations(path)
    assert loaded["r1"].verdict == "PASS"
    assert loaded["r1"].comment == "ok"
