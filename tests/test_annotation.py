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

def test_annotation_to_dict_simplified():
    """Test simplified AnnotationRecord serialization to dict."""
    record = AnnotationRecord(
        run_id="id1",
        phase=1,
        open_coded_failure_modes=["hallucination"],
        verdict="FAIL",
        comment="Tool hallucinated",
        reviewed=True,
    )

    d = record.to_dict()
    assert d["run_id"] == "id1"
    assert d["phase"] == 1
    assert d["verdict"] == "FAIL"
    assert d["comment"] == "Tool hallucinated"
    assert d["open_coded_failure_modes"] == ["hallucination"]

def test_annotation_from_dict_simplified():
    """Test simplified AnnotationRecord deserialization from dict."""
    data = {
        "run_id": "id1",
        "phase": 1,
        "open_coded_failure_modes": ["hallucination"],
        "verdict": "FAIL",
        "comment": "Tool hallucinated",
        "reviewed": True,
        "timestamp": "2026-04-24T10:00:00+00:00"
    }

    record = AnnotationRecord.from_dict(data)
    assert record.run_id == "id1"
    assert record.verdict == "FAIL"
    assert record.comment == "Tool hallucinated"

def test_annotation_with_dimensions():
    """Test that dimensions are preserved in annotations"""
    data = {
        "run_id": "test-123",
        "phase": 3,
        "dimensions": {
            "claim_type": "independent",
            "claim_length": "medium",
            "relationship": "similar_domain"
        },
        "verdict": "FAIL",
        "failure_modes": ["failed_claim_construction"],
        "open_coded_failure_modes": ["big_claim"],
        "comment": "Test comment",
        "reviewed": True,
        "timestamp": "2026-04-27T10:00:00"
    }

    record = AnnotationRecord.from_dict(data)
    assert record.dimensions == data["dimensions"]
    assert record.failure_modes == ["failed_claim_construction"]
    assert record.to_dict()["dimensions"] == data["dimensions"]

def test_pass_verdict_with_failure_modes():
    """Test that PASS verdict with failure modes is recorded (UI should prevent)"""
    data = {
        "run_id": "test-124",
        "phase": 3,
        "verdict": "PASS",
        "failure_modes": ["failed_claim_construction"],
        "comment": "Test",
        "reviewed": True
    }

    # Data model allows this; UI validation should prevent it
    record = AnnotationRecord.from_dict(data)
    assert record.verdict == "PASS"
    assert record.failure_modes == ["failed_claim_construction"]

def test_fail_verdict_without_failure_modes():
    """Test that FAIL verdict without failure modes is recorded (UI should prevent)"""
    data = {
        "run_id": "test-125",
        "phase": 3,
        "verdict": "FAIL",
        "failure_modes": [],
        "comment": "Test",
        "reviewed": True
    }

    # Data model allows this; UI validation should prevent it
    record = AnnotationRecord.from_dict(data)
    assert record.verdict == "FAIL"
    assert len(record.failure_modes) == 0
