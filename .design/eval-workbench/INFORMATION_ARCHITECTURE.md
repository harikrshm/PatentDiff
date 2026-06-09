# Information Architecture: Eval Workbench — Analyst Console

> Companion to `DESIGN_BRIEF.md`. This is a **single-screen scrolling narrative**, not a multi-page
> site. The "site map" below is therefore a **section map**; navigation is scroll + sticky chrome +
> in-page anchors, not routing. The old two-route Dash structure (`/` Explore, `/decision`) is **collapsed
> into one page**.

## Site Map

One route. The console is a vertical funnel of five numbered sections under a persistent control bar.

- **Console** `/`  *(the only page)*
  - `▸ Control bar` — sticky chrome (corpus selector · Run eval · last-run · light/dark) — `#top`
  - `① How bad` — KPI tiles — `#how-bad`
  - `② Where` — custom heatmap + eval/dimension toggles — `#where`
  - `③ Why` — shape-read HYPOTHESIS + your-voice conclusion — `#why`
  - `④ Priority` — Freq × Impact × Exposure live table + tier inputs — `#priority`
  - `⑤ Decision` — layer assignment + ordered recommendation + required rationale — `#decision`

(`/decision` retained only as a redirect/anchor to `#priority` if any old link exists; not a real second page.)

## Navigation Model

- **Primary navigation**: The **scroll** itself is the primary nav — the five numbered steps are the
  structure. A slim **step rail** (left or top) shows the five markers (1–5) as anchor links and a
  current-section indicator, so the PM always knows where they are in the arc and can jump back.
- **Secondary navigation**: Within-section controls only — the eval toggle (PHOSITA · Citation · Either)
  in §2/§3, and tier dropdowns in §4. No nested pages.
- **Utility navigation**: Lives in the **sticky control bar**: active trace-set selector, Run-eval button
  + status, last-run timestamp, and the light/dark toggle. Persistent across the whole scroll.
- **Mobile navigation**: None — desktop-first, out of scope below ~1024px (brief). The step rail collapses
  to top markers on narrow laptops; no hamburger, no phone layout.

## Content Hierarchy

### ① How bad `#how-bad`
1. **Four KPI tiles** — PHOSITA FAIL %, Citation FAIL %, Either-fails %, Fully-clean %, each with n. The
   headline magnitude; this is the "should I even care" gate, so it leads.
2. **Active-corpus context line** — which trace set / model / prompt version these numbers came from.
   Small, directly under the tiles, so every number is attributable.

### ② Where `#where`
1. **Eval toggle** — PHOSITA · Citation · Either. Sets what the heatmap measures; must precede it.
2. **Custom heatmap** — claim profile (rows) × prior-art relationship (cols), FAIL % + n per cell,
   colorblind-safe diverging scale, n<3 ⚠ flag. The centerpiece "where does it concentrate" answer.
3. **Column/row averages** — relationship averages as the quick read.
4. **Dimension-source caption** — human-verified vs inferred accuracy figures. Honesty footnote, last.

### ③ Why `#why`
1. **Shape-read HYPOTHESIS (machine voice)** — templated note: dispersion (pp) + relationship gradient,
   labeled HYPOTHESIS, naming the worst cluster. The machine's guess at the architecture layer.
2. **Supporting numbers** — dispersion value + gradient sequence inline, so small-n cells can be discounted.
3. **Your conclusion (your voice)** — the PM's own read, captured here, visually distinct from the
   hypothesis. This is where the "guides/decides" motif is most load-bearing.

### ④ Priority `#priority`
1. **Impact tiers per failure mode** (your voice, domain judgment) — High/Med/Low, ⚠ assumed where placeholder.
2. **Exposure tiers per dimension cell** (your voice) — High/Med/Low, ⚠ assumed, tooltip explains placeholder.
3. **Live priority table** — rows = failure mode × cell; cols = FAIL% · n · Freq(computed) · Impact ·
   Exposure · **Score = F×I×E**. Sorts by score desc, re-sorts live as inputs change. The core ranking.
4. **Frequency × Impact rollup** — the two-mode inversion ("frequency said citation; F×I said PHOSITA"),
   shown explicitly.

### ⑤ Decision `#decision`
1. **Layer assignment** (your voice) — L1/L2/L3 per failure mode, each carrying its §3 HYPOTHESIS indicator.
2. **Ordered recommendation** — cheapest-layer-first, assembled from score + assigned layer.
3. **Required rationale** (your voice) — the audit trail: *why this order*. Terminal action; persisted.

## User Flows

### Primary: "Run the post-eval decision" (the whole product)
1. PM lands on `/` — sticky control bar shows the **live** corpus; §1 KPIs render immediately.
2. PM reads **§1 How bad**.
   - If numbers look stale / wrong corpus → PM switches corpus or clicks **Run eval** → background job,
     button disables + streams status → page data refreshes on completion → return to step 2.
3. PM scrolls to **§2 Where**, toggles eval (PHOSITA/Citation/Either) → heatmap re-renders; reads the
   concentration of FAIL.
4. PM scrolls to **§3 Why** — heatmap toggle carries through, so §3 hypothesis always matches §2 view.
   - Reads the machine **HYPOTHESIS** + dispersion/gradient numbers.
   - Records their **own conclusion** in the your-voice field → persisted to `annotations.json`.
5. PM scrolls to **§4 Priority** — sets **Impact** per failure mode and **Exposure** per cell.
   - Each change → live re-sort of the F×I×E table → persisted to `priority_inputs.json`.
6. PM scrolls to **§5 Decision** — assigns **layer** per failure mode (with the §3 hypothesis shown
   beside it), reviews the cheapest-first ordering, writes the **required rationale** → persisted.
7. Done — the decision and its audit trail are saved to disk; reopening restores all inputs.

### Secondary: "Compare against a baseline / experiment set"
1. PM opens control bar corpus selector → picks `baseline` (or `exp1`, etc.).
2. Entire page re-derives from that set — KPIs, heatmap, hypothesis, priority all reflect the new corpus.
3. PM's saved inputs (annotations, tiers, rationale) are keyed by `{section, widget, active_set}` so each
   corpus keeps its own decision state.

### Tertiary: "Re-run the eval"
1. PM clicks **Run eval** (control bar) on the active set.
2. Button disables (no double-run); status + log tail stream live.
3. On completion, data refreshes in place; last-run timestamp updates. Scroll position preserved.

## Naming Conventions

| Concept | Label in UI | Notes |
|---|---|---|
| Step in the funnel | **① How bad / ② Where / ③ Why / ④ Priority / ⑤ Decision** | Numbered, plain-language; the arc is the nav. |
| Active dataset | **Trace set** (selector: "Active trace set") | Not "corpus" in UI; "corpus" stays internal/docs only. |
| Reasoning failure | **PHOSITA** | Domain term, kept; expand to "PHOSITA reasoning" on first KPI. |
| Citation failure | **Citation** | Short label in toggles; "Citation text" in headings. |
| Machine-generated note | **HYPOTHESIS** | Always uppercase, always this word — never "insight"/"finding"/"verdict". |
| PM-entered conclusion | **Your call** / **Your rationale** | Second-person, the your-voice register. Distinct from HYPOTHESIS. |
| Placeholder input | **⚠ assumed** | One consistent badge + tooltip everywhere a non-measured input appears. |
| Priority score | **Score** (F × I × E) | Always shown with its three factors visible, never as a bare verdict. |
| Architecture fix layer | **Layer** (L1 / L2 / L3) | L1 instruction · L2/L3 capability; PM-assigned, never computed. |
| Re-run action | **Run eval** | Verb-first button label. |

## Component Reuse Map

| Component | Used on | Behavior differences |
|---|---|---|
| Sticky control bar | All sections (persistent) | Always pinned; corpus change re-derives whole page. |
| Step rail | All sections | Highlights current section via scroll-spy; click = anchor jump. |
| KPI tile | §1 (×4) | Valence tint differs per metric (fail vs clean). |
| Eval toggle (segmented) | §2, §3 | Shared state — one toggle drives both heatmap and hypothesis. |
| HYPOTHESIS note (machine voice) | §3, and echoed beside each §5 layer row | In §5 it's read-only echo of the §3 note for that failure mode. |
| Your-voice input | §3 (conclusion), §4 (tiers), §5 (layer + rationale) | Same visual register; field type varies (textarea / dropdown / radio). |
| ⚠ assumed badge | §4 (impact + exposure) | Identical treatment + tooltip wherever a placeholder input appears. |
| Section header / step marker | §1–§5 | Carries the number + plain-language title + one-line "question it answers". |

## Content Growth Plan

This is a fixed-structure analytical tool, not a content site — the **five sections never grow**. What
accumulates is **data**, accommodated structurally:

- **Trace sets** grow as new experiment suffixes appear in `traces/` — absorbed by the corpus selector
  (`list_trace_sets()` scans and lists them; no IA change needed).
- **Heatmap dimensions** are fixed at three (`claim_type`, `claim_length`, `relationship`); if a fourth is
  ever added it becomes a toggle, not a new section.
- **Saved PM state** grows per trace set — keyed by `{section, widget_id, active_set}` so each corpus
  keeps independent annotations/tiers/rationale without UI sprawl.
- No pagination/search/archive needed — corpus counts are small (tens–hundreds of traces).

## URL Strategy

- **Pattern**: single route `/`. Sections addressable by anchor: `/#how-bad`, `/#where`, `/#why`,
  `/#priority`, `/#decision` (step-rail links).
- **Dynamic segments**: none.
- **Query parameters**: optional, non-essential — `?set=<trace-set>` may deep-link a corpus and
  `?eval=phosita|citation|either` the heatmap view, so a particular read can be shared/bookmarked. State
  otherwise lives in `traces/workbench_state/*.json`, not the URL.
- **Legacy**: `/decision` → redirect/anchor to `/#priority` (the old second page is merged in).
