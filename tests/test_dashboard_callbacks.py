"""Dashboard (/eval) callbacks: deep-link defaults + Block-1 trace metadata."""
import app_workbench.callbacks as cb


def test_apply_deep_link_sets_concrete_defaults_on_load():
    # Empty search must SET concrete values (not no_update) so the blocks that
    # read corpus-selector.value actually fire on a fresh load.
    out_set, out_eval = cb.apply_deep_link("")
    assert out_set == "live"
    assert out_eval == "phosita"


def test_apply_deep_link_passes_valid_params():
    out_set, out_eval = cb.apply_deep_link("?eval=citation")
    assert out_eval == "citation"
    # invalid eval falls back to the default, never no_update
    assert cb.apply_deep_link("?eval=bogus")[1] == "phosita"


def test_render_trace_meta_empty_when_no_history(tmp_path, monkeypatch):
    import core.eval_history as eh
    monkeypatch.setattr(cb, "history_for",
                        lambda kind, trace_set=None: eh.history_for(
                            kind, trace_set, path=tmp_path / "none.jsonl"))
    out = cb.render_trace_meta("live", 0)
    # a single calm caption span, not the per-eval pairs
    assert getattr(out, "className", "") == "wb-caption"


def test_render_trace_meta_lists_each_eval_kind(tmp_path, monkeypatch):
    import core.eval_history as eh
    h = tmp_path / "h.jsonl"
    eh.append_run([
        eh.HistoryRecord(timestamp="2026-06-01T10:00:00", eval_kind="phosita",
                         trace_set="live", pass_rate=0.5, scored=80,
                         prompt_version="v3", run_id="a"),
        eh.HistoryRecord(timestamp="2026-06-01T10:00:00", eval_kind="citation",
                         trace_set="live", pass_rate=0.6, scored=70,
                         prompt_version=None, run_id="a"),
    ], path=h)
    monkeypatch.setattr(cb, "history_for",
                        lambda kind, trace_set=None: eh.history_for(
                            kind, trace_set, path=h))
    out = cb.render_trace_meta("live", 0)
    text = str(out)
    assert "Phosita" in text and "Citation" in text
    assert "50% PASS" in text and "n=80" in text and "v3" in text


def test_render_kpi_vs_target_shows_gap_and_no_target(monkeypatch):
    from core.kpi_targets import Target
    monkeypatch.setattr(cb, "current_pass_rate",
                        lambda d, s, kind: (0.54, 89) if kind == "phosita" else (0.45, 71))
    monkeypatch.setattr(cb, "get_target",
                        lambda kind: Target(target_pass_rate=0.85, target_date="2026-09-01")
                        if kind == "phosita" else None)
    out = cb.render_kpi_vs_target("live", 0, 0)
    assert len(out) == 2
    text = str(out)
    assert "target 85%" in text and "-31 pp" in text   # phosita gap
    assert "uw-kt__gap--bad" in text                    # below target
    assert "No target set" in text                      # citation
