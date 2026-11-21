import core.regeneration as regen


_TRACE = {
    "run_id": "abc123",
    "inputs": {
        "source_patent": {"label": "A", "independent_claim": "a claim", "specification": "spec a"},
        "target_patent": {"label": "B", "independent_claim": "b claim", "specification": "spec b"},
    },
}

_GROQ_OK = {
    "raw_output": '{"element_mappings": [{"element_number": 1, "element_text": "x", '
                  '"corresponding_text": "y", "novelty": "N", "inventive_step": "N", '
                  '"verdict": "N", "comment": "c"}], "overall_opinion": "ok"}',
    "model": "stub", "tokens_input": 1, "tokens_output": 1, "latency_ms": 5,
}


def test_regenerate_one_uses_given_system_prompt(monkeypatch):
    captured = {}

    def fake_call_groq(system_prompt, user_prompt, model=None):
        captured["system"] = system_prompt
        return _GROQ_OK

    monkeypatch.setattr(regen, "call_groq", fake_call_groq)
    out = regen.regenerate_one(_TRACE, "SYSTEM PROMPT WITH BLOCK")

    assert captured["system"] == "SYSTEM PROMPT WITH BLOCK"
    assert out["run_id"] == "abc123"
    assert out["status"] == "ok"
    assert out["parsed_output"]["overall_opinion"] == "ok"
    assert out["prompt"]["system_prompt"] == "SYSTEM PROMPT WITH BLOCK"
