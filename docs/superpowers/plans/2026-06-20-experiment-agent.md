# Experiment Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an "Experiment Agent" workbench tab that reads the live evaluation dashboard, proposes a ranked sequence of ~3 experiments, runs them one at a time on a subset under human KEEP/REVERT gates (cumulative baselines), and surfaces results in the existing Comparison tab.

**Architecture:** Pure, testable logic in two new `core/` modules (`experiment_agent.py` = the brain, `experiment_agent_runner.py` = the staged executor) plus a small reusable `core/regeneration.py`. A thin Dash page (`app_unified/pages/eval_agent.py`) delegates to them and runs the slow LLM/regeneration work in diskcache background callbacks. The one runnable lever is an appended system-prompt instruction block, threaded through a new `extra_instructions` param on `core.llm.build_system_prompt`. Results are appended to `traces/experiments.jsonl` for the Comparison tab.

**Tech Stack:** Python 3.13, Pydantic 2, pandas, Dash 2.18 (multi-page + diskcache background callbacks), Groq API (mocked in all tests), pytest.

**Spec:** `docs/superpowers/specs/2026-06-20-experiment-agent-design.md`

**Conventions reminder:** run the app with `python -m app_unified.app`; run tests with `python -m pytest` (bare `pytest` is not on PATH on this Windows env). All new tests MUST mock the network — no live Groq calls.

---

## File Structure

**New files**
- `core/regeneration.py` — `regenerate_one(trace, system_prompt)` extracted from the script (one model call per trace → trace dict). Canonical home so both the script and the runner share it.
- `core/experiment_agent.py` — models (`ProposedExperiment`, `ExperimentPlan`, `AgentContext`), `gather_context`, `propose_plan`, `load_demo_plan`.
- `core/experiment_agent_runner.py` — `select_subset`, `run_stage` (returns `StageResult`), `keep_stage` (manifest append).
- `app_unified/pages/eval_agent.py` — the `/eval/agent` page (layout + callbacks delegating to core).
- `traces/agent_demo_cache.json` — one curated known-good plan + one `StageResult` for offline demo.
- `tests/test_regeneration.py`, `tests/test_experiment_agent.py`, `tests/test_experiment_agent_runner.py`.

**Modified files**
- `core/llm.py` — add `extra_instructions: str = ""` to `build_system_prompt` (default-compatible).
- `scripts/regenerate_traces.py` — import `regenerate_one` from `core.regeneration` (DRY) instead of defining it.
- `app_unified/pages/eval_overview.py` — add a "→ Ask the agent" link to `/eval/agent` near the priority table.

---

## Task 1: Add `extra_instructions` to `build_system_prompt`

**Files:**
- Modify: `core/llm.py:20-63`
- Test: `tests/test_llm_extra_instructions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_extra_instructions.py
from core.llm import build_system_prompt


def test_default_is_unchanged():
    # Guards every existing caller/test: default must be byte-identical to today.
    base = build_system_prompt()
    assert base == build_system_prompt(extra_instructions="")
    assert base.startswith("You are an expert patent analyst.")


def test_extra_instructions_appended():
    block = "EXTRA RULE: always quote verbatim."
    out = build_system_prompt(extra_instructions=block)
    assert out.startswith(build_system_prompt())
    assert out.endswith(block)
    assert "\n\n" + block in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_llm_extra_instructions.py -v`
Expected: FAIL — `build_system_prompt() takes 0 positional arguments` / unexpected keyword `extra_instructions`.

- [ ] **Step 3: Write minimal implementation**

In `core/llm.py`, change the signature and return. The existing body builds a constant string; capture it as `base` and append.

```python
def build_system_prompt(extra_instructions: str = "") -> str:
    base = """You are an expert patent analyst. ...EXISTING UNCHANGED BODY... }"""
    if not extra_instructions:
        return base
    return base + "\n\n" + extra_instructions
```

(Keep the existing multi-line string exactly as-is as `base`; only wrap the return.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_llm_extra_instructions.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/llm.py tests/test_llm_extra_instructions.py
git commit -m "feat(llm): optional extra_instructions block on build_system_prompt"
```

---

## Task 2: Extract `regenerate_one` into `core/regeneration.py`

**Files:**
- Create: `core/regeneration.py`
- Modify: `scripts/regenerate_traces.py:28-68` (import instead of define)
- Test: `tests/test_regeneration.py`

- [ ] **Step 1: Write the failing test** (stubs `call_groq` — no network)

```python
# tests/test_regeneration.py
import core.regeneration as regen


_TRACE = {
    "run_id": "abc123",
    "inputs": {
        "source_patent": {"label": "A", "independent_claim": "a claim", "specification": "spec a"},
        "target_patent": {"label": "B", "independent_claim": "b claim", "specification": "spec b"},
    },
}

_GROQ_OK = {
    "raw_output": '{"element_mappings": [{"element_number": 1, "element_text": "x", '
                  '"corresponding_text": "y", "novelty": "N", "inventive_step": "N", '
                  '"verdict": "N", "comment": "c"}], "overall_opinion": "ok"}',
    "model": "stub", "tokens_input": 1, "tokens_output": 1, "latency_ms": 5,
}


def test_regenerate_one_uses_given_system_prompt(monkeypatch):
    captured = {}

    def fake_call_groq(system_prompt, user_prompt, model=None):
        captured["system"] = system_prompt
        return _GROQ_OK

    monkeypatch.setattr(regen, "call_groq", fake_call_groq)
    out = regen.regenerate_one(_TRACE, "SYSTEM PROMPT WITH BLOCK")

    assert captured["system"] == "SYSTEM PROMPT WITH BLOCK"
    assert out["run_id"] == "abc123"
    assert out["status"] == "ok"
    assert out["parsed_output"]["overall_opinion"] == "ok"
    assert out["prompt"]["system_prompt"] == "SYSTEM PROMPT WITH BLOCK"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_regeneration.py -v`
Expected: FAIL — `No module named 'core.regeneration'`.

- [ ] **Step 3: Write minimal implementation**

Move the body of `scripts/regenerate_traces.regenerate_one` verbatim into the new module:

```python
# core/regeneration.py
"""Single-trace regeneration: re-run the model under test for one trace dict
with a given system prompt. Extracted from scripts/regenerate_traces so the
Experiment Agent runner and the CLI share one implementation."""
from __future__ import annotations

from datetime import datetime, timezone

from core.llm import build_user_prompt, call_groq
from core.models import PatentInput
from core.report import parse_llm_response


def regenerate_one(trace: dict, system_prompt: str) -> dict:
    inputs = trace["inputs"]
    source = PatentInput(**inputs["source_patent"])
    target = PatentInput(**inputs["target_patent"])
    user_prompt, truncation_warnings = build_user_prompt(source, target)

    parsed_dump = None
    status = "ok"
    error = None
    llm_response = {"raw_output": "", "model": "", "tokens_input": 0,
                    "tokens_output": 0, "latency_ms": 0}
    try:
        llm_response = call_groq(system_prompt, user_prompt)
        try:
            parsed = parse_llm_response(llm_response["raw_output"])
            parsed_dump = parsed.model_dump()
        except ValueError as parse_err:
            status = "parse_error"
            error = str(parse_err)
    except Exception as api_err:
        status = "api_error"
        error = str(api_err)

    return {
        "run_id": trace["run_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": inputs,
        "prompt": {"system_prompt": system_prompt, "user_prompt": user_prompt},
        "llm_response": llm_response,
        "parsed_output": parsed_dump,
        "status": status,
        "error": error,
        "truncation_warnings": truncation_warnings,
    }
```

Then in `scripts/regenerate_traces.py`, delete the local `regenerate_one` (lines 36-68) and its now-unused imports of `PatentInput`/`parse_llm_response`/`datetime`, and add:

```python
from core.regeneration import regenerate_one
```

(Keep `build_system_prompt`, `build_user_prompt`, `call_groq` imports only if still referenced — `build_system_prompt` is still used in `main`; `build_user_prompt`/`call_groq` are now only used inside `core.regeneration`, so remove them from the script import.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_regeneration.py tests/ -k "regenerat" -v`
Expected: PASS. Then run the full suite to confirm the script refactor didn't break existing tests: `python -m pytest -q` → all green.

- [ ] **Step 5: Commit**

```bash
git add core/regeneration.py scripts/regenerate_traces.py tests/test_regeneration.py
git commit -m "refactor: extract regenerate_one into core.regeneration (shared by CLI + agent)"
```

---

## Task 3: Agent data models

**Files:**
- Create: `core/experiment_agent.py` (models only for now)
- Test: `tests/test_experiment_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_experiment_agent.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_experiment_agent.py -v`
Expected: FAIL — `No module named 'core.experiment_agent'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/experiment_agent.py
"""The Experiment Agent brain: turns the live dashboard data into a ranked plan
of experiments. Deterministic targeting (gather_context) + an LLM-authored plan
(propose_plan). No Dash; the only live IO is the single Groq call in propose_plan."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[1]


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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_experiment_agent.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/experiment_agent.py tests/test_experiment_agent.py
git commit -m "feat(agent): ProposedExperiment + ExperimentPlan models"
```

---

## Task 4: `gather_context` — deterministic targeting

**Files:**
- Modify: `core/experiment_agent.py`
- Test: `tests/test_experiment_agent.py`

`AgentContext` carries the real numbers the agent reasons over. It is built from a merged dashboard frame (columns per `core.workbench_data.load_merged`: `run_id, claim_type, claim_length, relationship, dim_source, phosita_verdict, citation_verdict`), PM-supplied impact/exposure tiers (same inputs `core.priority.priority_table` already takes), and KPI targets.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_experiment_agent.py
import pandas as pd
from core.experiment_agent import gather_context, AgentContext


def _frame():
    # Method × Genus-species cell: 3 citation FAILs out of 3 -> 100% fail (top priority)
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
        exposure_tiers={},                       # default Med per cell
        targets={"citation_text": 0.95},         # target PASS rate
    )
    assert isinstance(ctx, AgentContext)
    top = ctx.priority_rows[0]
    assert top["failure_mode"] == "Citation Text"
    assert top["cell"] == "Method × Genus-species"
    # KPI gap: current citation FAIL = 3/5 = 60%, target FAIL = 5% -> gap ~55pp
    assert ctx.kpi_gaps["citation_text"] == pytest.approx(55.0, abs=1.0)
    # cited examples are the failing run_ids from the top cell
    assert set(ctx.examples["Citation Text"]).issubset({"m0", "m1", "m2"})
    assert len(ctx.examples["Citation Text"]) <= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_experiment_agent.py::test_gather_context_picks_top_cell_and_examples -v`
Expected: FAIL — `cannot import name 'gather_context'`.

- [ ] **Step 3: Write minimal implementation**

Add to `core/experiment_agent.py`:

```python
import pandas as pd

from core.priority import priority_table, MODE_VERDICT


class AgentContext(BaseModel):
    priority_rows: list[dict]            # top-scored cells, highest first
    kpi_gaps: dict[str, float]           # eval_kind -> (current_fail - target_fail) in pp
    examples: dict[str, list[str]]       # failure_mode -> up to 3 failing run_ids


_EVAL_KIND = {"Citation Text": "citation_text", "Absent PHOSITA": "absent_phosita_reasoning"}


def gather_context(df: pd.DataFrame,
                   impact_tiers: dict[str, str],
                   exposure_tiers: dict[tuple[str, str], str],
                   targets: dict[str, float],
                   top_k: int = 5) -> AgentContext:
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

    # examples: failing run_ids from the top cell of each mode (if any in priority_rows)
    for row in priority_rows:
        mode = row["failure_mode"]
        if mode in examples:
            continue
        col = MODE_VERDICT[mode]
        cell_df = df[(df["claim_type"] == row["claim_type"])
                     & (df["relationship"] == row["relationship"])
                     & (df[col] == "FAIL")]
        examples[mode] = list(cell_df["run_id"].head(3))

    return AgentContext(priority_rows=priority_rows, kpi_gaps=kpi_gaps, examples=examples)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_experiment_agent.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add core/experiment_agent.py tests/test_experiment_agent.py
git commit -m "feat(agent): gather_context deterministic targeting"
```

---

## Task 5: `propose_plan` + demo-cache fallback

**Files:**
- Modify: `core/experiment_agent.py`
- Create: `traces/agent_demo_cache.json` (minimal stub now; curated in Task 10)
- Test: `tests/test_experiment_agent.py`

`propose_plan` builds a prompt from `AgentContext`, calls `core.llm.call_groq`, and parses the JSON into an `ExperimentPlan`. It retries once on malformed JSON, then raises `AgentPlanError`. `load_demo_plan` reads the committed cache for the page's fallback.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_experiment_agent.py
import core.experiment_agent as agent
from core.experiment_agent import propose_plan, AgentPlanError, load_demo_plan


_PLAN_JSON = (
    '{"experiments": [{"order": 1, "target_eval": "citation", '
    '"target_segment": "Method × Genus-species", "prompt_block": "Quote verbatim.", '
    '"predicted_delta_pp": -30.0, "rationale": "paraphrasing", "cited_run_ids": ["m0"]}]}'
)


def _ctx():
    return agent.AgentContext(
        priority_rows=[{"failure_mode": "Citation Text", "cell": "Method × Genus-species",
                        "claim_type": "Method", "relationship": "Genus-species",
                        "fail_rate": 1.0, "n": 3, "score": 27}],
        kpi_gaps={"citation_text": 55.0}, examples={"Citation Text": ["m0"]})


def test_propose_plan_parses_llm_json(monkeypatch):
    monkeypatch.setattr(agent, "call_groq",
                        lambda system, user, model=None: {"raw_output": _PLAN_JSON})
    plan = propose_plan(_ctx())
    assert len(plan.experiments) == 1
    assert plan.experiments[0].target_eval == "citation"


def test_propose_plan_retries_then_raises(monkeypatch):
    calls = {"n": 0}

    def bad(system, user, model=None):
        calls["n"] += 1
        return {"raw_output": "not json"}

    monkeypatch.setattr(agent, "call_groq", bad)
    with pytest.raises(AgentPlanError):
        propose_plan(_ctx())
    assert calls["n"] == 2          # initial + one retry


def test_propose_plan_passes_pm_feedback(monkeypatch):
    seen = {}
    monkeypatch.setattr(agent, "call_groq",
                        lambda system, user, model=None: seen.update(user=user) or {"raw_output": _PLAN_JSON})
    propose_plan(_ctx(), pm_feedback="focus on System claims")
    assert "focus on System claims" in seen["user"]


def test_load_demo_plan_returns_plan():
    plan = load_demo_plan()
    assert plan.experiments        # non-empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_experiment_agent.py -k "propose or demo" -v`
Expected: FAIL — `cannot import name 'propose_plan'`.

- [ ] **Step 3: Write minimal implementation**

Add to `core/experiment_agent.py`:

```python
from core.llm import call_groq

DEMO_CACHE_PATH = REPO_ROOT / "traces" / "agent_demo_cache.json"


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
        except Exception as e:        # pydantic ValidationError or JSON error
            last_err = e
            user = user + "\n\nYour previous output was not valid JSON. Return ONLY the JSON object."
    raise AgentPlanError(f"Could not parse a plan after 2 attempts: {last_err}")


def load_demo_plan(path: Path = DEMO_CACHE_PATH) -> ExperimentPlan:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ExperimentPlan.model_validate(data["plan"])
```

Create a minimal `traces/agent_demo_cache.json` (curated for real in Task 10):

```json
{
  "plan": {
    "experiments": [
      {"order": 1, "target_eval": "citation", "target_segment": "Method × Genus-species",
       "prompt_block": "For every element, corresponding_text MUST be an exact verbatim span copied from the target patent, or the empty string. Never paraphrase.",
       "predicted_delta_pp": -30.0,
       "rationale": "Citation FAILs concentrate in Method × Genus-species where the tool paraphrases prior art.",
       "cited_run_ids": []}
    ]
  },
  "stage_result": null
}
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_experiment_agent.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add core/experiment_agent.py traces/agent_demo_cache.json tests/test_experiment_agent.py
git commit -m "feat(agent): propose_plan with retry + demo-cache fallback"
```

---

## Task 6: `select_subset` — the runnable trace subset

**Files:**
- Create: `core/experiment_agent_runner.py`
- Test: `tests/test_experiment_agent_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_experiment_agent_runner.py
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
    # all targeted-segment ids present, capped total, includes a guardrail sample from elsewhere
    assert {"m0", "m1", "m2", "m3", "m4"}.issubset(set(ids))
    assert len(ids) <= 8
    assert any(i.startswith("o") for i in ids)


def test_select_subset_unknown_segment_returns_empty():
    assert select_subset(_frame(), segment="No × Such") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_experiment_agent_runner.py -v`
Expected: FAIL — `No module named 'core.experiment_agent_runner'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/experiment_agent_runner.py
"""Staged executor for the Experiment Agent: pick a runnable subset, regenerate it
with the cumulative system-prompt block, re-score both evals, and gate the result.
Pure logic + Groq calls (mocked in tests). No Dash."""
from __future__ import annotations

import pandas as pd


def select_subset(df: pd.DataFrame, segment: str, cap: int = 8, guardrail: int = 2) -> list[str]:
    """run_ids for the targeted 'ClaimType × Relationship' segment plus a small
    guardrail sample from other segments. Empty if the segment matches nothing."""
    try:
        claim_type, relationship = [s.strip() for s in segment.split("×")]
    except ValueError:
        return []
    in_seg = df[(df["claim_type"] == claim_type) & (df["relationship"] == relationship)]
    seg_ids = list(in_seg["run_id"])
    if not seg_ids:
        return []
    others = list(df[~df["run_id"].isin(seg_ids)]["run_id"].head(guardrail))
    return (seg_ids + others)[:cap]
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_experiment_agent_runner.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/experiment_agent_runner.py tests/test_experiment_agent_runner.py
git commit -m "feat(agent): select_subset for staged runs"
```

---

## Task 7: `run_stage` — regenerate, rescore, gate

**Files:**
- Modify: `core/experiment_agent_runner.py`
- Test: `tests/test_experiment_agent_runner.py`

`run_stage` composes the cumulative block, regenerates each subset trace with `core.regeneration.regenerate_one` using `build_system_prompt(extra_instructions=...)`, re-scores citation (`core.citation_eval.evaluate_trace`) and PHOSITA (`core.phosita_eval.evaluate_trace`, which needs a Groq client passed in), computes before/after FAIL, and calls `core.experiment_gate.evaluate_gate`. Callers pass `before_verdicts` (the baseline verdict map for the subset) so the math stays pure and testable.

- [ ] **Step 1: Write the failing test** (stubs regeneration + both scorers — no network)

```python
# add to tests/test_experiment_agent_runner.py
import core.experiment_agent_runner as runner
from core.experiment_agent import ProposedExperiment


def _exp():
    return ProposedExperiment(order=1, target_eval="citation",
                              target_segment="Method × Genus-species",
                              prompt_block="Quote verbatim.", predicted_delta_pp=-40.0,
                              rationale="x", cited_run_ids=[])


def test_run_stage_composes_block_and_gates(monkeypatch):
    captured = {}

    # regeneration returns a trivial trace dict per run_id, capturing the system prompt
    def fake_regen(trace, system_prompt):
        captured["system"] = system_prompt
        return {"run_id": trace["run_id"], "parsed_output": {"element_mappings": []}}

    # after the fix, citation now PASSes for every subset trace
    monkeypatch.setattr(runner, "regenerate_one", fake_regen)
    monkeypatch.setattr(runner, "score_citation", lambda tr: "PASS")
    monkeypatch.setattr(runner, "score_phosita", lambda tr, client: "PASS")
    monkeypatch.setattr(runner, "build_system_prompt",
                        lambda extra_instructions="": f"BASE|{extra_instructions}")

    subset = [{"run_id": "m0", "inputs": {}}, {"run_id": "m1", "inputs": {}}]
    before = {"m0": {"citation": "FAIL", "phosita": "PASS"},
              "m1": {"citation": "FAIL", "phosita": "PASS"}}

    result = runner.run_stage(_exp(), kept_block="PRIOR", subset_traces=subset,
                              before_verdicts=before, judge_client=object(),
                              cell_of={"m0": "Method × Genus-species",
                                       "m1": "Method × Genus-species"})

    # cumulative block: prior + new, threaded into build_system_prompt
    assert captured["system"] == "BASE|PRIOR\n\nQuote verbatim."
    # citation FAIL 100% -> 0%
    assert result.before == 100.0
    assert result.after == 0.0
    assert result.gate.passed is True
    assert result.coverage == "ran 2/2"
    assert result.new_block == "PRIOR\n\nQuote verbatim."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_experiment_agent_runner.py::test_run_stage_composes_block_and_gates -v`
Expected: FAIL — `cannot import name 'run_stage'` / missing `score_citation`.

- [ ] **Step 3: Write minimal implementation**

Add to `core/experiment_agent_runner.py`:

```python
from dataclasses import dataclass

from core.citation_eval import evaluate_trace as _citation_eval
from core.experiment_gate import GateResult, evaluate_gate
from core.experiment_agent import ProposedExperiment
from core.llm import build_system_prompt
from core.phosita_eval import evaluate_trace as _phosita_eval
from core.regeneration import regenerate_one

_TARGET_KEY = {"citation": "citation", "phosita": "phosita"}


def score_citation(trace: dict) -> str:
    return _citation_eval(trace)["verdict"]


def score_phosita(trace: dict, client) -> str:
    res = _phosita_eval(trace, client)
    return res["verdict"] if res else "NO_CITATIONS"


@dataclass
class StageResult:
    before: float                 # FAIL% on the targeted eval, baseline
    after: float                  # FAIL% on the targeted eval, post-change
    other_before: float
    other_after: float
    gate: GateResult
    coverage: str                 # "ran X/Y"
    new_block: str                # cumulative block to carry forward if KEPT
    after_verdicts: dict          # run_id -> {"citation":..., "phosita":...}


def _fail_pct(verdicts: list[str]) -> float:
    scored = [v for v in verdicts if v in ("PASS", "FAIL")]
    if not scored:
        return 0.0
    return 100.0 * sum(v == "FAIL" for v in scored) / len(scored)


def run_stage(proposed: ProposedExperiment, *, kept_block: str, subset_traces: list[dict],
              before_verdicts: dict, judge_client, cell_of: dict[str, str]) -> StageResult:
    new_block = (kept_block + "\n\n" + proposed.prompt_block).strip() if kept_block \
        else proposed.prompt_block
    system_prompt = build_system_prompt(extra_instructions=new_block)

    target = proposed.target_eval                 # "citation" | "phosita"
    other = "phosita" if target == "citation" else "citation"

    after_verdicts: dict[str, dict] = {}
    ran = 0
    for trace in subset_traces:
        regenerated = regenerate_one(trace, system_prompt)
        if regenerated.get("parsed_output") is None and regenerated.get("status") not in (None, "ok"):
            continue                              # skip a failed regeneration; lowers coverage
        rid = regenerated["run_id"]
        after_verdicts[rid] = {
            "citation": score_citation(regenerated),
            "phosita": score_phosita(regenerated, judge_client),
        }
        ran += 1

    ids = list(after_verdicts)
    before_t = _fail_pct([before_verdicts[i][target] for i in ids if i in before_verdicts])
    after_t = _fail_pct([after_verdicts[i][target] for i in ids])
    before_o = _fail_pct([before_verdicts[i][other] for i in ids if i in before_verdicts])
    after_o = _fail_pct([after_verdicts[i][other] for i in ids])

    # per-cell deltas on the targeted eval
    cells = {cell_of.get(i, "?") for i in ids}
    cell_deltas: dict[str, float] = {}
    for cell in cells:
        cids = [i for i in ids if cell_of.get(i) == cell]
        b = _fail_pct([before_verdicts[i][target] for i in cids if i in before_verdicts])
        a = _fail_pct([after_verdicts[i][target] for i in cids])
        cell_deltas[cell] = a - b

    gate = evaluate_gate(
        target_eval=target, before=before_t, after=after_t,
        segment_before=before_t, segment_after=after_t,
        other_before=before_o, other_after=after_o,
        cell_deltas_pp=cell_deltas, ruler_ok=True,
    )
    return StageResult(before=before_t, after=after_t,
                       other_before=before_o, other_after=after_o,
                       gate=gate, coverage=f"ran {ran}/{len(subset_traces)}",
                       new_block=new_block, after_verdicts=after_verdicts)
```

Note for the test: it monkeypatches `runner.regenerate_one`, `runner.score_citation`, `runner.score_phosita`, and `runner.build_system_prompt`, so those names must be module-level in `experiment_agent_runner` (they are, via the imports + defs above).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_experiment_agent_runner.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add core/experiment_agent_runner.py tests/test_experiment_agent_runner.py
git commit -m "feat(agent): run_stage regenerate+rescore+gate (cumulative block)"
```

---

## Task 8: `keep_stage` — append to the experiments manifest

**Files:**
- Modify: `core/experiment_agent_runner.py`
- Test: `tests/test_experiment_agent_runner.py`

On KEEP, append an `Experiment` row to `traces/experiments.jsonl` so the Comparison tab renders the move. Reuse the `core.experiments.Experiment` model and `MANIFEST_PATH`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_experiment_agent_runner.py
import json
from core.experiment_agent_runner import keep_stage


def test_keep_stage_appends_manifest_row(tmp_path):
    manifest = tmp_path / "experiments.jsonl"
    keep_stage(exp_id="agent-1", name="Agent: verbatim (Method × Genus-species)",
               created="2026-06-20T10:00:00Z",
               phosita_eval_file="phosita_eval_full.agent-1.jsonl",
               citation_eval_file="citation_text_eval_full.agent-1.jsonl",
               manifest_path=manifest)
    lines = manifest.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["exp_id"] == "agent-1"
    assert row["name"].startswith("Agent:")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_experiment_agent_runner.py::test_keep_stage_appends_manifest_row -v`
Expected: FAIL — `cannot import name 'keep_stage'`.

- [ ] **Step 3: Write minimal implementation**

Add to `core/experiment_agent_runner.py`:

```python
import json as _json
from pathlib import Path

from core.experiments import Experiment, MANIFEST_PATH


def keep_stage(*, exp_id: str, name: str, created: str,
               phosita_eval_file: str, citation_eval_file: str,
               trace_set: str = "live", manifest_path: Path = MANIFEST_PATH) -> None:
    """Append one Experiment row to the manifest so the Comparison tab shows it."""
    exp = Experiment(exp_id=exp_id, name=name, created=created, splits=[], repetitions=1,
                     trace_set=trace_set, phosita_eval_file=phosita_eval_file,
                     citation_eval_file=citation_eval_file)
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "a", encoding="utf-8") as f:
        f.write(_json.dumps(exp.model_dump()) + "\n")
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_experiment_agent_runner.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add core/experiment_agent_runner.py tests/test_experiment_agent_runner.py
git commit -m "feat(agent): keep_stage appends to experiments manifest"
```

---

## Task 9: The `/eval/agent` Dash page

**Files:**
- Create: `app_unified/pages/eval_agent.py`
- Test: `tests/test_eval_agent_page.py`

Dash callbacks are hard to unit-test directly, so keep ALL logic in the core modules (done) and test the page's two thin pure helpers: `render_plan(plan)` (plan → list of card components, smoke) and `render_stage(result)` (StageResult → result component, smoke). The callbacks themselves wire buttons to `gather_context`/`propose_plan`/`run_stage`/`keep_stage` and store state in `dcc.Store`s.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eval_agent_page.py
import app_unified.app  # registers pages
from app_unified.pages.eval_agent import render_plan, render_stage
from core.experiment_agent import ExperimentPlan, ProposedExperiment


def test_render_plan_one_card_per_experiment():
    plan = ExperimentPlan(experiments=[
        ProposedExperiment(order=1, target_eval="citation", target_segment="Method × Genus-species",
                           prompt_block="Quote verbatim.", predicted_delta_pp=-30.0,
                           rationale="x", cited_run_ids=["m0"]),
        ProposedExperiment(order=2, target_eval="phosita", target_segment="System × Overlapping",
                           prompt_block="Explain PSA.", predicted_delta_pp=-15.0,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_eval_agent_page.py -v`
Expected: FAIL — `No module named 'app_unified.pages.eval_agent'`.

- [ ] **Step 3: Write minimal implementation**

Model the file on an existing page (open `app_unified/pages/eval_comparison.py` for the exact import style, `register_page`, `layout`, `@callback` conventions, background-callback usage, and the project's CSS class names). Key elements:

```python
# app_unified/pages/eval_agent.py
import dash
from dash import html, dcc, callback, Input, Output, State, no_update

from core.experiment_agent import (gather_context, propose_plan, load_demo_plan,
                                    AgentPlanError, ExperimentPlan)
from core.experiment_agent_runner import select_subset, run_stage, keep_stage, StageResult

dash.register_page(__name__, path="/eval/agent", name="Experiment Agent")


def render_plan(plan: ExperimentPlan) -> list:
    cards = []
    for e in plan.experiments:
        cards.append(html.Div(className="wb-card", children=[
            html.Div(f"#{e.order} · target: {e.target_eval} · {e.target_segment}",
                     className="wb-card-title"),
            html.P(e.rationale),
            html.Pre(e.prompt_block, className="wb-prompt-block"),
            html.Div(f"Predicted Δ: {e.predicted_delta_pp:+.0f}pp (prediction — measured result decides)",
                     className="wb-muted"),
        ]))
    return cards


def render_stage(result: StageResult) -> html.Div:
    verdict = "PASS" if result.gate.passed else "FAIL"
    return html.Div(className="wb-card", children=[
        html.Div(f"Gate: {verdict} · {result.coverage}",
                 className=f"wb-gate-{verdict.lower()}"),
        html.Div(f"Target eval FAIL: {result.before:.0f}% → {result.after:.0f}%"),
        html.Ul([html.Li(r) for r in result.gate.reasons]),
        html.Div([
            html.Button("Approve (KEEP)", id="agent-keep", className="wb-btn-primary"),
            html.Button("Reject (REVERT)", id="agent-revert", className="wb-btn"),
        ]),
    ])


layout = html.Div(className="wb-root", children=[
    html.H2("Experiment Agent"),
    html.P("The agent reads the live dashboard, proposes a ranked plan, and runs it "
           "one change at a time — you keep or revert each result."),
    html.Button("Analyze", id="agent-analyze", className="wb-btn-primary"),
    dcc.Store(id="agent-plan-store"),
    dcc.Store(id="agent-stage-index", data=0),
    dcc.Store(id="agent-kept-block", data=""),
    html.Div(id="agent-plan-view"),
    dcc.Textarea(id="agent-feedback", placeholder="PM feedback — steer the plan…",
                 className="wb-textarea"),
    html.Button("Revise plan", id="agent-revise", className="wb-btn"),
    html.Button("Approve plan & start", id="agent-start", className="wb-btn-primary"),
    html.Div(id="agent-stage-view"),
    dcc.Link("→ See results in the Comparison tab", href="/eval/comparison"),
])
```

Wire the callbacks (follow `eval_comparison.py`'s background-callback pattern). Behaviour:
- **Analyze / Revise** → build the dashboard frame (reuse the same helper `eval_overview.py` uses to call `core.workbench_data.load_merged` + the page's impact/exposure/target stores), call `gather_context`, then `propose_plan(ctx, pm_feedback)`. On `AgentPlanError` or missing `GROQ_API_KEY`, call `load_demo_plan()` and show a "cached plan" banner. Store the plan; render via `render_plan`.
- **Approve plan & start / KEEP** → for the current stage index, `select_subset` → load those trace dicts → `run_stage(...)` with `kept_block` from the store; render via `render_stage`. On KEEP: write the regenerated subset's eval files for this stage and call `keep_stage(...)`, set `kept_block = result.new_block`, increment stage index. On REVERT: leave `kept_block`, increment stage index. When index passes the last experiment, show "plan complete — see Comparison".

Keep each callback small; all real work is the already-tested core functions.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_eval_agent_page.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app_unified/pages/eval_agent.py tests/test_eval_agent_page.py
git commit -m "feat(agent): /eval/agent page (plan, feedback, staged run)"
```

---

## Task 10: Dashboard link + curate the demo cache

**Files:**
- Modify: `app_unified/pages/eval_overview.py` (add link near the priority table)
- Modify: `traces/agent_demo_cache.json` (curate a realistic plan + a realistic StageResult)

- [ ] **Step 1: Add the Dashboard link**

In `app_unified/pages/eval_overview.py`, near where the priority table is rendered, add:

```python
dcc.Link("→ Ask the Experiment Agent", href="/eval/agent", className="wb-link"),
```

(Match the file's existing import of `dcc` and class-name conventions; if `dcc` isn't imported there, add it.)

- [ ] **Step 2: Curate the demo cache**

Replace `traces/agent_demo_cache.json` with a realistic 2-3 experiment plan whose #1 mirrors the known EXP1 verbatim win (citation, Method × Genus-species, ~−40pp), plus a `stage_result` block matching the `StageResult` field names (`before, after, other_before, other_after, gate{passed,reasons}, coverage, new_block, after_verdicts`). This is the offline-recording safety net referenced in the spec.

- [ ] **Step 3: Manually verify the page loads**

Run: `python -m app_unified.app`, open `http://127.0.0.1:8050/eval/agent`, click **Analyze** with no `GROQ_API_KEY` set → confirm the cached plan renders with the banner; confirm the Dashboard shows the "Ask the Experiment Agent" link. Stop the server.

- [ ] **Step 4: Commit**

```bash
git add app_unified/pages/eval_overview.py traces/agent_demo_cache.json
git commit -m "feat(agent): dashboard link + curated demo cache"
```

---

## Task 11: Full suite + branch wrap-up

**Files:** none (verification)

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: all green — the prior 237 plus the new agent tests; no network calls.

- [ ] **Step 2: Confirm default behavior is untouched**

Run: `python -m pytest -k "system_prompt or build_system_prompt or regenerat" -q`
Expected: PASS — proves the `build_system_prompt` default and the regeneration refactor changed no existing behavior.

- [ ] **Step 3: Commit any final fixups, then stop for review**

Leave the branch `feat/experiment-agent` ready for `superpowers:finishing-a-development-branch` (PR or merge decision is the user's).

---

## Self-Review

**Spec coverage:**
- New tab `/eval/agent` → Task 9. ✓
- Analyze → ranked plan of ~3 grounded experiments → Tasks 4 (context), 5 (propose_plan), 9 (UI). ✓
- PM feedback loop revises the plan → Task 5 (`pm_feedback` arg) + Task 9 (Revise button). ✓
- Staged execution, per-experiment KEEP/REVERT, cumulative baseline → Task 7 (`new_block` cumulative) + Task 9 (stage index + kept-block store). ✓
- Runnable lever = appended system-prompt block → Task 1 (`extra_instructions`) + Task 7 (threading). ✓
- Results in Comparison tab via manifest append → Task 8. ✓
- Error handling + demo cache fallback → Task 5 (retry + `load_demo_plan`), Task 7 (coverage skip), Task 9 (banner), Task 10 (curated cache). ✓
- Dashboard link → Task 10. ✓
- All Groq calls mocked in tests → Tasks 2,4,5,7 use monkeypatch; no live calls. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. ✓

**Type consistency:** `build_system_prompt(extra_instructions=...)` (Tasks 1,7,9); `ProposedExperiment`/`ExperimentPlan` fields identical across Tasks 3,5,7,9; `StageResult` fields identical across Tasks 7,9,10; `regenerate_one(trace, system_prompt)` identical across Tasks 2,7; `evaluate_gate(...)` keyword args match `core/experiment_gate.py`. ✓

**Note on tiny-n confidence label** (spec §5): the `coverage` string carries n; surfacing a "low-confidence, n<…" note is a one-line addition in `render_stage` (Task 9) — implement inline there.
