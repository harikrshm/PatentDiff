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


def _layout_ids(node, acc=None):
    acc = set() if acc is None else acc
    node_id = getattr(node, "id", None)
    if isinstance(node_id, str):
        acc.add(node_id)
    children = getattr(node, "children", None)
    for child in children if isinstance(children, (list, tuple)) else [children]:
        if child is not None and not isinstance(child, (str, int, float)):
            _layout_ids(child, acc)
    return acc


def test_every_agent_callback_input_exists_in_static_layout():
    """Dash will not fire a callback when an Input id is absent from the layout.
    Keep/Revert once lived only inside render_stage, so Approve never worked."""
    from dash._callback import GLOBAL_CALLBACK_LIST
    from app_unified.pages.eval_agent import layout

    ids = _layout_ids(layout)
    missing = []
    for cb in GLOBAL_CALLBACK_LIST:
        if "agent-" not in cb["output"]:
            continue
        for inp in cb["inputs"]:
            if inp["id"].startswith("agent-") and inp["id"] not in ids:
                missing.append(inp["id"])
    assert not missing, f"callback Inputs missing from layout: {missing}"
