from datetime import datetime
from core.annotation import AnnotationRecord, ElementJudgment, OverallOpinionJudgment

def test_annotation_record_creation():
    """Test basic AnnotationRecord creation."""
    record = AnnotationRecord(
        run_id="test-id-123",
        phase=1,
        element_judgments=[],
        overall_opinion_judgment=OverallOpinionJudgment(
            tool_verdict="test",
            your_verdict="PASS",
            critique="good"
        ),
        open_coded_failure_modes=["hallucination"],
        failure_modes=None,
        annotation="Test annotation",
        reviewed=True,
    )
    assert record.run_id == "test-id-123"
    assert record.phase == 1
    assert len(record.element_judgments) == 0
    assert record.reviewed is True

def test_element_judgment_creation():
    """Test ElementJudgment creation."""
    judgment = ElementJudgment(
        element_number=1,
        tool_novelty=True,
        tool_inventive_step=False,
        your_verdict="PASS",
        critique="Good element"
    )
    assert judgment.element_number == 1
    assert judgment.tool_novelty is True

def test_annotation_to_dict():
    """Test AnnotationRecord serialization to dict."""
    record = AnnotationRecord(
        run_id="id1",
        phase=1,
        element_judgments=[
            ElementJudgment(
                element_number=1,
                tool_novelty=True,
                tool_inventive_step=False,
                your_verdict="PASS",
                critique="Good"
            )
        ],
        overall_opinion_judgment=OverallOpinionJudgment(
            tool_verdict="Similar",
            your_verdict="FAIL",
            critique="Incorrect"
        ),
        open_coded_failure_modes=["hallucination"],
        failure_modes=None,
        annotation="Test",
        reviewed=True,
    )

    d = record.to_dict()
    assert d["run_id"] == "id1"
    assert d["phase"] == 1
    assert len(d["element_judgments"]) == 1
    assert d["element_judgments"][0]["element_number"] == 1

def test_annotation_from_dict():
    """Test AnnotationRecord deserialization from dict."""
    data = {
        "run_id": "id1",
        "phase": 1,
        "element_judgments": [
            {
                "element_number": 1,
                "tool_novelty": True,
                "tool_inventive_step": False,
                "your_verdict": "PASS",
                "critique": "Good"
            }
        ],
        "overall_opinion_judgment": {
            "tool_verdict": "Similar",
            "your_verdict": "FAIL",
            "critique": "Incorrect"
        },
        "open_coded_failure_modes": ["hallucination"],
        "failure_modes": None,
        "annotation": "Test",
        "reviewed": True,
        "timestamp": "2026-04-24T10:00:00+00:00"
    }

    record = AnnotationRecord.from_dict(data)
    assert record.run_id == "id1"
    assert record.phase == 1
    assert len(record.element_judgments) == 1
