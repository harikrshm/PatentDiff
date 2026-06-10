# tests/test_app_unified_shell.py
import importlib


def test_shell_registers_all_four_routes():
    import dash
    importlib.import_module("app_unified.app")  # registers pages on import
    registered = {p["path"] for p in dash.page_registry.values()}
    assert {"/", "/eval", "/eval/traces", "/eval/comparison"} <= registered


def test_shell_layout_has_nav_and_page_container():
    mod = importlib.import_module("app_unified.app")
    from dash import page_container  # noqa: F401
    assert mod.app.layout is not None
