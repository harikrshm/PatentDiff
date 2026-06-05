import json
from pathlib import Path

import pandas as pd

from core.workbench_data import TraceSet, list_trace_sets, load_merged


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_list_trace_sets_discovers_live_and_suffixed(tmp_path: Path):
    (tmp_path / "traces.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "phosita_eval_full.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "citation_text_eval_full.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "phosita_eval_full.exp1.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "citation_text_eval_full.exp1.jsonl").write_text("", encoding="utf-8")

    sets = {s.name: s for s in list_trace_sets(tmp_path)}

    assert "live" in sets
    assert "exp1" in sets
    assert sets["live"].phosita_path.name == "phosita_eval_full.jsonl"
    assert sets["exp1"].phosita_path.name == "phosita_eval_full.exp1.jsonl"


def test_load_merged_one_row_per_trace_with_human_override(tmp_path: Path):
    _write_jsonl(
        tmp_path / "traces.jsonl",
        [{"run_id": "r1", "inputs": {}, "parsed_output": {"element_mappings": []}}],
    )
    _write_jsonl(
        tmp_path / "phosita_eval_full.jsonl",
        [{"run_id": "r1", "verdict": "FAIL", "config": {"prompt_version": "v3"}}],
    )
    _write_jsonl(
        tmp_path / "citation_text_eval_full.jsonl",
        [{"run_id": "r1", "verdict": "PASS"}],
    )
    _write_jsonl(
        tmp_path / "traces_annotations.jsonl",
        [{"run_id": "r1", "phase": 3,
          "dimensions": {"claim_type": "System", "claim_length": "Long",
                         "relationship": "Novel"}}],
    )

    ts = TraceSet(
        name="live",
        traces_path=tmp_path / "traces.jsonl",
        phosita_path=tmp_path / "phosita_eval_full.jsonl",
        citation_path=tmp_path / "citation_text_eval_full.jsonl",
    )
    df = load_merged(ts, annotations_path=tmp_path / "traces_annotations.jsonl")

    assert len(df) == 1
    row = df.iloc[0]
    assert row["run_id"] == "r1"
    assert row["phosita_verdict"] == "FAIL"
    assert row["citation_verdict"] == "PASS"
    assert row["claim_type"] == "System"        # human override applied
    assert row["dim_source"] == "human"


def test_load_merged_filters_phosita_to_v3(tmp_path: Path):
    _write_jsonl(tmp_path / "traces.jsonl",
                 [{"run_id": "r1", "inputs": {}, "parsed_output": {"element_mappings": []}}])
    _write_jsonl(
        tmp_path / "phosita_eval_full.jsonl",
        [{"run_id": "r1", "verdict": "FAIL", "config": {"prompt_version": "v1"}}],
    )
    _write_jsonl(tmp_path / "citation_text_eval_full.jsonl",
                 [{"run_id": "r1", "verdict": "PASS"}])

    ts = TraceSet("live", tmp_path / "traces.jsonl",
                  tmp_path / "phosita_eval_full.jsonl",
                  tmp_path / "citation_text_eval_full.jsonl")
    df = load_merged(ts, annotations_path=tmp_path / "missing.jsonl")

    # v1 phosita verdict ignored; only citation present
    assert df.iloc[0]["phosita_verdict"] is None
    assert df.iloc[0]["citation_verdict"] == "PASS"
