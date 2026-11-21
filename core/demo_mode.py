"""Demo mode: cache-first optimization for portfolio deployments.

When DEMO_MODE=true, the app pre-loads all cached traces/evals and disables
live Groq calls. This enables:
- Fast cold starts (1-2 sec, not 5-10 sec)
- No API key required
- Fully interactive Dashboard, Traces, Comparison tabs
- /eval/agent falls back to cached plan

Set DEMO_MODE=true in Render's environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
# In the hosted demo "/" lands on the dashboard, so the prototype moves aside.
PROTOTYPE_PATH = "/prototype" if DEMO_MODE else "/"
REPO_ROOT = Path(__file__).resolve().parents[1]

# Pre-load cached data on module import
_CACHED_TRACES: dict = {}
_CACHED_EVALS_CITATION: dict = {}
_CACHED_EVALS_PHOSITA: dict = {}
_CACHED_PLAN: dict | None = None


def _load_jsonl(path: Path) -> dict[str, dict]:
    """Load a .jsonl file into {run_id: row_dict}."""
    result = {}
    if not path.exists():
        return result
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                import json

                row = json.loads(line)
                run_id = row.get("run_id")
                if run_id:
                    result[run_id] = row
    except Exception as e:
        print(f"⚠️  Demo mode: failed to load {path.name}: {e}")
    return result


def _load_cached_data() -> None:
    """Pre-load traces and evals from disk."""
    global _CACHED_TRACES, _CACHED_EVALS_CITATION, _CACHED_EVALS_PHOSITA, _CACHED_PLAN

    if not DEMO_MODE:
        return

    print("[DEMO MODE] Pre-loading cached data...")

    # Load traces
    traces_path = REPO_ROOT / "traces" / "traces.jsonl"
    _CACHED_TRACES = _load_jsonl(traces_path)
    print(f"  > Loaded {len(_CACHED_TRACES)} traces")

    # Load evals
    citation_path = REPO_ROOT / "traces" / "citation_text_eval_full.jsonl"
    _CACHED_EVALS_CITATION = _load_jsonl(citation_path)
    print(f"  > Loaded {len(_CACHED_EVALS_CITATION)} citation evals")

    phosita_path = REPO_ROOT / "traces" / "phosita_eval_full.jsonl"
    _CACHED_EVALS_PHOSITA = _load_jsonl(phosita_path)
    print(f"  > Loaded {len(_CACHED_EVALS_PHOSITA)} phosita evals")

    # Load agent demo plan
    plan_path = REPO_ROOT / "traces" / "agent_demo_cache.json"
    if plan_path.exists():
        try:
            import json

            with open(plan_path, encoding="utf-8") as f:
                _CACHED_PLAN = json.load(f)
                print(f"  > Loaded cached experiment plan")
        except Exception as e:
            print(f"  ! Failed to load plan cache: {e}")


def get_traces() -> dict[str, dict]:
    """Return cached traces (demo mode only)."""
    return _CACHED_TRACES


def get_citation_evals() -> dict[str, dict]:
    """Return cached citation evals (demo mode only)."""
    return _CACHED_EVALS_CITATION


def get_phosita_evals() -> dict[str, dict]:
    """Return cached phosita evals (demo mode only)."""
    return _CACHED_EVALS_PHOSITA


def get_cached_plan() -> dict | None:
    """Return cached experiment plan (demo mode only)."""
    return _CACHED_PLAN


def examples(limit: int = 3) -> list[dict]:
    """Recorded traces worth replaying in the prototype: successful, with enough
    mapped elements to be readable, one per distinct source/target pair."""
    picked, seen = [], set()
    for row in _CACHED_TRACES.values():
        out = row.get("parsed_output") or {}
        if row.get("status") != "success" or len(out.get("element_mappings") or []) < 4:
            continue
        inputs = row["inputs"]
        pair = (inputs["source_patent"]["label"], inputs["target_patent"]["label"])
        if pair in seen:
            continue
        seen.add(pair)
        picked.append({"title": f"{pair[0]} vs {pair[1]}", "trace": row})
        if len(picked) == limit:
            break
    return picked


def find_recorded(claim_a: str, claim_b: str) -> dict | None:
    """The recorded trace whose two independent claims match the given text."""
    a, b = (claim_a or "").strip(), (claim_b or "").strip()
    for row in _CACHED_TRACES.values():
        inputs = row.get("inputs") or {}
        if not row.get("parsed_output") or row.get("status") != "success":
            continue
        if (inputs["source_patent"]["independent_claim"].strip() == a
                and inputs["target_patent"]["independent_claim"].strip() == b):
            return row
    return None


def stub_groq_response() -> dict:
    """Return a stub Groq response for demo mode.

    This is returned when call_groq() is invoked in demo mode without
    a real API key. The response is minimal but valid for the LLM response
    contract.
    """
    return {
        "raw_output": '{"element_mappings": [], "overall_opinion": "Demo mode: cached data only"}',
        "model": "demo",
        "tokens_input": 0,
        "tokens_output": 0,
        "latency_ms": 0,
    }


# Pre-load on module import
if DEMO_MODE:
    _load_cached_data()
