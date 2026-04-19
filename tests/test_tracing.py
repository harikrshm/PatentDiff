import json
import os
import tempfile

from core.models import AnalysisReport, ElementMapping, PatentInput
from tracing.logger import build_trace_record
from tracing.store import append_trace


def _sample_inputs():
    return {
        "source_patent": PatentInput(
            label="Patent A",
            independent_claim="A method comprising step X.",
            specification="Step X does something.",
        ),
        "target_patent": PatentInput(
            label="Patent B",
            independent_claim="A method comprising step Y.",
            specification="Step Y does something else.",
        ),
    }


def _sample_report():
    return AnalysisReport(
        element_mappings=[
            ElementMapping(
                element_number=1,
                element_text="step X",
                corresponding_text="step Y",
                novelty="Y",
                inventive_step="N",
                verdict="N",
                comment="Novel technical improvement.",
            )
        ],
        overall_opinion="Patent A has inventive step.",
    )


def test_build_trace_record_success():
    inputs = _sample_inputs()
    record = build_trace_record(
        source_patent=inputs["source_patent"],
        target_patent=inputs["target_patent"],
        system_prompt="sys",
        user_prompt="usr",
        llm_response={"raw_output": "{}", "model": "test", "tokens_input": 10, "tokens_output": 20, "latency_ms": 100},
        parsed_output=_sample_report(),
        status="success",
        error=None,
    )
    assert record["status"] == "success"
    assert record["run_id"] is not None
    assert record["timestamp"] is not None
    assert record["inputs"]["source_patent"]["label"] == "Patent A"
    assert record["prompt"]["system_prompt"] == "sys"
    assert record["llm_response"]["model"] == "test"
    assert record["parsed_output"]["overall_opinion"] == "Patent A has inventive step."
    assert record["error"] is None


def test_build_trace_record_error():
    inputs = _sample_inputs()
    record = build_trace_record(
        source_patent=inputs["source_patent"],
        target_patent=inputs["target_patent"],
        system_prompt="sys",
        user_prompt="usr",
        llm_response={"raw_output": "broken", "model": "test", "tokens_input": 10, "tokens_output": 0, "latency_ms": 50},
        parsed_output=None,
        status="error",
        error="JSON parse failed",
    )
    assert record["status"] == "error"
    assert record["error"] == "JSON parse failed"
    assert record["parsed_output"] is None


def test_append_trace_creates_file_and_appends():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "traces.jsonl")
        inputs = _sample_inputs()
        record = build_trace_record(
            source_patent=inputs["source_patent"],
            target_patent=inputs["target_patent"],
            system_prompt="sys",
            user_prompt="usr",
            llm_response={"raw_output": "{}", "model": "test", "tokens_input": 10, "tokens_output": 20, "latency_ms": 100},
            parsed_output=_sample_report(),
            status="success",
            error=None,
        )
        append_trace(record, filepath)
        append_trace(record, filepath)

        with open(filepath, "r") as f:
            lines = f.readlines()
        assert len(lines) == 2
        parsed = json.loads(lines[0])
        assert parsed["status"] == "success"
        assert parsed["inputs"]["source_patent"]["label"] == "Patent A"


def test_build_trace_record_includes_truncation_warnings():
    inputs = _sample_inputs()
    record = build_trace_record(
        source_patent=inputs["source_patent"],
        target_patent=inputs["target_patent"],
        system_prompt="sys",
        user_prompt="usr",
        llm_response={"raw_output": "{}", "model": "test", "tokens_input": 10, "tokens_output": 20, "latency_ms": 100},
        parsed_output=_sample_report(),
        status="success",
        error=None,
        truncation_warnings=["Patent A specification truncated"],
    )
    assert record["truncation_warnings"] == ["Patent A specification truncated"]


def test_build_trace_record_empty_truncation_warnings():
    inputs = _sample_inputs()
    record = build_trace_record(
        source_patent=inputs["source_patent"],
        target_patent=inputs["target_patent"],
        system_prompt="sys",
        user_prompt="usr",
        llm_response={"raw_output": "{}", "model": "test", "tokens_input": 10, "tokens_output": 20, "latency_ms": 100},
        parsed_output=_sample_report(),
        status="success",
        error=None,
        truncation_warnings=[],
    )
    assert record["truncation_warnings"] == []
