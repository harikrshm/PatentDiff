import json
from unittest.mock import MagicMock

import pytest

from core.phosita_eval import (
    PROMPT_VERSION,
    JUDGE_MODEL,
    JUDGE_TEMPERATURE,
    _has_novel_elements,
)


def test_constants_have_expected_values():
    assert PROMPT_VERSION == "v2"
    assert JUDGE_MODEL == "qwen/qwen3-32b"


def test_has_novel_elements_true_when_one_n():
    mappings = [
        {"element_number": 1, "novelty": "Y"},
        {"element_number": 2, "novelty": "N"},
    ]
    assert _has_novel_elements(mappings) is True


def test_has_novel_elements_false_when_all_y():
    mappings = [
        {"element_number": 1, "novelty": "Y"},
        {"element_number": 2, "novelty": "Y"},
    ]
    assert _has_novel_elements(mappings) is False


def test_has_novel_elements_false_when_empty():
    assert _has_novel_elements([]) is False


def test_has_novel_elements_false_when_novelty_missing():
    # Missing novelty field is treated as not novel (don't crash, don't false-positive).
    mappings = [{"element_number": 1}]
    assert _has_novel_elements(mappings) is False


from core.phosita_eval import needs_judge_call


def test_needs_judge_call_true_when_novel_elements():
    trace = {
        "parsed_output": {
            "element_mappings": [{"element_number": 1, "novelty": "N"}],
            "overall_opinion": "ok",
        }
    }
    assert needs_judge_call(trace) is True


def test_needs_judge_call_false_when_no_novel_elements():
    trace = {
        "parsed_output": {
            "element_mappings": [{"element_number": 1, "novelty": "Y"}],
            "overall_opinion": "ok",
        }
    }
    assert needs_judge_call(trace) is False


def test_needs_judge_call_false_when_no_parsed_output():
    assert needs_judge_call({"run_id": "x"}) is False
    assert needs_judge_call({"run_id": "x", "parsed_output": None}) is False


def test_needs_judge_call_false_when_empty_mappings():
    trace = {"parsed_output": {"element_mappings": [], "overall_opinion": "ok"}}
    assert needs_judge_call(trace) is False


from core.phosita_eval import _build_judge_prompt


_SAMPLE_PARSED = {
    "element_mappings": [
        {
            "element_number": 1,
            "element_text": "receiving an input",
            "corresponding_text": "receiving an input",
            "novelty": "Y",
            "inventive_step": "Y",
            "verdict": "Y",
            "comment": "Found in target claim verbatim.",
        },
        {
            "element_number": 2,
            "element_text": "applying a neural network",
            "corresponding_text": "",
            "novelty": "N",
            "inventive_step": "N",
            "verdict": "N",
            "comment": "Not disclosed in target. Novel.",
        },
    ],
    "overall_opinion": "Source patent is valid because element 2 is novel.",
}


def test_build_judge_prompt_returns_system_and_user():
    system, user = _build_judge_prompt(_SAMPLE_PARSED)
    assert isinstance(system, str) and isinstance(user, str)
    assert len(system) > 0 and len(user) > 0


def test_build_judge_prompt_system_defines_pass_and_fail():
    system, _ = _build_judge_prompt(_SAMPLE_PARSED)
    assert "PASS" in system
    assert "FAIL" in system


def test_build_judge_prompt_system_requires_json_output():
    system, _ = _build_judge_prompt(_SAMPLE_PARSED)
    assert "JSON" in system
    assert '"verdict"' in system
    assert '"comment"' in system
    assert '"opinion_check"' in system
    assert "has_psa_argument" in system


def test_build_judge_prompt_user_contains_only_overall_opinion():
    _, user = _build_judge_prompt(_SAMPLE_PARSED)
    # Overall opinion must be present.
    assert "Source patent is valid because element 2 is novel." in user
    # Element-level data must NOT be present in v2.
    assert "Not disclosed in target. Novel." not in user
    assert "element_number" not in user.lower()
    assert "novelty" not in user.lower()


def test_build_judge_prompt_handles_missing_overall_opinion():
    parsed = {"element_mappings": _SAMPLE_PARSED["element_mappings"]}
    system, user = _build_judge_prompt(parsed)
    # Empty/missing overall_opinion should not crash; should be marked clearly.
    assert "(no overall opinion provided)" in user.lower() or "overall opinion" in user.lower()


from types import SimpleNamespace

from core.phosita_eval import _call_judge


def _make_mock_client(content: str):
    """Build a fake Groq-style client that returns the given string as content."""
    client = MagicMock()
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    client.chat.completions.create.return_value = response
    return client


def test_call_judge_parses_valid_json():
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": False,
            "has_psa_argument": False,
            "note": "No PSA argument found.",
        },
        "verdict": "FAIL",
        "comment": "No PSA reasoning present.",
    }
    raw = json.dumps(payload)
    client = _make_mock_client(raw)
    parsed, returned_raw = _call_judge(client, "system", "user")
    assert parsed == payload
    assert returned_raw == raw


def test_call_judge_raises_on_invalid_json():
    client = _make_mock_client("not json at all")
    with pytest.raises(ValueError):
        _call_judge(client, "system", "user")


def test_call_judge_raises_when_opinion_check_missing():
    # Old v1-style response without opinion_check must raise ValueError.
    client = _make_mock_client('{"verdict": "PASS", "comment": "ok"}')
    with pytest.raises(ValueError, match="opinion_check"):
        _call_judge(client, "system", "user")


def test_call_judge_passes_model_temperature_max_tokens():
    payload = {
        "opinion_check": {"uses_psa_vocabulary": True, "has_psa_argument": True, "note": "ok"},
        "verdict": "PASS",
        "comment": "ok",
    }
    client = _make_mock_client(json.dumps(payload))
    _call_judge(client, "sys", "usr")
    call_args = client.chat.completions.create.call_args
    # Either positional or kwargs - assert via kwargs (Groq SDK uses kwargs).
    kwargs = call_args.kwargs
    assert kwargs["model"] == JUDGE_MODEL
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 1024
    assert kwargs["response_format"] == {"type": "json_object"}
    # Messages list contains the two prompts.
    msgs = kwargs["messages"]
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert msgs[1] == {"role": "user", "content": "usr"}


from core.phosita_eval import evaluate_trace


def _trace_with(parsed_output):
    return {"run_id": "test-rid", "parsed_output": parsed_output}


def test_evaluate_trace_returns_none_when_parsed_output_missing():
    assert evaluate_trace({"run_id": "x"}, MagicMock()) is None
    assert evaluate_trace({"run_id": "x", "parsed_output": None}, MagicMock()) is None


def test_evaluate_trace_pass_when_no_elements():
    trace = _trace_with({"element_mappings": [], "overall_opinion": "ok"})
    client = MagicMock()
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
    assert "N/A" in result["comment"]
    assert "no elements" in result["comment"].lower()
    # Judge MUST NOT be called when short-circuiting.
    client.chat.completions.create.assert_not_called()


def test_evaluate_trace_pass_when_no_novel_elements():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "Y", "inventive_step": "Y",
             "verdict": "Y", "comment": "found"},
            {"element_number": 2, "novelty": "Y", "inventive_step": "Y",
             "verdict": "Y", "comment": "found"},
        ],
        "overall_opinion": "All elements disclosed in target.",
    })
    client = MagicMock()
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
    assert "no novel elements" in result["comment"].lower()
    client.chat.completions.create.assert_not_called()


def test_evaluate_trace_calls_judge_when_novel_elements_present():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "Novel, not obvious."},
        ],
        "overall_opinion": "Element 1 is novel; source patent is valid.",
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": False,
            "has_psa_argument": False,
            "note": "Just a conclusion.",
        },
        "verdict": "FAIL",
        "comment": "No PSA reasoning.",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "FAIL"
    assert result["comment"] == "No PSA reasoning."
    assert result["run_id"] == "test-rid"
    assert result["eval_name"] == "absent_phosita_reasoning"
    assert result["config"] == {
        "judge_model": JUDGE_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": JUDGE_TEMPERATURE,
    }
    assert json.loads(result["judge_raw"])["opinion_check"]["has_psa_argument"] is False
    client.chat.completions.create.assert_called_once()


def test_evaluate_trace_pass_verdict_from_judge():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "Y",
             "verdict": "Y", "comment": "A PSA would find this obvious because..."},
        ],
        "overall_opinion": "Element 1 is novel but obvious; source patent invalid.",
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": True,
            "has_psa_argument": True,
            "note": "Explains why PSA would not combine.",
        },
        "verdict": "PASS",
        "comment": "PSA reasoning present.",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
    assert result["comment"] == "PSA reasoning present."


def test_evaluate_trace_returns_none_on_invalid_json(capsys):
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "novel"},
        ],
        "overall_opinion": "valid",
    })
    client = _make_mock_client("definitely not json")
    result = evaluate_trace(trace, client)
    assert result is None
    captured = capsys.readouterr()
    assert "test-rid" in captured.err


def test_evaluate_trace_returns_none_on_judge_exception(capsys):
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "novel"},
        ],
        "overall_opinion": "valid",
    })
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("network down")
    result = evaluate_trace(trace, client)
    assert result is None
    captured = capsys.readouterr()
    assert "test-rid" in captured.err
    assert "network down" in captured.err


def test_evaluate_trace_returns_none_on_invalid_verdict_string(capsys):
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "novel"},
        ],
        "overall_opinion": "valid",
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": False,
            "has_psa_argument": False,
            "note": "x",
        },
        "verdict": "MAYBE",
        "comment": "unsure",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result is None
    captured = capsys.readouterr()
    assert "MAYBE" in captured.err


def test_evaluate_trace_fail_when_no_psa_argument():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "Not disclosed."},
        ],
        "overall_opinion": "Element 1 is novel and non-obvious.",
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": True,
            "has_psa_argument": False,
            "note": "'novel and non-obvious' is a conclusion, not reasoning.",
        },
        "verdict": "FAIL",
        "comment": "PSA vocabulary present but no argument given.",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "FAIL"
    assert result["comment"] == "PSA vocabulary present but no argument given."


def test_evaluate_trace_pass_when_psa_argument_present():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "Not disclosed."},
        ],
        "overall_opinion": (
            "The feedback loop mechanism is entirely absent from prior art; "
            "a PSA cannot combine what does not exist."
        ),
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": False,
            "has_psa_argument": True,
            "note": "Complete technical absence documented — implicit PSA argument.",
        },
        "verdict": "PASS",
        "comment": "Complete absence of mechanism is an implicit PSA argument.",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
    assert result["comment"] == "Complete absence of mechanism is an implicit PSA argument."


import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_traces_jsonl(path: Path, traces: list[dict]):
    with open(path, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")


def test_runner_skips_traces_with_null_parsed_output(tmp_path, monkeypatch):
    """The runner must skip traces whose parsed_output is null without crashing."""
    traces_path = tmp_path / "traces.jsonl"
    out_path = tmp_path / "phosita_eval_full.jsonl"
    _write_traces_jsonl(traces_path, [
        {"run_id": "skip-1", "parsed_output": None},
        {"run_id": "skip-2"},  # no parsed_output key
    ])
    # No GROQ_API_KEY needed because no judge call happens for these short-circuits.
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-not-used")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_phosita_eval.py"),
         "--traces", str(traces_path),
         "--out", str(out_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"runner failed: {result.stderr}"
    # Output file may not exist if zero lines written - that's fine. If it exists, it's empty.
    if out_path.exists():
        assert out_path.read_text(encoding="utf-8").strip() == ""


def test_runner_short_circuits_no_novel_elements(tmp_path, monkeypatch):
    """Trace with all novelty=Y elements gets a PASS line written without judge call."""
    traces_path = tmp_path / "traces.jsonl"
    out_path = tmp_path / "phosita_eval_full.jsonl"
    _write_traces_jsonl(traces_path, [
        {
            "run_id": "all-y",
            "parsed_output": {
                "element_mappings": [
                    {"element_number": 1, "novelty": "Y", "inventive_step": "Y",
                     "verdict": "Y", "comment": "found"},
                ],
                "overall_opinion": "All disclosed.",
            },
        },
    ])
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-not-used")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_phosita_eval.py"),
         "--traces", str(traces_path),
         "--out", str(out_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"runner failed: {result.stderr}"
    lines = [json.loads(l) for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    assert lines[0]["run_id"] == "all-y"
    assert lines[0]["verdict"] == "PASS"
    assert lines[0]["config"]["prompt_version"] == PROMPT_VERSION


def test_runner_idempotent_cache_skips_already_evaluated(tmp_path, monkeypatch):
    """Second run with same prompt_version does not re-evaluate."""
    traces_path = tmp_path / "traces.jsonl"
    out_path = tmp_path / "phosita_eval_full.jsonl"
    _write_traces_jsonl(traces_path, [
        {
            "run_id": "all-y",
            "parsed_output": {
                "element_mappings": [
                    {"element_number": 1, "novelty": "Y", "inventive_step": "Y",
                     "verdict": "Y", "comment": "found"},
                ],
                "overall_opinion": "All disclosed.",
            },
        },
    ])
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-not-used")
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "run_phosita_eval.py"),
           "--traces", str(traces_path),
           "--out", str(out_path)]
    # First run.
    r1 = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert r1.returncode == 0
    first_contents = out_path.read_text(encoding="utf-8")
    # Second run on the same trace + version: file unchanged.
    r2 = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert r2.returncode == 0
    assert out_path.read_text(encoding="utf-8") == first_contents
    # Stdout should report 0 newly evaluated, 1 cached.
    assert "cached" in r2.stdout.lower() or "skipped" in r2.stdout.lower()
