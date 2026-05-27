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
    assert PROMPT_VERSION == "v1"
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
    # Both verdicts named in the rubric definition.
    assert "PASS" in system
    assert "FAIL" in system
    # Scope filter on novelty=Y elements documented.
    assert "novelty=Y" in system or "novelty = Y" in system


def test_build_judge_prompt_system_requires_json_output():
    system, _ = _build_judge_prompt(_SAMPLE_PARSED)
    assert "JSON" in system
    assert '"verdict"' in system
    assert '"comment"' in system


def test_build_judge_prompt_user_contains_overall_opinion():
    _, user = _build_judge_prompt(_SAMPLE_PARSED)
    assert "Source patent is valid because element 2 is novel." in user


def test_build_judge_prompt_user_contains_element_data():
    _, user = _build_judge_prompt(_SAMPLE_PARSED)
    # Element-level details the judge needs.
    assert "element_number" in user or "Element 1" in user or "1:" in user
    assert "Not disclosed in target. Novel." in user  # element 2's comment
    assert "novelty" in user.lower()
    assert "inventive_step" in user.lower() or "inventive step" in user.lower()


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
    client = _make_mock_client('{"verdict": "PASS", "comment": "Good reasoning."}')
    parsed, raw = _call_judge(client, "system", "user")
    assert parsed == {"verdict": "PASS", "comment": "Good reasoning."}
    assert raw == '{"verdict": "PASS", "comment": "Good reasoning."}'


def test_call_judge_raises_on_invalid_json():
    client = _make_mock_client("not json at all")
    with pytest.raises(ValueError):
        _call_judge(client, "system", "user")


def test_call_judge_passes_model_temperature_max_tokens():
    client = _make_mock_client('{"verdict": "PASS", "comment": "ok"}')
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
    client = _make_mock_client('{"verdict": "FAIL", "comment": "No PSA reasoning."}')
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "FAIL"
    assert result["comment"] == "No PSA reasoning."
    assert result["run_id"] == "test-rid"
    assert result["eval_name"] == "absent_phosita_reasoning"
    assert result["judge_raw"] == '{"verdict": "FAIL", "comment": "No PSA reasoning."}'
    assert result["config"] == {
        "judge_model": JUDGE_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": JUDGE_TEMPERATURE,
    }
    client.chat.completions.create.assert_called_once()


def test_evaluate_trace_pass_verdict_from_judge():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "Y",
             "verdict": "Y", "comment": "A PSA would find this obvious because..."},
        ],
        "overall_opinion": "Element 1 is novel but obvious; source patent invalid.",
    })
    client = _make_mock_client('{"verdict": "PASS", "comment": "PSA reasoning present."}')
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
    assert result["comment"] == "PSA reasoning present."
