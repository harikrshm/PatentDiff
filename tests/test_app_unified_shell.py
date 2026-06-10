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
    assert "uw-topnav" in layout_str        # top_nav() is present
    assert "_pages_content" in layout_str   # page_container is present
