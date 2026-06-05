"""Run the existing eval scripts on a selected trace set, as a subprocess.

This does NOT modify the evals (the ruler). It only invokes the same CLI an
operator would run by hand, pointing --traces/--out at the chosen set. Intended
to be called from a Dash background callback.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from core.workbench_data import TraceSet

REPO_ROOT = Path(__file__).resolve().parents[1]
CITATION_SCRIPT = REPO_ROOT / "scripts" / "run_citation_eval.py"
PHOSITA_SCRIPT = REPO_ROOT / "scripts" / "run_phosita_eval.py"


def build_eval_commands(trace_set: TraceSet) -> list[list[str]]:
    """Return [citation_cmd, phosita_cmd] for the selected set (citation first — cheaper)."""
    py = sys.executable
    return [
        [py, str(CITATION_SCRIPT),
         "--traces", str(trace_set.traces_path),
         "--out", str(trace_set.citation_path)],
        [py, str(PHOSITA_SCRIPT),
         "--traces", str(trace_set.traces_path),
         "--out", str(trace_set.phosita_path)],
    ]


def run_evals(trace_set: TraceSet, set_status=None) -> str:
    """Run both evals sequentially; stream a short status via set_status(str).

    Returns a final summary string. Re-running is safe — the scripts are
    idempotent-cached. Raises CalledProcessError if a script exits non-zero.
    """
    log_lines: list[str] = []
    for label, cmd in zip(("Citation", "PHOSITA"), build_eval_commands(trace_set)):
        if set_status:
            set_status(f"Running {label} eval on '{trace_set.name}'…")
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True,
                              text=True, check=True)
        tail = (proc.stdout or "").strip().splitlines()[-3:]
        log_lines.append(f"[{label}] " + " | ".join(tail))
    return "\n".join(log_lines)
