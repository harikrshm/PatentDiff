import pandas as pd

from core.experiment_agent_runner import select_subset


def _frame():
    rows = []
    for i in range(5):
        rows.append(dict(run_id=f"m{i}", claim_type="Method", relationship="Genus-species"))
    for i in range(5):
        rows.append(dict(run_id=f"o{i}", claim_type="System", relationship="Overlapping"))
    return pd.DataFrame(rows)


def test_select_subset_targets_segment_plus_guardrail():
    ids = select_subset(_frame(), segment="Method × Genus-species", cap=8, guardrail=2)
    assert {"m0", "m1", "m2", "m3", "m4"}.issubset(set(ids))
    assert len(ids) <= 8
    assert any(i.startswith("o") for i in ids)


def test_select_subset_unknown_segment_returns_empty():
    assert select_subset(_frame(), segment="No × Such") == []
