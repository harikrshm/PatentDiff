from pathlib import Path

from core.workbench_state import load_state, save_state


def test_load_state_missing_returns_default(tmp_path: Path):
    assert load_state(tmp_path, "priority_inputs") == {}


def test_save_then_load_round_trips(tmp_path: Path):
    data = {"impact": {"Absent PHOSITA": "High"}, "layers": {"Citation Text": "L1"}}
    save_state(tmp_path, "priority_inputs", data)
    assert load_state(tmp_path, "priority_inputs") == data


def test_save_creates_dir_if_absent(tmp_path: Path):
    target = tmp_path / "nested" / "state"
    save_state(target, "layout", {"a": 1})
    assert (target / "layout.json").exists()
    assert load_state(target, "layout") == {"a": 1}
