"""Staged executor for the Experiment Agent: pick a runnable subset, regenerate it
with the cumulative system-prompt block, re-score both evals, and gate the result.
Pure logic + Groq calls (mocked in tests). No Dash."""
from __future__ import annotations

import json as _json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from core.citation_eval import evaluate_trace as _citation_eval
from core.experiment_agent import ProposedExperiment
from core.experiment_gate import GateResult, evaluate_gate
from core.experiments import Experiment, MANIFEST_PATH
from core.llm import build_system_prompt
from core.phosita_eval import evaluate_trace as _phosita_eval
from core.regeneration import regenerate_one


# ---------------------------------------------------------------------------
# Task 6: select_subset
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 7: run_stage — regenerate, rescore, gate
# ---------------------------------------------------------------------------

def score_citation(trace: dict) -> str:
    return _citation_eval(trace)["verdict"]


def score_phosita(trace: dict, client) -> str:
    res = _phosita_eval(trace, client)
    return res["verdict"] if res else "NO_CITATIONS"


@dataclass
class StageResult:
    before: float
    after: float
    other_before: float
    other_after: float
    gate: GateResult
    coverage: str
    new_block: str
    after_verdicts: dict


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

    target = proposed.target_eval
    other = "phosita" if target == "citation" else "citation"

    after_verdicts: dict[str, dict] = {}
    ran = 0
    for trace in subset_traces:
        regenerated = regenerate_one(trace, system_prompt)
        if regenerated.get("parsed_output") is None and regenerated.get("status") not in (None, "ok"):
            continue
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

    cells = {cell_of.get(i, "?") for i in ids}
    cell_deltas: dict[str, float] = {}
    for cell in cells:
        cids = [i for i in ids if cell_of.get(i) == cell]
        b = _fail_pct([before_verdicts[i][target] for i in cids if i in before_verdicts])
        a = _fail_pct([after_verdicts[i][target] for i in cids])
        cell_deltas[cell] = a - b

    # Segment metrics cover ONLY the targeted segment's traces (not the guardrail
    # sample), so the gate's "improved >=10pp in the targeted segment" branch can
    # actually fire. Fall back to overall when the subset has no segment traces.
    seg_ids = [i for i in ids if cell_of.get(i) == proposed.target_segment]
    if seg_ids:
        segment_before = _fail_pct([before_verdicts[i][target] for i in seg_ids if i in before_verdicts])
        segment_after = _fail_pct([after_verdicts[i][target] for i in seg_ids])
    else:
        segment_before, segment_after = before_t, after_t

    gate = evaluate_gate(
        target_eval=target, before=before_t, after=after_t,
        segment_before=segment_before, segment_after=segment_after,
        other_before=before_o, other_after=after_o,
        cell_deltas_pp=cell_deltas, ruler_ok=True,
    )
    return StageResult(before=before_t, after=after_t,
                       other_before=before_o, other_after=after_o,
                       gate=gate, coverage=f"ran {ran}/{len(subset_traces)}",
                       new_block=new_block, after_verdicts=after_verdicts)


# ---------------------------------------------------------------------------
# Task 8: keep_stage — append to experiments manifest
# ---------------------------------------------------------------------------

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
