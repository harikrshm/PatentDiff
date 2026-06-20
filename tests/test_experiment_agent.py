import pytest
import pandas as pd
from pydantic import ValidationError

from core.experiment_agent import ProposedExperiment, ExperimentPlan, gather_context, AgentContext


def _exp(**kw):
    base = dict(order=1, target_eval="citation", target_segment="Method × Genus-species",
                prompt_block="Quote verbatim.", predicted_delta_pp=-20.0,
                rationale="paraphrasing observed", cited_run_ids=["r1", "r2"])
    base.update(kw)
    return base


def test_proposed_experiment_valid():
    e = ProposedExperiment(**_exp())
    assert e.order == 1
    assert e.target_eval == "citation"


def test_proposed_experiment_rejects_bad_eval():
    with pytest.raises(ValidationError):
        ProposedExperiment(**_exp(target_eval="not_a_real_eval"))


def test_experiment_plan_orders_experiments():
    plan = ExperimentPlan(experiments=[ProposedExperiment(**_exp(order=1)),
                                       ProposedExperiment(**_exp(order=2))])
    assert [e.order for e in plan.experiments] == [1, 2]


# ---------------------------------------------------------------------------
# Task 4: gather_context
# ---------------------------------------------------------------------------

def _frame():
    rows = []
    for i in range(3):
        rows.append(dict(run_id=f"m{i}", claim_type="Method", claim_length="Long",
                         relationship="Genus-species", dim_source="human",
                         phosita_verdict="PASS", citation_verdict="FAIL"))
    for i in range(2):
        rows.append(dict(run_id=f"s{i}", claim_type="System", claim_length="Short",
                         relationship="Overlapping", dim_source="human",
                         phosita_verdict="PASS", citation_verdict="PASS"))
    return pd.DataFrame(rows)


def test_gather_context_picks_top_cell_and_examples():
    ctx = gather_context(
        _frame(),
        impact_tiers={"Citation Text": "High", "Absent PHOSITA": "Med"},
        exposure_tiers={},
        targets={"citation_text": 0.95},
    )
    assert isinstance(ctx, AgentContext)
    top = ctx.priority_rows[0]
    assert top["failure_mode"] == "Citation Text"
    assert top["cell"] == "Method × Genus-species"
    assert ctx.kpi_gaps["citation_text"] == pytest.approx(55.0, abs=1.0)
    assert set(ctx.examples["Citation Text"]).issubset({"m0", "m1", "m2"})
    assert len(ctx.examples["Citation Text"]) <= 3
