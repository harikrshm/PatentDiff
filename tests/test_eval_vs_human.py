import subprocess
import sys
from pathlib import Path

from core.eval_vs_human import classify_coded, classify_human, confusion, tpr, tnr

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cli_smoke_runs_and_writes_report(tmp_path, monkeypatch):
    # Run the CLI as a subprocess against the real repo state.
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_eval_vs_human.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    report_path = REPO_ROOT / "traces" / "eval_vs_human_report.md"
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "TPR" in text
    assert "TNR" in text
    assert "Confusion matrix" in text
    # 30 human-annotated traces in sample
    assert "30 human-annotated" in text


def test_classify_coded_pass_is_negative():
    assert classify_coded("PASS") == 0


def test_classify_coded_no_citations_is_negative():
    assert classify_coded("NO_CITATIONS") == 0


def test_classify_coded_fail_is_positive():
    assert classify_coded("FAIL") == 1


def test_classify_human_citation_text_is_positive():
    assert classify_human(["citation_text"]) == 1


def test_classify_human_other_mode_is_negative():
    assert classify_human(["absent_phosita_reasoning"]) == 0


def test_classify_human_empty_is_negative():
    assert classify_human([]) == 0
    assert classify_human(None) == 0


def test_classify_human_multi_label_with_citation_text():
    assert classify_human(["citation_text", "absent_phosita_reasoning"]) == 1


def test_confusion_counts():
    # (human_label, coded_label)
    pairs = [
        (1, 1),  # TP
        (1, 1),  # TP
        (0, 1),  # FP
        (1, 0),  # FN
        (0, 0),  # TN
        (0, 0),  # TN
        (0, 0),  # TN
    ]
    c = confusion(pairs)
    assert c == {"tp": 2, "fp": 1, "fn": 1, "tn": 3}


def test_tpr_normal():
    assert tpr(tp=3, fn=1) == 0.75


def test_tpr_zero_denominator_returns_none():
    assert tpr(tp=0, fn=0) is None


def test_tnr_normal():
    assert tnr(tn=7, fp=3) == 0.7


def test_tnr_zero_denominator_returns_none():
    assert tnr(tn=0, fp=0) is None
