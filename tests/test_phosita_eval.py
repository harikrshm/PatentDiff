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
