"""Tests for core/dimension_tagger.py."""
import pytest

from core.dimension_tagger import (
    infer_claim_length,
    infer_claim_type,
    infer_relationship,
    tag_trace,
)


def _trace_with_claim(claim: str) -> dict:
    return {"inputs": {"source_patent": {"independent_claim": claim}}}


def _trace_with_elements(novelty_list: list[str]) -> dict:
    return {
        "parsed_output": {
            "element_mappings": [
                {"element_number": i + 1, "novelty": n}
                for i, n in enumerate(novelty_list)
            ]
        }
    }


# --- infer_claim_type ---


def test_infer_claim_type_method_simple():
    assert infer_claim_type(_trace_with_claim("A method comprising:\nreceiving data")) == "Method"


def test_infer_claim_type_method_computer_implemented():
    assert (
        infer_claim_type(_trace_with_claim("A computer-implemented method, comprising:\nprocessing"))
        == "Method"
    )


def test_infer_claim_type_method_with_leading_number():
    assert (
        infer_claim_type(_trace_with_claim("1. A method for processing, the method comprising:"))
        == "Method"
    )


def test_infer_claim_type_method_performed_by():
    assert (
        infer_claim_type(_trace_with_claim("A method performed by one or more computers, comprising:"))
        == "Method"
    )


def test_infer_claim_type_system():
    assert infer_claim_type(_trace_with_claim("A system comprising:\nat least one processor")) == "System"


def test_infer_claim_type_apparatus():
    assert (
        infer_claim_type(_trace_with_claim("An apparatus for encoding audio, comprising:\none or more processors"))
        == "System"
    )


def test_infer_claim_type_article():
    assert (
        infer_claim_type(_trace_with_claim("An abrasive article comprising:\na backing"))
        == "System"
    )


def test_infer_claim_type_unknown_empty():
    assert infer_claim_type(_trace_with_claim("")) == "Unknown"


def test_infer_claim_type_unknown_no_inputs():
    assert infer_claim_type({}) == "Unknown"


# --- infer_claim_length ---


def test_infer_claim_length_short_four_elements():
    assert infer_claim_length(_trace_with_elements(["Y", "N", "Y", "N"])) == "Short"


def test_infer_claim_length_short_five_elements():
    # Spec: Short = ≤5 elements
    assert infer_claim_length(_trace_with_elements(["Y"] * 5)) == "Short"


def test_infer_claim_length_long_six_elements():
    assert infer_claim_length(_trace_with_elements(["Y"] * 6)) == "Long"


def test_infer_claim_length_long_ten_elements():
    assert infer_claim_length(_trace_with_elements(["N"] * 10)) == "Long"


def test_infer_claim_length_short_no_parsed_output():
    # Zero elements → Short
    assert infer_claim_length({}) == "Short"


# --- infer_relationship ---


def test_infer_relationship_anticipation_all_y():
    # 100% Y → Anticipation
    assert infer_relationship(_trace_with_elements(["Y", "Y", "Y", "Y"])) == "Anticipation"


def test_infer_relationship_anticipation_mostly_y():
    # 75% Y (≥0.60) → Anticipation
    assert infer_relationship(_trace_with_elements(["Y", "Y", "Y", "N"])) == "Anticipation"


def test_infer_relationship_novel_all_n():
    # 0% Y → Novel
    assert infer_relationship(_trace_with_elements(["N", "N", "N", "N"])) == "Novel"


def test_infer_relationship_novel_mostly_n():
    # 25% Y (≤0.25) → Novel
    assert infer_relationship(_trace_with_elements(["Y", "N", "N", "N"])) == "Novel"


def test_infer_relationship_implicit_mixed():
    # 40% Y → Implicit
    assert infer_relationship(_trace_with_elements(["Y", "Y", "N", "N", "N"])) == "Implicit"


def test_infer_relationship_implicit_half():
    # 50% Y → Implicit
    assert infer_relationship(_trace_with_elements(["Y", "Y", "N", "N"])) == "Implicit"


def test_infer_relationship_unknown_no_elements():
    assert infer_relationship({}) == "Unknown"
    assert infer_relationship({"parsed_output": {"element_mappings": []}}) == "Unknown"


# --- tag_trace ---


def test_tag_trace_returns_all_dimensions_and_source():
    trace = {
        "inputs": {"source_patent": {"independent_claim": "A method comprising:\nreceiving data"}},
        "parsed_output": {
            "element_mappings": [
                {"element_number": 1, "novelty": "Y"},
                {"element_number": 2, "novelty": "N"},
            ]
        },
    }
    result = tag_trace(trace)
    assert result["claim_type"] == "Method"
    assert result["claim_length"] == "Short"   # 2 elements ≤ 5
    assert result["relationship"] == "Implicit"  # 50% Y
    assert result["source"] == "inferred"


def test_tag_trace_empty_trace():
    result = tag_trace({})
    assert result["claim_type"] == "Unknown"
    assert result["claim_length"] == "Short"
    assert result["relationship"] == "Unknown"
    assert result["source"] == "inferred"
