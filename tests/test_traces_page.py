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


def test_build_record_phase1_fail_uses_open_coded_modes():
    rec = eval_traces.build_record(
        run_id="r2", phase=1, verdict="FAIL",
        failure_modes_ids=["hallucination"], comment="made up text",
        reviewed=False, dimensions=None,
    )
    assert rec.open_coded_failure_modes == ["hallucination"]
    assert rec.failure_modes is None


def test_trace_coverage_counts():
    from types import SimpleNamespace

    from core.annotation import AnnotationRecord
    traces = {f"r{i}": SimpleNamespace(run_id=f"r{i}") for i in range(4)}
    anns = {
        "r0": AnnotationRecord(run_id="r0", phase=3, verdict="PASS",
                               comment="x", reviewed=True),
        "r1": AnnotationRecord(run_id="r1", phase=3, verdict="PASS",
                               comment="x", reviewed=False),
    }
    cov = eval_traces.trace_coverage(traces, anns)
    assert cov["total"] == 4 and cov["reviewed"] == 1
    assert cov["reviewed_ids"] == {"r0"}


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
