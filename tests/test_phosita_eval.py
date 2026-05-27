import json
from unittest.mock import MagicMock

import pytest

from core.phosita_eval import (
    PROMPT_VERSION,
    JUDGE_MODEL,
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
