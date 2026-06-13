# core/experiment_gate.py
"""Pure gate logic for Phase 2 experiments: the token guardrail and the
quantitative success gate. No app/IO dependencies — callers pass in the measured
FAIL rates so this stays unit-testable. See
docs/superpowers/specs/2026-06-13-phase2-experiments-design.md."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateResult:
    passed: bool
    reasons: list[str]          # one line per criterion, with its verdict


def system_prompt_within_budget() -> tuple[bool, int]:
    """Token guardrail: the live product system prompt must fit its budget so
    spec-truncation math (which uses the fixed SYSTEM_PROMPT_TOKENS) stays valid."""
    from core.llm import build_system_prompt, _estimate_tokens, SYSTEM_PROMPT_TOKENS
    n = _estimate_tokens(build_system_prompt())
    return n <= SYSTEM_PROMPT_TOKENS, n


def evaluate_gate(*, target_eval: str,
                  before: float, after: float,
                  segment_before: float, segment_after: float,
                  other_before: float, other_after: float,
                  cell_deltas_pp: dict[str, float],
                  ruler_ok: bool) -> GateResult:
    """All inputs are FAIL rates in percent (0-100). A negative delta = improvement.

    PASS requires ALL of:
      - target eval FAIL drops >= 3pp overall OR >= 10pp in the targeted segment
      - the other eval does NOT regress more than +2pp
      - the ruler (judge-vs-human alignment) is unchanged (ruler_ok)
      - no dimension cell regresses by more than +10pp
    """
    reasons: list[str] = []
    overall_delta = after - before
    segment_delta = segment_after - segment_before
    other_delta = other_after - other_before
    worst_cell = max(cell_deltas_pp.values(), default=0.0)

    c1 = (overall_delta <= -3.0) or (segment_delta <= -10.0)
    c2 = other_delta <= 2.0
    c3 = bool(ruler_ok)
    c4 = worst_cell <= 10.0

    reasons.append(
        f"[{'PASS' if c1 else 'FAIL'}] target {target_eval}: "
        f"{overall_delta:+.1f}pp overall, {segment_delta:+.1f}pp segment "
        f"(need <=-3 overall or <=-10 segment)")
    reasons.append(
        f"[{'PASS' if c2 else 'FAIL'}] other eval: {other_delta:+.1f}pp "
        f"(need <=+2)")
    reasons.append(
        f"[{'PASS' if c3 else 'FAIL'}] ruler vs human: "
        f"{'unchanged' if c3 else 'MOVED'}")
    reasons.append(
        f"[{'PASS' if c4 else 'FAIL'}] worst dimension cell: {worst_cell:+.1f}pp "
        f"(need <=+10)")
    return GateResult(passed=c1 and c2 and c3 and c4, reasons=reasons)
