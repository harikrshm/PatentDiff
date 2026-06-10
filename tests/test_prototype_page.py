from unittest.mock import patch

from app_unified.pages import prototype


def test_run_analysis_appends_trace_and_returns_report(tmp_path, monkeypatch):
    fake_llm = {
        "raw_output": "ELEMENT 1 ...", "model": "test-model",
        "tokens_input": 10, "tokens_output": 20, "latency_ms": 5,
    }
    appended = {}

    def fake_append(trace):
        appended["trace"] = trace

    with patch.object(prototype, "call_groq", return_value=fake_llm), \
         patch.object(prototype, "parse_llm_response") as fake_parse, \
         patch.object(prototype, "append_trace", side_effect=fake_append):
        fake_parse.return_value.element_mappings = []
        fake_parse.return_value.overall_opinion = "No overlap."
        status, report_children, meta = prototype.run_analysis(
            "US-A", "claim a", "spec a", "US-B", "claim b", "spec b",
        )

    assert appended["trace"]["status"] == "success"
    assert appended["trace"]["inputs"]["source_patent"]["label"] == "US-A"
    assert status == ""  # no error banner


def test_run_analysis_rejects_missing_fields():
    status, report_children, meta = prototype.run_analysis(
        "US-A", "", "spec a", "US-B", "claim b", "spec b",
    )
    assert "fill in all fields" in status.lower()
