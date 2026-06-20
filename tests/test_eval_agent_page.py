# tests/test_eval_agent_page.py
"""Tests for the /eval/agent Dash page helpers.

Only covers the two PURE display functions (render_plan, render_stage) as
specified. No live Groq / network calls.
"""
import app_unified.app  # side-effect: registers all pages
from app_unified.pages.eval_agent import render_plan, render_stage
from core.experiment_agent import ExperimentPlan, ProposedExperiment


def test_render_plan_one_card_per_experiment():
    plan = ExperimentPlan(experiments=[
        ProposedExperiment(order=1, target_eval="citation",
                           target_segment="Method × Genus-species",
                           prompt_block="Quote verbatim.",
                           predicted_delta_pp=-30.0,
                           rationale="x", cited_run_ids=["m0"]),
        ProposedExperiment(order=2, target_eval="phosita",
                           target_segment="System × Overlapping",
                           prompt_block="Explain PSA.",
                           predicted_delta_pp=-15.0,
                           rationale="y", cited_run_ids=[]),
    ])
    cards = render_plan(plan)
    assert len(cards) == 2


def test_render_stage_smoke():
    from core.experiment_gate import GateResult
    from core.experiment_agent_runner import StageResult
    sr = StageResult(before=100.0, after=0.0, other_before=50.0, other_after=50.0,
                     gate=GateResult(passed=True, reasons=["[PASS] ..."]),
                     coverage="ran 8/8", new_block="b", after_verdicts={})
    comp = render_stage(sr)
    assert comp is not None
