# tests/conftest.py
# Bootstrap the Dash app before any test module is imported.
# dash.register_page() requires an app instance to exist; importing
# app_unified.app here (at conftest load time, before test collection)
# satisfies that requirement for page-level unit tests.
import app_unified.app  # noqa: F401
