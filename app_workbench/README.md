# Eval Workbench (Dash)

Interactive eval workbench: how-bad → where → why-layer → what-to-fix-first.

## Run

    pip install -r requirements.txt
    python -m app_workbench.app

Open http://127.0.0.1:8050.

## Surfaces
- **Explore** — corpus selector, Run-eval, KPI tiles, drag-drop pivot heatmap, shape-read hypothesis. Widgets are draggable/resizable; layout persists.
- **Decision** — Impact (per mode) + Exposure (per cell) inputs → live Frequency × Impact × Exposure priority table; PM assigns the architecture layer and records the decision rationale.

## Principle
The app guides; the PM decides. Every derived insight shows a templated
HYPOTHESIS plus the number behind it. Final layer / priority / decision are PM
inputs, persisted under `traces/workbench_state/` (git-ignored).

## Notes
- Reads existing eval sets only; does not generate traces.
- "Run eval" re-runs the existing scripts on the selected set (needs `GROQ_API_KEY` for PHOSITA).
- The eval/judge logic (the measurement ruler) is never modified by this app.
