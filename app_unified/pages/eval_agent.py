# app_unified/pages/eval_agent.py
"""Experiment Agent — /eval/agent page.

AI-proposed experiment plan (via Groq) with a PM feedback loop and
sequential staged execution. Falls back to a cached demo plan whenever
GROQ_API_KEY is absent or the Groq call fails.

Data-loading path (replicates how the dashboard callbacks obtain their inputs):
  - df              : app_workbench.data.load("live")  (wraps core.workbench_data.load_merged)
  - impact_tiers    : app_workbench.state.get_priority_inputs("live")["impact"]
  - exposure_tiers  : same source, keys converted from "A × B" strings to (A, B) tuples
  - targets         : core.kpi_targets.get_target("phosita"/"citation") → pass rates
                      re-keyed to "absent_phosita_reasoning" / "citation_text" as
                      gather_context expects (see core/experiment_agent._EVAL_KIND)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import dash
from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from app_unified.components import page_header
from app_workbench.data import load as _load_df
from app_workbench.state import get_priority_inputs
from core import demo_mode
from core.experiment_agent import (
    AgentPlanError,
    ExperimentPlan,
    ProposedExperiment,
    gather_context,
    load_demo_plan,
    propose_plan,
)
from core.experiment_agent_runner import (
    StageResult,
    keep_stage,
    load_demo_stage_result,
    run_stage,
    select_subset,
)
from core.kpi_targets import get_target
from core.workbench_data import _iter_jsonl

dash.register_page(__name__, path="/eval/agent", name="Experiment Agent")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIR = REPO_ROOT / "traces"
TRACES_FILE = TRACES_DIR / "traces.jsonl"


# ---------------------------------------------------------------------------
# Data helpers (used inside background callbacks at call time, never at import)
# ---------------------------------------------------------------------------

def _build_analysis_inputs():
    """Return (df, impact_tiers, exposure_tiers, targets) for the live set.

    Replicates the data-loading path that dashboard callbacks use:
      - df           via app_workbench.data.load("live")
      - impact/exposure via app_workbench.state.get_priority_inputs("live")
      - targets      via core.kpi_targets.get_target
    """
    df = _load_df("live")

    pri = get_priority_inputs("live")
    impact_tiers: dict[str, str] = pri.get("impact") or {}

    # Exposure might be stored with string keys ("A × B") if the UI wrote them.
    # priority_table expects tuple keys; convert any strings here.
    raw_exposure: dict = pri.get("exposure") or {}
    exposure_tiers: dict[tuple[str, str], str] = {}
    for k, v in raw_exposure.items():
        if isinstance(k, tuple):
            exposure_tiers[k] = v
        elif isinstance(k, str) and "×" in k:
            parts = k.split("×", 1)
            exposure_tiers[(parts[0].strip(), parts[1].strip())] = v

    # gather_context expects keys "absent_phosita_reasoning" / "citation_text" (see
    # experiment_agent._EVAL_KIND), with values as PASS rates (0..1).
    targets: dict[str, float] = {}
    t = get_target("phosita")
    if t:
        targets["absent_phosita_reasoning"] = t.target_pass_rate
    t = get_target("citation")
    if t:
        targets["citation_text"] = t.target_pass_rate

    return df, impact_tiers, exposure_tiers, targets


def _load_traces_by_ids(run_ids: list[str]) -> list[dict]:
    """Load raw trace dicts from traces.jsonl for the given run_ids."""
    all_traces = {
        t["run_id"]: t
        for t in _iter_jsonl(TRACES_FILE)
        if "run_id" in t
    }
    return [all_traces[rid] for rid in run_ids if rid in all_traces]


def _build_before_verdicts(df) -> dict[str, dict[str, str]]:
    """Build before_verdicts dict expected by run_stage from the live df."""
    result: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        rid = str(row["run_id"])
        result[rid] = {
            "citation": row.get("citation_verdict") or "NO_SCORE",
            "phosita": row.get("phosita_verdict") or "NO_SCORE",
        }
    return result


def _build_cell_of(df) -> dict[str, str]:
    """Map run_id → 'claim_type × relationship' from the live df."""
    return {
        str(row["run_id"]): f"{row['claim_type']} × {row['relationship']}"
        for _, row in df.iterrows()
    }


def _serialize_stage_result(sr: StageResult) -> dict:
    return {
        "before": sr.before,
        "after": sr.after,
        "other_before": sr.other_before,
        "other_after": sr.other_after,
        "gate_passed": sr.gate.passed,
        "gate_reasons": sr.gate.reasons,
        "coverage": sr.coverage,
        "new_block": sr.new_block,
        "after_verdicts": sr.after_verdicts,
    }


def _write_stage_eval_files(exp_id: str, after_verdicts: dict) -> tuple[str, str]:
    """Write phosita and citation eval JSONL files from after_verdicts.

    Returns (phosita_filename, citation_filename) — plain filenames, not full paths.
    """
    from core.phosita_eval import PROMPT_VERSION as _PHOSITA_PV

    phosita_name = f"phosita_eval_full.{exp_id}.jsonl"
    citation_name = f"citation_text_eval_full.{exp_id}.jsonl"

    with open(TRACES_DIR / phosita_name, "w", encoding="utf-8") as fp:
        for rid, vdict in after_verdicts.items():
            fp.write(json.dumps({
                "run_id": rid,
                "verdict": vdict.get("phosita", "NO_SCORE"),
                "config": {"prompt_version": _PHOSITA_PV},
            }) + "\n")

    with open(TRACES_DIR / citation_name, "w", encoding="utf-8") as fc:
        for rid, vdict in after_verdicts.items():
            fc.write(json.dumps({
                "run_id": rid,
                "verdict": vdict.get("citation", "NO_SCORE"),
            }) + "\n")

    return phosita_name, citation_name


# ---------------------------------------------------------------------------
# Pure display helpers (tested directly in tests/test_eval_agent_page.py)
# ---------------------------------------------------------------------------

def render_plan(plan: ExperimentPlan) -> list:
    """One card per experiment in the plan.

    Each card shows: order, target_eval, target_segment, rationale,
    the prompt_block (in a <pre>), and predicted_delta with a note that
    this is a PREDICTION — the measured gate result decides.
    """
    cards = []
    for exp in plan.experiments:
        delta_sign = "−" if exp.predicted_delta_pp <= 0 else "+"
        cards.append(
            html.Section(
                className="uw-agent__exp-card",
                children=[
                    html.Div(className="uw-agent__exp-head", children=[
                        html.Span(f"#{exp.order}", className="wb-kicker"),
                        html.Span(
                            f"{exp.target_eval.upper()}  ·  {exp.target_segment}",
                            className="uw-agent__exp-target wb-mono",
                        ),
                        html.Span(
                            f"Predicted {delta_sign}{abs(exp.predicted_delta_pp):.1f} pp {exp.target_eval} FAIL",
                            className="uw-agent__exp-delta wb-caption",
                            title="This is a PREDICTION. The measured gate result decides.",
                        ),
                    ]),
                    html.P(exp.rationale, className="uw-agent__exp-rationale"),
                    html.Pre(exp.prompt_block, className="uw-agent__exp-block wb-mono"),
                    html.P(
                        "Note: predicted delta is an estimate — the gate measures the actual result.",
                        className="wb-caption uw-agent__exp-note",
                    ),
                ],
            )
        )
    return cards


def render_stage(result: StageResult, recorded: bool = False) -> html.Div:
    """Gate PASS/FAIL card for a completed stage.

    Shows: gate status, coverage (with low-n warning), target eval before→after,
    gate.reasons list, and Keep / Revert buttons. `recorded` labels a result that
    comes from the demo cache rather than a fresh run.
    """
    gate_ok = result.gate.passed
    gate_cls = "uw-agent__gate--pass" if gate_ok else "uw-agent__gate--fail"
    gate_label = "PASS" if gate_ok else "FAIL"

    # Parse coverage to detect low-n (e.g., "ran 2/8" → n=2)
    ran_n = 0
    try:
        ran_n = int(result.coverage.split("/")[0].replace("ran", "").strip())
    except (ValueError, IndexError):
        pass
    low_n_note = (
        html.P("⚠ Low n — results may be unreliable (< 5 traces).",
               className="wb-caption uw-agent__low-n")
        if ran_n > 0 and ran_n < 5 else None
    )

    reasons_list = html.Ul(
        className="uw-agent__reasons",
        children=[html.Li(r, className="wb-mono uw-agent__reason") for r in result.gate.reasons],
    )

    return html.Div(
        className="uw-agent__stage-result",
        children=[
            html.Div(className=f"uw-agent__gate {gate_cls}", children=[
                html.Span("Gate", className="wb-kicker"),
                html.Span(gate_label, className="uw-agent__gate-label"),
            ]),
            html.P(
                f"Coverage: {result.coverage}"
                + (" · recorded run, not recomputed" if recorded else ""),
                className="wb-caption uw-agent__coverage",
            ),
            *([low_n_note] if low_n_note else []),
            html.Div(className="uw-agent__deltas", children=[
                html.Span(
                    f"Target: {result.before:.1f}% → {result.after:.1f}% FAIL",
                    className="wb-mono",
                ),
                html.Span(
                    f"Other eval: {result.other_before:.1f}% → {result.other_after:.1f}% FAIL",
                    className="wb-mono uw-agent__other",
                ),
            ]),
            reasons_list,
        ],
    )


def _complete_view(demo: bool = False) -> html.Div:
    """Shown when all staged experiments have been processed."""
    body = (
        "The demo records stage 1 only. Stages 2 and 3 need a live run with a Groq key. "
        "Open the Comparison tab to see recorded experiments."
        if demo else
        "All stages have been kept or reverted. "
        "Open the Comparison tab to see the recorded results."
    )
    return html.Div(
        className="uw-agent__complete",
        children=[
            html.P("Demo ends here." if demo else "Plan complete.",
                   className="uw-agent__complete-title"),
            html.P(body, className="wb-caption"),
            dcc.Link("Open Comparison →", href="/eval/comparison",
                     className="wb-btn wb-btn--secondary"),
        ],
    )


def _demo_banner() -> html.Div:
    text = (
        "Demo: this plan was recorded from a live run. Live model calls are off here."
        if demo_mode.DEMO_MODE else
        "Showing the recorded plan. No Groq access "
        "(GROQ_API_KEY is not set, or Groq returned an error)."
    )
    return html.Div(
        className="uw-agent__banner uw-agent__banner--demo",
        children=html.P(text, className="wb-caption"),
    )


_EMPTY_PLAN = html.Div(
    className="uw-compare__empty",
    children=[
        html.P("No plan yet", className="uw-compare__empty-title"),
        html.P("Analyze reads the live dashboard and proposes up to three experiments.",
               className="uw-compare__empty-hint"),
    ],
)


# ---------------------------------------------------------------------------
# Layout (module-level, read by Dash's page system)
# ---------------------------------------------------------------------------

layout = html.Div(
    className="uw-page uw-page--instrument uw-agent",
    children=[
        page_header(
            "Experiment Agent",
            "Reads the dashboard, proposes up to three prompt experiments, and runs them one at a time. You keep or revert each.",
        ),

        html.Div(className="uw-agent__row", children=[
            html.Button(
                "Analyze", id="agent-analyze-btn", n_clicks=0,
                className="wb-btn wb-btn--primary uw-agent__analyze",
            ),
            html.Span(
                id="agent-analyze-status", className="wb-controlbar__status",
                role="status", **{"aria-live": "polite"},
            ),
        ]),

        html.Div(id="agent-banner"),

        html.Div(id="agent-plan-area", className="uw-agent__plan-area", children=_EMPTY_PLAN),

        html.Div(className="uw-agent__review", children=[
            html.Div(className="uw-agent__feedback-row", children=[
                html.Label("PM feedback", htmlFor="agent-feedback", className="uw-label"),
                dcc.Textarea(
                    id="agent-feedback", value="",
                    placeholder="e.g. Focus on System claims. Leave PHOSITA alone.",
                    className="uw-input--area uw-agent__textarea",
                ),
                html.Div(className="uw-agent__row", children=[
                    html.Button(
                        "Revise plan", id="agent-revise-btn", n_clicks=0,
                        className="wb-btn wb-btn--secondary",
                    ),
                ]),
            ]),
            html.Div(className="uw-agent__row uw-agent__approve-row", children=[
                html.Button(
                    "Approve plan and start", id="agent-approve-btn", n_clicks=0,
                    className="wb-btn wb-btn--primary",
                ),
                html.Span(
                    id="agent-stage-status", className="wb-controlbar__status",
                    role="status", **{"aria-live": "polite"},
                ),
            ]),
        ]),

        html.Div(id="agent-stage-area", className="uw-agent__stage-area"),

        # Static (not rendered per stage): Dash won't fire _stage_control if any
        # of its Inputs is missing from the layout. CSS shows them with a result.
        html.Div(className="uw-agent__action-row uw-agent__stage-actions", children=[
            html.Button(
                "Keep change", id="agent-stage-keep-btn", n_clicks=0,
                className="wb-btn wb-btn--primary",
            ),
            html.Button(
                "Revert change", id="agent-stage-revert-btn", n_clicks=0,
                className="wb-btn wb-btn--secondary",
            ),
        ]),

        html.Div(
            className="uw-agent__footer",
            children=[
                dcc.Link(
                    "See results in Comparison →",
                    href="/eval/comparison",
                    className="uw-agent__link",
                ),
            ],
        ),

        dcc.Store(id="agent-plan"),
        dcc.Store(id="agent-stage-idx", data=0),
        dcc.Store(id="agent-kept-block", data=""),
        dcc.Store(id="agent-stage-trigger", data=None),
        dcc.Store(id="agent-stage-result"),
    ],
)


# ---------------------------------------------------------------------------
# Callback 1 — Analyze / Revise (background; calls Groq)
# ---------------------------------------------------------------------------

@callback(
    Output("agent-plan", "data"),
    Output("agent-banner", "children"),
    Output("agent-plan-area", "children"),
    Input("agent-analyze-btn", "n_clicks"),
    Input("agent-revise-btn", "n_clicks"),
    State("agent-feedback", "value"),
    background=True,
    running=[
        (Output("agent-analyze-btn", "disabled"), True, False),
        (Output("agent-revise-btn", "disabled"), True, False),
        (Output("agent-analyze-btn", "children"), "Analyzing…", "Analyze"),
    ],
    progress=[Output("agent-analyze-status", "children")],
    prevent_initial_call=True,
)
def _analyze_or_revise(set_progress, n_analyze, n_revise, feedback):
    """Build context from the live dashboard data and propose a plan via Groq.

    Falls back to load_demo_plan() on any API error or missing key, and shows
    a visible banner so the PM knows the plan is cached.
    """
    if not (n_analyze or n_revise):
        return no_update, no_update, no_update

    triggered = ctx.triggered_id
    # Pass PM feedback only when explicitly revising
    pm_feedback = (feedback or "").strip() or None
    if triggered == "agent-analyze-btn":
        pm_feedback = None

    set_progress(["Gathering context…"])
    try:
        df, impact_tiers, exposure_tiers, targets = _build_analysis_inputs()
        context = gather_context(df, impact_tiers, exposure_tiers, targets)
    except Exception:
        # Even context-building can fail (e.g., empty trace set). Fall back.
        set_progress(["Loading cached plan…"])
        plan = load_demo_plan()
        return plan.model_dump(), _demo_banner(), render_plan(plan)

    use_demo = False
    if demo_mode.DEMO_MODE or not os.environ.get("GROQ_API_KEY"):
        use_demo = True
    else:
        set_progress(["Proposing plan via Groq…"])
        try:
            plan = propose_plan(context, pm_feedback=pm_feedback)
        except (AgentPlanError, Exception):
            use_demo = True

    if use_demo:
        set_progress(["Loading cached plan…"])
        plan = load_demo_plan()
        banner = _demo_banner()
    else:
        banner = None

    set_progress(["Done."])
    return plan.model_dump(), banner, render_plan(plan)


# ---------------------------------------------------------------------------
# Callback 2 — Stage control (regular; fast; writes state, triggers stage runner)
# ---------------------------------------------------------------------------

@callback(
    Output("agent-stage-idx", "data"),
    Output("agent-kept-block", "data"),
    Output("agent-stage-trigger", "data"),
    Input("agent-approve-btn", "n_clicks"),
    Input("agent-stage-keep-btn", "n_clicks"),
    Input("agent-stage-revert-btn", "n_clicks"),
    State("agent-stage-result", "data"),
    State("agent-stage-idx", "data"),
    State("agent-kept-block", "data"),
    State("agent-plan", "data"),
    prevent_initial_call=True,
)
def _stage_control(n_approve, n_keep, n_revert,
                   result_data, stage_idx, kept_block, plan_data):
    """Advance the stage pipeline on Approve / Keep / Revert.

    - Approve   → reset stage_idx to 0 and fire the stage runner.
    - Keep      → write eval files, call keep_stage, advance stage_idx with new block.
    - Revert    → advance stage_idx keeping the existing block.
    """
    # Guard against spurious fires when buttons are first rendered with n_clicks=0
    if (n_approve or 0) == 0 and (n_keep or 0) == 0 and (n_revert or 0) == 0:
        return no_update, no_update, no_update

    triggered = ctx.triggered_id
    idx = stage_idx or 0
    block = kept_block or ""

    if triggered == "agent-approve-btn":
        # Start from stage 0 with the current (possibly empty) kept block.
        return 0, block, time.time()

    if triggered == "agent-stage-keep-btn":
        if result_data:
            new_block = result_data.get("new_block", block)
            # Write eval files + record in the experiments manifest
            after_verdicts = result_data.get("after_verdicts") or {}
            if after_verdicts:
                try:
                    exp_id = f"agent-{uuid.uuid4().hex[:8]}"
                    # Derive a human-readable name from the current experiment
                    exp_name = exp_id
                    if plan_data:
                        plan = ExperimentPlan.model_validate(plan_data)
                        if idx < len(plan.experiments):
                            exp = plan.experiments[idx]
                            slug = exp.prompt_block[:40].replace("\n", " ").strip()
                            exp_name = f"Agent: {slug} ({exp.target_segment})"
                    ph_file, ct_file = _write_stage_eval_files(exp_id, after_verdicts)
                    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    keep_stage(
                        exp_id=exp_id,
                        name=exp_name,
                        created=created,
                        phosita_eval_file=ph_file,
                        citation_eval_file=ct_file,
                    )
                except Exception:
                    pass  # keep_stage failure is non-fatal for the UI flow
        else:
            new_block = block
        return idx + 1, new_block, time.time()

    if triggered == "agent-stage-revert-btn":
        return idx + 1, block, time.time()

    return no_update, no_update, no_update


# ---------------------------------------------------------------------------
# Callback 3 — Stage runner (background; calls Groq for regen + phosita scoring)
# ---------------------------------------------------------------------------

@callback(
    Output("agent-stage-area", "children"),
    Output("agent-stage-result", "data"),
    Input("agent-stage-trigger", "data"),
    State("agent-plan", "data"),
    State("agent-stage-idx", "data"),
    State("agent-kept-block", "data"),
    background=True,
    running=[
        (Output("agent-stage-status", "children"), "Running stage…", ""),
    ],
    prevent_initial_call=True,
)
def _run_current_stage(trigger, plan_data, stage_idx, kept_block):
    """Execute one experiment stage: select subset → regenerate → score → gate.

    Concerns (see DONE_WITH_CONCERNS report):
      - judge_client is a live Groq() client; requires GROQ_API_KEY.
      - before_verdicts and cell_of are built from the live "live" set at run time.
      - trace dicts are loaded from traces/traces.jsonl.
    """
    if trigger is None or plan_data is None:
        return no_update, no_update

    plan = ExperimentPlan.model_validate(plan_data)
    idx = stage_idx or 0

    if idx >= len(plan.experiments):
        return _complete_view(), no_update

    proposed = plan.experiments[idx]

    if demo_mode.DEMO_MODE:
        recorded = load_demo_stage_result() if idx == 0 else None
        if recorded is None:
            return _complete_view(demo=True), None
        return render_stage(recorded, recorded=True), _serialize_stage_result(recorded)

    try:
        from groq import Groq
        judge_client = Groq()

        df, _, _, _ = _build_analysis_inputs()
        before_verdicts = _build_before_verdicts(df)
        cell_of = _build_cell_of(df)

        run_ids = select_subset(df, proposed.target_segment, cap=8, guardrail=2)
        if not run_ids:
            return html.Div(
                className="uw-agent__stage-error",
                children=html.P(
                    f"No traces found for segment '{proposed.target_segment}'. "
                    "Skipping this stage — click Reject (REVERT) to advance.",
                    className="wb-caption",
                ),
            ), None

        subset_traces = _load_traces_by_ids(run_ids)

        result = run_stage(
            proposed,
            kept_block=kept_block or "",
            subset_traces=subset_traces,
            before_verdicts=before_verdicts,
            judge_client=judge_client,
            cell_of=cell_of,
        )
    except Exception as exc:
        return html.Div(
            className="uw-agent__stage-error",
            children=html.P(
                f"Stage failed: {exc}. Check GROQ_API_KEY and trace files.",
                className="wb-caption",
            ),
        ), None

    return render_stage(result), _serialize_stage_result(result)
