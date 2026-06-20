import pytest
from pydantic import ValidationError

from core.experiment_agent import ProposedExperiment, ExperimentPlan


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
