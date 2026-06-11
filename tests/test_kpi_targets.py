# tests/test_kpi_targets.py
import pytest

from core.kpi_targets import Target, get_target, load_targets, set_target


def test_set_get_round_trip(tmp_path):
    p = tmp_path / "kpi.json"
    set_target("phosita", 0.85, "2026-09-01", path=p)
    t = get_target("phosita", path=p)
    assert isinstance(t, Target)
    assert t.target_pass_rate == 0.85 and t.target_date == "2026-09-01"
    assert t.baseline_run is None


def test_missing_file(tmp_path):
    assert load_targets(tmp_path / "nope.json") == {}
    assert get_target("phosita", path=tmp_path / "nope.json") is None


def test_set_validates_rate_and_date(tmp_path):
    p = tmp_path / "kpi.json"
    with pytest.raises(ValueError):
        set_target("phosita", 1.5, "2026-09-01", path=p)
    with pytest.raises(ValueError):
        set_target("phosita", 0.8, "not-a-date", path=p)


def test_set_upserts_without_clobbering_others(tmp_path):
    p = tmp_path / "kpi.json"
    set_target("phosita", 0.85, "2026-09-01", path=p)
    set_target("citation", 0.90, "2026-10-01", path=p)
    assert set(load_targets(p)) == {"phosita", "citation"}
