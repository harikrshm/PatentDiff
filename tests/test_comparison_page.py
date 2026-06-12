import json
from pathlib import Path

from app_unified.pages import eval_comparison
from core.phosita_eval import PROMPT_VERSION as _PV


def _phosita_line(run_id, verdict):
    return json.dumps({"run_id": run_id, "verdict": verdict,
                       "config": {"prompt_version": _PV}}) + "\n"


def test_eval_path_live_vs_named():
    base = Path("traces")
    assert eval_comparison.eval_path(base, "live", "phosita").name == "phosita_eval_full.jsonl"
    assert eval_comparison.eval_path(base, "baseline", "phosita").name == "phosita_eval_full.baseline.jsonl"
    assert eval_comparison.eval_path(base, "baseline", "citation").name == "citation_text_eval_full.baseline.jsonl"
    assert eval_comparison.eval_path(base, "live", "citation").name == "citation_text_eval_full.jsonl"


def test_build_comparison_returns_kpis_and_matrix(tmp_path):
    before = tmp_path / "phosita_eval_full.baseline.jsonl"
    after = tmp_path / "phosita_eval_full.jsonl"
    before.write_text(_phosita_line("r1", "FAIL") + _phosita_line("r2", "PASS"))
    after.write_text(_phosita_line("r1", "PASS") + _phosita_line("r2", "PASS"))
    result = eval_comparison.build_comparison(tmp_path, "baseline", "live", "phosita")
    assert result["before_rate"] == 0.5
    assert result["after_rate"] == 1.0
    assert result["matrix"][("FAIL", "PASS")] == 1
    assert result["buckets"][("FAIL", "PASS")] == ["r1"]


# ── _kpi_tiles: failure-rate display layer ────────────────────────────────────

_BASE_R = {
    "before_rate": 0.5, "after_rate": 0.75, "delta_pp": 25.0,
    "before_scored": 10, "after_scored": 12,
}
_REGRESS_R = {
    "before_rate": 0.75, "after_rate": 0.5, "delta_pp": -25.0,
    "before_scored": 10, "after_scored": 12,
}


def test_kpi_tiles_labels_are_fail_not_pass():
    tiles = eval_comparison._kpi_tiles(_BASE_R)
    text = str(tiles)
    assert "Before FAIL" in text
    assert "After FAIL" in text
    assert "FAIL rate" in text
    assert "PASS" not in text


def test_kpi_tiles_values_are_fail_percentages():
    tiles = eval_comparison._kpi_tiles(_BASE_R)
    text = str(tiles)
    # before_fail = 1 - 0.5 = 50%; after_fail = 1 - 0.75 = 25%
    assert "50.0%" in text
    assert "25.0%" in text


def test_kpi_tiles_fail_delta_negates_pass_delta():
    # pass_delta = +25pp → fail_delta = -25pp
    tiles = eval_comparison._kpi_tiles(_BASE_R)
    text = str(tiles)
    assert "-25.0 pp" in text


def test_kpi_tiles_improvement_gets_success_valence():
    # fail rate drops (pass delta +25pp) → improvement → green left border
    tiles = eval_comparison._kpi_tiles(_BASE_R)
    assert tiles[2].style.get("borderLeftColor") == "var(--color-status-success)"


def test_kpi_tiles_regression_gets_error_valence():
    # fail rate rises (pass delta -25pp) → regression → red left border
    tiles = eval_comparison._kpi_tiles(_REGRESS_R)
    assert tiles[2].style.get("borderLeftColor") == "var(--color-status-error)"


def test_kpi_tiles_no_change_has_no_valence():
    flat = {**_BASE_R, "delta_pp": 0.0}
    tiles = eval_comparison._kpi_tiles(flat)
    assert not tiles[2].style
