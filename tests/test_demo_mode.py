"""Demo mode: recorded examples feed the prototype; nothing live is touched."""
from unittest.mock import patch

import pytest

from app_unified.pages import prototype
from core import demo_mode


def _mapping(i):
    return {"element_number": i, "element_text": f"element {i}", "corresponding_text": "",
            "novelty": "N", "inventive_step": "N", "verdict": "N", "comment": "c"}


def _trace(run_id, src, tgt, *, n_elements=5, status="success"):
    return {
        "run_id": run_id, "status": status,
        "inputs": {
            "source_patent": {"label": src, "independent_claim": f"claim {src}", "specification": "s"},
            "target_patent": {"label": tgt, "independent_claim": f"claim {tgt}", "specification": "t"},
        },
        "parsed_output": {"element_mappings": [_mapping(i) for i in range(n_elements)],
                          "overall_opinion": "recorded opinion"},
        "llm_response": {"model": "m", "tokens_input": 1, "tokens_output": 2, "latency_ms": 3},
    }


@pytest.fixture
def recorded(monkeypatch):
    traces = {
        "a": _trace("a", "US1", "US2"),
        "dup": _trace("dup", "US1", "US2"),                 # same pair: skipped
        "short": _trace("short", "US3", "US4", n_elements=2),  # too few elements
        "bad": _trace("bad", "US5", "US6", status="error"),
        "b": _trace("b", "US7", "US8"),
    }
    monkeypatch.setattr(demo_mode, "_CACHED_TRACES", traces)
    return traces


def test_examples_are_distinct_readable_successes(recorded):
    got = demo_mode.examples()
    assert [e["trace"]["run_id"] for e in got] == ["a", "b"]
    assert got[0]["title"] == "US1 vs US2"


def test_find_recorded_matches_on_both_claims(recorded):
    assert demo_mode.find_recorded("claim US1 ", "claim US2")["run_id"] == "a"
    assert demo_mode.find_recorded("claim US1", "claim other") is None
    assert demo_mode.find_recorded("claim US5", "claim US6") is None  # errored run


def test_prototype_replays_recorded_without_model_or_trace_writes(recorded, monkeypatch):
    monkeypatch.setattr(demo_mode, "DEMO_MODE", True)
    with patch.object(prototype, "call_groq") as groq, patch.object(prototype, "append_trace") as append:
        status, report, meta = prototype.run_analysis(
            "US1", "claim US1", "s", "US2", "claim US2", "t")
    assert status == "" and report is not None and meta is not None
    groq.assert_not_called()
    append.assert_not_called()


def test_prototype_demo_unrecorded_text_explains_instead_of_calling_model(recorded, monkeypatch):
    monkeypatch.setattr(demo_mode, "DEMO_MODE", True)
    with patch.object(prototype, "call_groq") as groq:
        status, report, meta = prototype.run_analysis(
            "US1", "edited claim", "s", "US2", "claim US2", "t")
    assert "Load example" in status and report is None and meta is None
    groq.assert_not_called()
