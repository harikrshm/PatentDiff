import pandas as pd

import core.experiment_agent_runner as runner
from core.experiment_agent import ProposedExperiment
from core.experiment_agent_runner import select_subset


def _frame():
    rows = []
    for i in range(5):
        rows.append(dict(run_id=f"m{i}", claim_type="Method", relationship="Genus-species"))
    for i in range(5):
        rows.append(dict(run_id=f"o{i}", claim_type="System", relationship="Overlapping"))
    return pd.DataFrame(rows)


def test_select_subset_targets_segment_plus_guardrail():
    ids = select_subset(_frame(), segment="Method × Genus-species", cap=8, guardrail=2)
    assert {"m0", "m1", "m2", "m3", "m4"}.issubset(set(ids))
    assert len(ids) <= 8
    assert any(i.startswith("o") for i in ids)


def test_select_subset_unknown_segment_returns_empty():
    assert select_subset(_frame(), segment="No × Such") == []


# ---------------------------------------------------------------------------
# Task 7: run_stage
# ---------------------------------------------------------------------------

def _exp():
    return ProposedExperiment(order=1, target_eval="citation",
                              target_segment="Method × Genus-species",
                              prompt_block="Quote verbatim.", predicted_delta_pp=-40.0,
                              rationale="x", cited_run_ids=[])


def test_run_stage_composes_block_and_gates(monkeypatch):
    captured = {}

    def fake_regen(trace, system_prompt):
        captured["system"] = system_prompt
        return {"run_id": trace["run_id"], "parsed_output": {"element_mappings": []}}

    monkeypatch.setattr(runner, "regenerate_one", fake_regen)
    monkeypatch.setattr(runner, "score_citation", lambda tr: "PASS")
    monkeypatch.setattr(runner, "score_phosita", lambda tr, client: "PASS")
    monkeypatch.setattr(runner, "build_system_prompt",
                        lambda extra_instructions="": f"BASE|{extra_instructions}")

    subset = [{"run_id": "m0", "inputs": {}}, {"run_id": "m1", "inputs": {}}]
    before = {"m0": {"citation": "FAIL", "phosita": "PASS"},
              "m1": {"citation": "FAIL", "phosita": "PASS"}}

    result = runner.run_stage(_exp(), kept_block="PRIOR", subset_traces=subset,
                              before_verdicts=before, judge_client=object(),
                              cell_of={"m0": "Method × Genus-species",
                                       "m1": "Method × Genus-species"})

    assert captured["system"] == "BASE|PRIOR\n\nQuote verbatim."
    assert result.before == 100.0
    assert result.after == 0.0
    assert result.gate.passed is True
    assert result.coverage == "ran 2/2"
    assert result.new_block == "PRIOR\n\nQuote verbatim."


# ---------------------------------------------------------------------------
# Task 8: keep_stage
# ---------------------------------------------------------------------------

import json
from core.experiment_agent_runner import keep_stage


def test_keep_stage_appends_manifest_row(tmp_path):
    manifest = tmp_path / "experiments.jsonl"
    keep_stage(exp_id="agent-1", name="Agent: verbatim (Method × Genus-species)",
               created="2026-06-20T10:00:00Z",
               phosita_eval_file="phosita_eval_full.agent-1.jsonl",
               citation_eval_file="citation_text_eval_full.agent-1.jsonl",
               manifest_path=manifest)
    lines = manifest.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["exp_id"] == "agent-1"
    assert row["name"].startswith("Agent:")
