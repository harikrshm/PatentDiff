"""The console's graphs must not show Plotly's white default before data lands."""
from dash import dcc

from app_workbench.app import build_console_body


def _graphs(node, acc=None):
    acc = [] if acc is None else acc
    if isinstance(node, dcc.Graph):
        acc.append(node)
    children = getattr(node, "children", None)
    for child in children if isinstance(children, (list, tuple)) else [children]:
        if child is not None and not isinstance(child, (str, int, float)):
            _graphs(child, acc)
    return acc


def test_every_console_graph_starts_transparent_and_axis_free():
    graphs = _graphs(build_console_body())
    assert {g.id for g in graphs} >= {"fr-gauge", "heatmap", "trajectory-chart"}
    for g in graphs:
        layout = g.figure.layout
        assert layout.paper_bgcolor == "rgba(0,0,0,0)", g.id
        assert layout.xaxis.visible is False and layout.yaxis.visible is False, g.id
