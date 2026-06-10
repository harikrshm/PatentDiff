from pathlib import Path

from app_unified.pages import eval_comparison


def test_eval_path_live_vs_named():
    base = Path("traces")
    assert eval_comparison.eval_path(base, "live", "phosita").name == "phosita_eval_full.jsonl"
    assert eval_comparison.eval_path(base, "baseline", "phosita").name == "phosita_eval_full.baseline.jsonl"
    assert eval_comparison.eval_path(base, "baseline", "citation").name == "citation_text_eval_full.baseline.jsonl"
    assert eval_comparison.eval_path(base, "live", "citation").name == "citation_text_eval_full.jsonl"


def test_build_comparison_returns_kpis_and_matrix(tmp_path):
    before = tmp_path / "phosita_eval_full.baseline.jsonl"
    after = tmp_path / "phosita_eval_full.jsonl"
    before.write_text('{"run_id":"r1","verdict":"FAIL"}\n{"run_id":"r2","verdict":"PASS"}\n')
    after.write_text('{"run_id":"r1","verdict":"PASS"}\n{"run_id":"r2","verdict":"PASS"}\n')
    result = eval_comparison.build_comparison(tmp_path, "baseline", "live", "phosita")
    assert result["before_rate"] == 0.5
    assert result["after_rate"] == 1.0
    assert result["matrix"][("FAIL", "PASS")] == 1
    assert result["buckets"][("FAIL", "PASS")] == ["r1"]
