import json

from core.models import AnalysisReport
from core.report import parse_llm_response


def test_parse_valid_json():
    raw = json.dumps({
        "element_mappings": [
            {
                "element_number": 1,
                "element_text": "a processor",
                "corresponding_text": "a CPU",
                "novelty": "Y",
                "inventive_step": "Y",
                "verdict": "Y",
                "comment": "Functionally equivalent.",
            }
        ],
        "overall_opinion": "Patent A lacks novelty for this element.",
    })
    report = parse_llm_response(raw)
    assert isinstance(report, AnalysisReport)
    assert len(report.element_mappings) == 1
    assert report.element_mappings[0].verdict == "Y"
    assert report.overall_opinion == "Patent A lacks novelty for this element."


def test_parse_multiple_elements():
    raw = json.dumps({
        "element_mappings": [
            {
                "element_number": 1,
                "element_text": "element A",
                "corresponding_text": "text A",
                "novelty": "Y",
                "inventive_step": "Y",
                "verdict": "Y",
                "comment": "Found.",
            },
            {
                "element_number": 2,
                "element_text": "element B",
                "corresponding_text": "",
                "novelty": "N",
                "inventive_step": "N",
                "verdict": "N",
                "comment": "Not found.",
            },
        ],
        "overall_opinion": "Mixed results.",
    })
    report = parse_llm_response(raw)
    assert len(report.element_mappings) == 2
    assert report.element_mappings[0].verdict == "Y"
    assert report.element_mappings[1].verdict == "N"


def test_parse_json_embedded_in_markdown():
    raw = '```json\n{"element_mappings": [{"element_number": 1, "element_text": "a processor", "corresponding_text": "a CPU", "novelty": "Y", "inventive_step": "Y", "verdict": "Y", "comment": "Match."}], "overall_opinion": "Lacks novelty."}\n```'
    report = parse_llm_response(raw)
    assert isinstance(report, AnalysisReport)
    assert len(report.element_mappings) == 1


def test_parse_invalid_json_raises():
    import pytest

    with pytest.raises(ValueError, match="Failed to parse"):
        parse_llm_response("this is not json at all")
