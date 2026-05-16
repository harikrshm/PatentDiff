import json
from pathlib import Path

from core.citation_eval import normalize, score_corresponding, evaluate_trace

TRACES_PATH = Path(__file__).resolve().parents[1] / "traces" / "traces.jsonl"


def _load_trace(run_id: str) -> dict:
    with open(TRACES_PATH, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["run_id"] == run_id:
                return d
    raise AssertionError(f"trace {run_id} not found")


def test_normalize_lowercases():
    assert normalize("Hello WORLD") == "hello world"


def test_normalize_collapses_whitespace():
    assert normalize("a    b\t\nc  d") == "a b c d"


def test_normalize_strips_leading_trailing_whitespace():
    assert normalize("   hello   ") == "hello"


def test_normalize_folds_non_breaking_hyphen():
    # U+2011 NON-BREAKING HYPHEN appears throughout the patent traces.
    # NFKC folds it to U+2010 (regular hyphen). What matters for the eval is
    # that both CT and target_text get the same fold, so they match.
    assert normalize("non‑obvious") == "non‐obvious"


def test_score_full_substring_is_quoted():
    target = "A method comprising: receiving a speech input from a user through a dialogue interface of the digital assistant, the speech input related to a search; obtaining a dialog session..."
    ct = "receiving a speech input from a user through a dialogue interface of the digital assistant, the speech input related to a search;"
    result = score_corresponding(ct, target)
    assert result["verdict"] == "quoted"
    assert result["contiguous_ratio"] >= 0.95
    assert result["quotation_score"] >= 0.75


def test_score_summary_with_meta_narration_is_summarised():
    target = "Apparatus for calculating driving coefficients for loudspeakers based on a virtual source position located inside or outside a loudspeaker transition zone."
    ct = "The target claim recites a loudspeaker transition zone and specifies that different calculation rules are applied depending on whether the virtual source position lies inside or outside this zone. This functions as zone constraint metadata governing the rendering process."
    result = score_corresponding(ct, target)
    assert result["verdict"] == "summarised"
    assert result["quotation_score"] < 0.75


def test_score_short_ct_uses_fallback():
    # CT has <5 tokens — must use 3-gram fallback path
    target = "a system comprising a processor and a memory"
    ct = "a processor and a memory"
    result = score_corresponding(ct, target)
    assert result["verdict"] == "quoted"


def test_score_empty_target_returns_summarised():
    target = ""
    ct = "anything at all here"
    result = score_corresponding(ct, target)
    assert result["verdict"] == "summarised"
    assert result["quotation_score"] == 0.0


def test_evaluate_trace_pass_when_all_quoted():
    target_patent = {
        "independent_claim": "A method comprising: receiving a speech input; obtaining a dialog session.",
        "specification": "",
    }
    trace = {
        "run_id": "test-pass",
        "inputs": {"target_patent": target_patent},
        "parsed_output": {
            "element_mappings": [
                {"element_number": 1, "corresponding_text": "receiving a speech input"},
                {"element_number": 2, "corresponding_text": "obtaining a dialog session"},
            ]
        },
    }
    result = evaluate_trace(trace)
    assert result["verdict"] == "PASS"
    assert result["num_elements_scored"] == 2
    assert result["num_quoted"] == 2
    assert result["num_summarised"] == 0


def test_evaluate_trace_fail_when_any_summarised():
    target_patent = {
        "independent_claim": "A method comprising: receiving a speech input; obtaining a dialog session.",
        "specification": "",
    }
    trace = {
        "run_id": "test-fail",
        "inputs": {"target_patent": target_patent},
        "parsed_output": {
            "element_mappings": [
                {"element_number": 1, "corresponding_text": "receiving a speech input"},
                {
                    "element_number": 2,
                    "corresponding_text": "The target claim recites a dialog session and explains its purpose in detail.",
                },
            ]
        },
    }
    result = evaluate_trace(trace)
    assert result["verdict"] == "FAIL"
    assert result["num_summarised"] >= 1


def test_evaluate_trace_no_citations_when_all_empty():
    trace = {
        "run_id": "test-empty",
        "inputs": {"target_patent": {"independent_claim": "x", "specification": ""}},
        "parsed_output": {
            "element_mappings": [
                {"element_number": 1, "corresponding_text": ""},
                {"element_number": 2, "corresponding_text": "   "},
            ]
        },
    }
    result = evaluate_trace(trace)
    assert result["verdict"] == "NO_CITATIONS"
    assert result["num_elements_scored"] == 0


def test_evaluate_trace_skips_empty_corresponding_text():
    target_patent = {
        "independent_claim": "receiving a speech input",
        "specification": "",
    }
    trace = {
        "run_id": "test-skip",
        "inputs": {"target_patent": target_patent},
        "parsed_output": {
            "element_mappings": [
                {"element_number": 1, "corresponding_text": "receiving a speech input"},
                {"element_number": 2, "corresponding_text": ""},
                {"element_number": 3, "corresponding_text": "   "},
            ]
        },
    }
    result = evaluate_trace(trace)
    assert result["verdict"] == "PASS"
    assert result["num_elements_scored"] == 1


def test_fixture_known_fail_b247f372():
    # Real annotated FAIL: source US20250024222A1, human-tagged citation_text
    trace = _load_trace("b247f372-1a0c-4218-b619-b9e0f6b84bd4")
    result = evaluate_trace(trace)
    assert result["verdict"] == "FAIL"
    # All 4 of its non-empty CTs are summaries; expect at least 3 flagged
    assert result["num_summarised"] >= 3


def test_fixture_known_fail_a0df6f16():
    # Second real annotated FAIL with citation_text
    trace = _load_trace("a0df6f16-08b2-4e90-b7bd-0e402154bb48")
    result = evaluate_trace(trace)
    assert result["verdict"] == "FAIL"


def test_fixture_known_pass_8992c05a():
    # Real PASS trace with clear quoted citations
    trace = _load_trace("8992c05a-2bb5-4ebd-b749-1f3118233e3a")
    result = evaluate_trace(trace)
    assert result["verdict"] == "PASS"


def test_normalize_folds_curly_double_quotes():
    # NFKC turns curly quotes into ASCII via compatibility decomp? Actually no -
    # NFKC does NOT change curly quotes. Test exists to pin behavior so we don't
    # accidentally rely on quote folding that doesn't happen.
    result = normalize("“foo”")
    # curly quotes survive NFKC; only lowercase + whitespace changes apply
    assert result == "“foo”"
