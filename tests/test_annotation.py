from datetime import datetime
import tempfile
from pathlib import Path
import json
from core.annotation import AnnotationRecord, load_annotations, save_annotations
from core.trace_loader import load_traces, Trace

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

def test_load_empty_annotations():
    """Test loading from non-existent file returns empty dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "annotations.jsonl"
        annotations = load_annotations(path)
        assert annotations == {}

def test_load_annotations_from_jsonl():
    """Test loading annotations from JSONL file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "annotations.jsonl"

        # Write test data
        record1 = {
            "run_id": "id1",
            "phase": 1,
            "element_judgments": [],
            "overall_opinion_judgment": {
                "tool_verdict": "test",
                "your_verdict": "PASS",
                "critique": "ok"
            },
            "open_coded_failure_modes": ["mode1"],
            "failure_modes": None,
            "annotation": "annotation1",
            "reviewed": True,
            "timestamp": "2026-04-24T10:00:00+00:00"
        }
        with open(path, "w") as f:
            f.write(json.dumps(record1) + "\n")

        annotations = load_annotations(path)
        assert len(annotations) == 1
        assert annotations["id1"].run_id == "id1"
        assert annotations["id1"].phase == 1

def test_save_annotations():
    """Test saving annotations to JSONL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "annotations.jsonl"

        record = AnnotationRecord(
            run_id="id1",
            phase=1,
            element_judgments=[],
            overall_opinion_judgment=OverallOpinionJudgment(
                tool_verdict="test",
                your_verdict="PASS",
                critique="ok"
            ),
            open_coded_failure_modes=["mode1"],
            failure_modes=None,
            annotation="test",
            reviewed=True,
        )

        save_annotations(path, {"id1": record})

        # Verify file exists and contains data
        assert path.exists()
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        loaded = json.loads(lines[0])
        assert loaded["run_id"] == "id1"

def test_load_traces_from_jsonl():
    """Test loading traces from traces.jsonl."""
    traces = load_traces(Path("C:/Users/91978/PatentDiff/traces/traces.jsonl"))
    assert len(traces) > 0
    assert all(isinstance(t, Trace) for t in traces)
    # Check first trace has required fields
    first = traces[0]
    assert hasattr(first, "run_id")
    assert hasattr(first, "inputs")
    assert hasattr(first, "parsed_output")

def test_annotation_record_simplified():
    """Test simplified AnnotationRecord with verdict and comment."""
    record = AnnotationRecord(
        run_id="test-id-123",
        phase=1,
        open_coded_failure_modes=["hallucination", "truncation"],
        verdict="FAIL",
        comment="Tool hallucinated correspondence in element 3.",
        reviewed=True,
    )
    assert record.run_id == "test-id-123"
    assert record.verdict == "FAIL"
    assert len(record.open_coded_failure_modes) == 2
    assert record.comment == "Tool hallucinated correspondence in element 3."

def test_parse_failure_modes():
    """Test parsing delimited failure modes."""
    from core.annotation import parse_failure_modes

    result = parse_failure_modes("hallucination | truncation | claim_mismatch")
    assert result == ["hallucination", "truncation", "claim_mismatch"]

    result = parse_failure_modes("mode1")
    assert result == ["mode1"]

    result = parse_failure_modes("")
    assert result == []
