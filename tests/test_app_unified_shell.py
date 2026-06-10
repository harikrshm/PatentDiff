# tests/test_app_unified_shell.py
import importlib


def test_shell_registers_all_four_routes():
    import dash
    importlib.import_module("app_unified.app")  # registers pages on import
    registered = {p["path"] for p in dash.page_registry.values()}
    assert {"/", "/eval", "/eval/traces", "/eval/comparison"} <= registered


def test_shell_layout_has_nav_and_page_container():
    mod = importlib.import_module("app_unified.app")
    layout_str = str(mod.app.layout)
    assert "uw-sidebar" in layout_str        # persistent left sidebar (T2)
    assert "uw-toolbar" in layout_str        # top contextual toolbar (T2)
    assert "_pages_content" in layout_str    # page_container is present


def test_sidebar_marks_active_route():
    from app_unified.components import sidebar_nav

    # The active route gets the is-active class; others do not.
    eval_nav = str(sidebar_nav("/eval"))
    assert "uw-nav__item is-active" in eval_nav
    # Sub-routes own their own active state; /eval is not active on /eval/traces.
    traces_nav = sidebar_nav("/eval/traces")
    active = [c for c in traces_nav
             if getattr(c, "href", None) and "is-active" in c.className]
    assert [c.href for c in active] == ["/eval/traces"]
