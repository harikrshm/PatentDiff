from pathlib import Path

from core.eval_runner import build_eval_commands, eval_for_set
from core.workbench_data import TraceSet


def test_build_eval_commands_targets_the_selected_set():
    ts = TraceSet(
        name="exp1",
        traces_path=Path("traces/traces.exp1.jsonl"),
        phosita_path=Path("traces/phosita_eval_full.exp1.jsonl"),
        citation_path=Path("traces/citation_text_eval_full.exp1.jsonl"),
    )
    cmds = build_eval_commands(ts)

    assert len(cmds) == 2
    citation_cmd, phosita_cmd = cmds[0], cmds[1]
    assert "run_citation_eval.py" in " ".join(citation_cmd)
    assert "run_phosita_eval.py" in " ".join(phosita_cmd)
    # each command points --traces / --out at the selected set's files
    assert str(ts.traces_path) in citation_cmd
    assert str(ts.citation_path) in citation_cmd
    assert str(ts.phosita_path) in phosita_cmd


def test_eval_for_set_bogus_name_returns_guard_message(tmp_path: Path):
    # Empty tmp_path has no phosita_eval_full.jsonl — no sets discovered.
    result = eval_for_set("bogus-set", tmp_path)
    assert result == "No such trace set."
