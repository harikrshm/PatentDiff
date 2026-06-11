"""Review tab — trace coverage counts."""
from types import SimpleNamespace

from core.annotation import AnnotationRecord
from app_unified.pages import eval_review as r


def test_review_progress_counts(monkeypatch):
    traces = [SimpleNamespace(run_id=f"r{i}") for i in range(5)]
    anns = {
        "r0": AnnotationRecord(run_id="r0", phase=3, verdict="PASS",
                               comment="ok", reviewed=True),
        "r1": AnnotationRecord(run_id="r1", phase=3, verdict="FAIL",
                               failure_modes=["m"], comment="x", reviewed=True),
        "r2": AnnotationRecord(run_id="r2", phase=3, verdict="PASS",
                               comment="x", reviewed=False),  # annotated, not reviewed
        # r3, r4 untouched
    }
    monkeypatch.setattr(r, "load_traces", lambda f: traces)
    monkeypatch.setattr(r, "load_annotations", lambda f: anns)

    p = r.review_progress()
    assert p["total"] == 5
    assert p["reviewed"] == 2                  # r0, r1
    assert p["annotated_not_reviewed"] == 1    # r2
    assert p["untouched"] == 2                 # r3, r4
    assert set(p["unreviewed"]) == {"r2", "r3", "r4"}


def test_review_route_registered():
    import dash
    paths = {p["path"] for p in dash.page_registry.values()}
    assert "/eval/review" in paths
