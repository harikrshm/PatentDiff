# Information Architecture: Unified Workbench

> Companion to `.design/unified-workbench/DESIGN_BRIEF.md`. The app is a **Plotly Dash multi-page app**
> (`app_unified/`, `use_pages=True`) — the routes already exist from Spec 1 and are **fixed**; this IA
> defines the **navigation frame, per-page structure, and register layout** that the visual build hangs
> on. It does not change routing or functionality.

## Site Map

Four real routes. The Evaluation group is a nav grouping, not a route of its own beyond `/eval`.

- **PatentDiff** `/` — prototype (claim-diff form → report) · *memo register*
- **Evaluation** *(nav group)*
  - **Overview** `/eval` — analyst console (the decision arc) · *instrument register* · **unchanged**
  - **Traces** `/eval/traces` — annotation tool (trace reader + failure coder) · *memo register*
  - **Comparison** `/eval/comparison` — before/after eval delta (v1) · *instrument register*

No new routes. `/eval` deep-link query params (`?set=`, `?eval=`) remain console-only.

## Navigation Model

- **Primary navigation — persistent left sidebar.** The single source of app navigation. Two top-level
  items: **PatentDiff** and **Evaluation**; Evaluation is an always-expanded group showing its three
  children (**Overview · Traces · Comparison**). Active item carries the indigo rail/active treatment.
  Max depth = 2 (section → view). The sidebar is the *only* primary nav — the Spec-1 horizontal top-nav +
  sub-nav strip is **replaced** by it.
  - **Collapsed (icon) state** on `/eval`: labels hide, items become icons, width animates to a thin
    strip so the console's step-rail leads the left edge. Hover or a pin control expands it temporarily.
    Every other route shows the full labeled sidebar.
- **Secondary / contextual navigation — top toolbar (in content area).** A slim bar at the top of the
  content column holding *page-contextual* controls, not navigation:
  - Eval pages (`/eval`, `/eval/traces`, `/eval/comparison`): **corpus / trace-set selector**, **Run
    eval** button + status, **last-run** timestamp.
  - Prototype (`/`): page title only (no eval controls).
  - The **theme toggle** is pinned to the toolbar's right on every route (global).
  - On `/eval`, the console's own decision-arc step markers (① How bad … ⑤ Decision) read as the
    in-page device beneath this toolbar (existing `wb-rail` behavior) — they are *in-page anchors*, not
    app nav.
- **Utility navigation**: theme toggle (toolbar right). No account/auth/help — single-user local tool.
- **Mobile navigation**: none. Desktop-first; below ~1024 the sidebar may default to its icon state and
  content reflows/scrolls. No hamburger, no phone layout.

## Content Hierarchy

### PatentDiff `/` — *memo register*
1. **Two-column claim/spec input** (Patent A source · Patent B target) — the primary job is drafting the
   comparison; the memo surface and inputs dominate above the fold.
2. **Analyze action** — the single indigo affordance, directly under the inputs.
3. **Report output** (machine voice) — element-mapping table + overall opinion, rendered as the
   instrument readout *inside* the memo page: mono tabular numerals, verdicts tinted by the reserved data
   scale. Appears below the form after Analyze.
4. **Run metadata** (run_id, model, tokens, latency) — collapsed detail, last.

### Overview `/eval` — *instrument register · UNCHANGED*
Existing console IA stands (see `.design/eval-workbench/INFORMATION_ARCHITECTURE.md`): control toolbar →
① How bad (KPIs) → ② Where (heatmap) → ③ Why (hypothesis + your-call) → ④ Priority → ⑤ Decision, read as
a vertical scroll with the left step-rail. This IA only adds the sidebar-collapse behavior around it.

### Traces `/eval/traces` — *memo register*
1. **Trace selector** — pick the trace to read/annotate. Left of the content (a memo "table of
   contents"), or a top selector within the toolbar region.
2. **Trace reader** (memo, read-only) — metadata, dimensions, both patents' claims/specs, the tool's
   overall opinion. The document being judged; it gets the most reading width.
3. **Annotation form** (human voice) — verdict (segmented PASS/FAIL), failure-mode multiselect (taxonomy),
   comment, reviewed, Save. The act of judgment; warm human-voice fields, beside or below the reader.
4. **Save status** — inline confirmation, last.

### Comparison `/eval/comparison` — *instrument register*
1. **Controls** — Before set · After set · Eval (PHOSITA/Citation). Sets what's measured; leads.
2. **PASS-rate KPI tiles** — before %, after %, delta pp (mono numerals, valence). The headline answer.
3. **Verdict transition matrix** — themed `dash_table`, mono numerals; the structural read.
4. **Flipped traces** — Fixed (FAIL→PASS) and Regressed (PASS→FAIL) run-id lists, for spot-checking. Last.

## User Flows

### Primary: "Run a patent comparison, then evaluate the model"
1. User lands on **`/` PatentDiff** (full sidebar). Drafts Patent A/B claims + specs on the memo surface.
2. Clicks **Analyze** → report renders (machine-voice table) → a trace is logged.
3. Switches via sidebar to **Evaluation › Traces** (`/eval/traces`, still memo register, frame unchanged):
   reads a logged trace, codes a verdict + failure mode, **Save**.
4. Sidebar to **Overview** (`/eval`): the sidebar **collapses to icons**; the instrument console leads
   with its step-rail. Reads how bad / where / why / priority / decision.
5. Sidebar (icon) to **Comparison** (`/eval/comparison`): sidebar **re-expands**; picks before/after sets;
   reads the PASS-rate delta + transition matrix to confirm a prompt change helped.

### Secondary: "Register hand-off" (the design-critical micro-flow)
1. User is on a **memo** page (paper surface). 2. Navigates to an **instrument** page (canvas surface).
3. The **frame is identical** (sidebar + toolbar in the same place); only the content **temperature**
   changes (warm paper → cool canvas). The user should perceive *a different kind of work*, not *a
   different app*. Reverse holds memo→instrument→memo.

### Tertiary: "Re-run the eval" (unchanged)
1. On any eval page, click **Run eval** (toolbar) for the active set. 2. Button disables; status streams.
3. On completion, data refreshes; last-run updates. Background job; never blocks navigation.

## Naming Conventions

| Concept | Label in UI | Notes |
|---|---|---|
| App-level section | **PatentDiff** / **Evaluation** | Sidebar top-level. "Evaluation" groups the 3 eval views. |
| Eval views | **Overview · Traces · Comparison** | Sidebar children under Evaluation. Keep these three words everywhere. |
| The prototype | **PatentDiff** (not "Prototype" in UI) | The product itself; "prototype" stays internal/docs. |
| Document surfaces | *(no UI label)* — "memo register" | Internal term; users feel it, never read it. |
| Measurement surfaces | *(no UI label)* — "instrument register" | Internal term. |
| Active dataset | **Trace set** ("Active trace set") | Inherited from console; "corpus" stays internal. |
| Machine output | **(machine voice)** treatment | LLM report, hypotheses — indigo voice palette. |
| Human input | **(your voice)** treatment | Annotation fields, PM conclusions — warm voice palette. |
| Re-run action | **Run eval** | Verb-first, inherited. |

## Component Reuse Map

| Component | Used on | Behavior differences |
|---|---|---|
| Left sidebar | All routes | Full+labeled everywhere; **icon-collapsed on `/eval`**; active item per route. |
| Top contextual toolbar | All routes | Eval controls on `/eval*`; title-only on `/`; theme toggle always right. |
| Memo page surface | `/`, `/eval/traces` | Warm paper canvas, hairline rules, prose type; identical token basis. |
| Instrument page surface | `/eval`, `/eval/comparison` | Cool canvas, mono numerals, dense; `/eval` is the existing `wb-*` build. |
| KPI tile | `/eval` (×4), `/eval/comparison` (×3) | Same mono-numeral tile; valence tint per metric. |
| Themed data table | `/eval` (priority), `/eval/comparison` (matrix), `/` (report) | Same `dash_table` token theme; columns differ. |
| Machine-voice block | `/` (report), `/eval` (hypothesis) | Indigo voice palette; read-only model output. |
| Human-voice field | `/eval/traces` (annotation), `/eval` (your-call) | Warm voice palette; editable input. |
| Theme toggle | All routes | Single global control; recolors both registers. |

## Content Growth Plan

Fixed-structure tool; the four views never grow. What accumulates is **data**, absorbed structurally:
- **Trace sets** grow as new suffixed `.jsonl` files appear in `traces/` — absorbed by the toolbar's
  corpus/trace-set selector (no IA change).
- **Traces** grow within a set — the Traces selector handles more entries (scroll/searchable list); no new
  pages.
- **Comparison** will grow into the **Spec-2 experiment tracker** (leaderboard + charts) — that adds
  surfaces *within* `/eval/comparison`, not new routes; reuses KPI/table vocabulary. Out of scope here.
- No pagination/search/archive needed at current corpus sizes (tens–hundreds of traces).

## URL Strategy

- **Pattern**: fixed routes `/`, `/eval`, `/eval/traces`, `/eval/comparison`. No new routes; the sidebar
  drives navigation, the URL reflects it.
- **Dynamic segments**: none.
- **Query parameters**: console-only, optional — `?set=<trace-set>` and `?eval=phosita|citation|either`
  on `/eval` (existing). Not introduced for the other pages in this pass.
- **Legacy**: none new; Spec-1 already removed the old Streamlit entry points.
