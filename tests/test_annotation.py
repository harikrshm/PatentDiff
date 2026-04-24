from datetime import datetime
import tempfile
from pathlib import Path
import json
from core.annotation import AnnotationRecord, load_annotations, save_annotations
from core.trace_loader import load_traces, Trace

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
            "open_coded_failure_modes": ["mode1"],
            "verdict": "PASS",
            "comment": "annotation1",
            "reviewed": True,
            "timestamp": "2026-04-24T10:00:00+00:00"
        }
        with open(path, "w") as f:
            f.write(json.dumps(record1) + "\n")

        annotations = load_annotations(path)
        assert len(annotations) == 1
        assert annotations["id1"].run_id == "id1"
        assert annotations["id1"].phase == 1

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
