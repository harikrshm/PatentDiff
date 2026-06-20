"""The Experiment Agent brain: turns the live dashboard data into a ranked plan
of experiments. Deterministic targeting (gather_context) + an LLM-authored plan
(propose_plan). No Dash; the only live IO is the single Groq call in propose_plan."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from core.llm import call_groq
from core.priority import priority_table, MODE_VERDICT

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_CACHE_PATH = REPO_ROOT / "traces" / "agent_demo_cache.json"


# ---------------------------------------------------------------------------
# Data models (Task 3)
# ---------------------------------------------------------------------------

class ProposedExperiment(BaseModel):
    order: int
    target_eval: Literal["citation", "phosita"]
    target_segment: str
    prompt_block: str
    predicted_delta_pp: float
    rationale: str
    cited_run_ids: list[str] = Field(default_factory=list)


class ExperimentPlan(BaseModel):
    experiments: list[ProposedExperiment]


# ---------------------------------------------------------------------------
# AgentContext + gather_context (Task 4)
# ---------------------------------------------------------------------------

class AgentContext(BaseModel):
    priority_rows: list[dict]
    kpi_gaps: dict[str, float]
    examples: dict[str, list[str]]


_EVAL_KIND = {"Citation Text": "citation_text", "Absent PHOSITA": "absent_phosita_reasoning"}


def gather_context(
    df: pd.DataFrame,
    impact_tiers: dict[str, str],
    exposure_tiers: dict[tuple[str, str], str],
    targets: dict[str, float],
    top_k: int = 5,
) -> AgentContext:
    table = priority_table(df, impact_tiers, exposure_tiers)
    priority_rows = [] if table.empty else table.head(top_k).to_dict("records")

    kpi_gaps: dict[str, float] = {}
    examples: dict[str, list[str]] = {}
    for mode, col in MODE_VERDICT.items():
        scored = df[df[col].isin(["PASS", "FAIL"])]
        if len(scored):
            current_fail = float((scored[col] == "FAIL").mean()) * 100.0
            kind = _EVAL_KIND[mode]
            target_fail = (1.0 - targets[kind]) * 100.0 if kind in targets else 0.0
            kpi_gaps[kind] = round(current_fail - target_fail, 1)

    for row in priority_rows:
        mode = row["failure_mode"]
        if mode in examples:
            continue
        col = MODE_VERDICT[mode]
        cell_df = df[
            (df["claim_type"] == row["claim_type"])
            & (df["relationship"] == row["relationship"])
            & (df[col] == "FAIL")
        ]
        examples[mode] = list(cell_df["run_id"].head(3))

    return AgentContext(priority_rows=priority_rows, kpi_gaps=kpi_gaps, examples=examples)


# ---------------------------------------------------------------------------
# propose_plan + demo-cache fallback (Task 5)
# ---------------------------------------------------------------------------

class AgentPlanError(RuntimeError):
    """The agent could not produce a valid plan (bad/unparseable LLM output)."""


def _build_agent_prompt(context: AgentContext, pm_feedback: Optional[str]) -> tuple[str, str]:
    system = (
        "You are a senior AI product manager improving an LLM patent-analysis tool. "
        "You are given the tool's current failure data. Propose a ranked sequence of "
        "up to 3 experiments. Each experiment targets ONE eval ('citation' or 'phosita') "
        "and proposes ONE instruction block to APPEND to the tool's system prompt. "
        "Return ONLY JSON matching: {\"experiments\": [{\"order\": int, "
        "\"target_eval\": \"citation\"|\"phosita\", \"target_segment\": str, "
        "\"prompt_block\": str, \"predicted_delta_pp\": float (negative = fewer failures), "
        "\"rationale\": str, \"cited_run_ids\": [str]}]}. No markdown, no prose."
    )
    user = (
        f"PRIORITY CELLS (highest leverage first):\n{json.dumps(context.priority_rows, indent=2)}\n\n"
        f"KPI GAPS (current FAIL% minus target FAIL%):\n{json.dumps(context.kpi_gaps, indent=2)}\n\n"
        f"EXAMPLE FAILING TRACES per mode:\n{json.dumps(context.examples, indent=2)}"
    )
    if pm_feedback:
        user += f"\n\nPM FEEDBACK — revise the plan accordingly:\n{pm_feedback}"
    return system, user


def _parse_plan(raw: str) -> ExperimentPlan:
    return ExperimentPlan.model_validate_json(raw)


def propose_plan(context: AgentContext, pm_feedback: Optional[str] = None) -> ExperimentPlan:
    system, user = _build_agent_prompt(context, pm_feedback)
    last_err: Optional[Exception] = None
    for attempt in range(2):
        resp = call_groq(system, user)
        raw = (resp or {}).get("raw_output", "")
        try:
            return _parse_plan(raw)
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = e
            user = user + "\n\nYour previous output was not valid JSON. Return ONLY the JSON object."
    raise AgentPlanError(f"Could not parse a plan after 2 attempts: {last_err}")


def load_demo_plan(path: Path = DEMO_CACHE_PATH) -> ExperimentPlan:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ExperimentPlan.model_validate(data["plan"])
