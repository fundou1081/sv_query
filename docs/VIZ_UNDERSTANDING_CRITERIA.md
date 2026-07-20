# Visualization for Understanding — Evaluation Criteria

> **Purpose**: This document defines what "对理解有帮助的图" (visualization that helps
> understanding) actually means for SystemVerilog modules, broken down by use case and
> specific criteria. Use this as the acceptance rubric when designing or evaluating any
> new visualization feature.
>
> **Why it exists (2026-07-20)**: Multiple iterations of visualization improvements
> (cluster/edges/colors/refactor/V6 teach) were claimed to "help understanding", but the
> claim was not backed by concrete criteria. After a critical re-evaluation, we admitted
> most improvements were cosmetic. This document fixes that going forward.
>
> **A visualization "helps understanding" iff it scores positively on at least one
> scenario's criteria below, AND does not have any negative marks on the cross-cutting
> criteria in §0**.

---

## §0. Cross-cutting criteria (apply to ALL scenarios)

These must hold before scenario-specific criteria even apply.

### 0.1 Accuracy — must reflect code truth, not approximations

| # | Criterion | V6 status (2026-07-20) |
|---|-----------|------------------------|
| 0.1.1 | Signal names match source (no AST placeholders like `Expression(ExpressionKind.NamedValue)`) | ✅ Fixed V5 commit `56418d5` |
| 0.1.2 | Edges reflect real data-flow / control-flow dependencies | ⚠️ Data-flow yes, control-flow (always @*, case selector) no |
| 0.1.3 | No fabricated semantics (e.g., don't invent signal widths) | ✅ V6.1 dropped bogus `[2b]` labels |
| 0.1.4 | When data is approximate, say so (e.g., "combinational deps not in graph") | ✅ V6.1 added explanatory comment |
| 0.1.5 | Strict mode (compile errors) fail-fast; non-strict explicitly declared | ✅ Phase B |

### 0.2 Coverage — must address the actual question

| # | Criterion | V6 status |
|---|-----------|-----------|
| 0.2.1 | User's named signal actually appears in output | ✅ — fails with hint if not |
| 0.2.2 | Module's full signal set reachable through view menu (focus / overview / pipeline) | ✅ |
| 0.2.3 | Combinations visible (output ↔ sub-modules ↔ ports) | ⚠️ For hierarchical: `module` cmd exists; for cross-section: no unified view |

### 0.3 Cognitive load — readable, not overwhelming

| # | Criterion | V6 status |
|---|-----------|-----------|
| 0.3.1 | Default view ≤ 100 nodes | ✅ (cap=100 hardcoded, but should be configurable) |
| 0.3.2 | Focus mode ≤ 50 nodes (BFS depth 2 in dense graphs) | ✅ (depending on depth) |
| 0.3.3 | One focus node visually distinct from the rest | ✅ yellow + penwidth=3 |
| 0.3.4 | Edges distinguishable by color/style (data vs control vs clock vs reset) | ✅ |
| 0.3.5 | Text labels include signal name + kind + (optional) width | ✅ (V6.1 dropped width to avoid lies) |

### 0.4 Actionability — leads to next step

| # | Criterion | V6 status |
|---|-----------|-----------|
| 0.4.1 | Output names tell user *what to look at in code* | ❌ User must mentally map "focus y" → "find assignment of y" themselves |
| 0.4.2 | Anomalies surfaced (uncovered signal, infinite-fanout, dead code) | ⚠️ Coverage yes, fan-out alert missing |
| 0.4.3 | Click-through to source code (interactive mode) | ❌ No HTML/SVG click handling |
| 0.4.4 | Suggested next view (e.g., "this signal goes to darkriscv ALU — try `--focus ALUout`") | ❌ |

### 0.5 Honesty — visualization owns its limitations

| # | Criterion | V6 status |
|---|-----------|-----------|
| 0.5.1 | Help text states limitations upfront (e.g., "combinational deps in always @* not captured") | ⚠️  Improved V6.1, but still scattered |
| 0.5.2 | No inflated marketing terms ("teaching" implies pedagogical guarantee — risky) | ⚠️ We use "teach" but the value is navigation, not education |
| 0.5.3 | When a view is partial, say so in the output (comment in DOT or footer in HTML) | ✅ V6.1 added comment for empty focus |

---

## §1. Scenario: First-glance module comprehension

**User goal**: "I've never seen this module. Give me the gist in 30 seconds."

### Required

| # | Criterion | V6 status |
|---|-----------|-----------|
| 1.1 | Output a one-line summary ("5-stage pipeline, 4 FSMs, 48 registers") | ❌ No prose, just counts |
| 1.2 | Output semantic intent ("XOR accumulator", "priority arbiter", "FSM controller") | ❌ Not implemented; would need pattern recognition |
| 1.3 | Output I/O port list with widths | ⚠️ In DOT but visual dump, not textual |
| 1.4 | Output hierarchy depth and total sub-instance count | ⚠️ Has `module` cmd, not in teach summary |
| 1.5 | ≤ 30 seconds to grok small (<500 LOC) module | ❌ Not measurable. User must read DOT and counts |

### Optional (nice-to-have)

| # | Criterion | V6 status |
|---|-----------|-----------|
| 1.6 | Highlight "main inputs of interest" (e.g., clock-domain, reset) | ❌ |
| 1.7 | Highlight "main outputs" (e.g., registers visible at module boundary) | ❌ |
| 1.8 | Color-code by domain (compute / control / status) | ❌ |

---

## §2. Scenario: Signal tracing — "Where does X go?" / "What drives X?"

**User goal**: "I want to understand the data flow of a single signal."

### Required

| # | Criterion | V6 status |
|---|-----------|-----------|
| 2.1 | Selected signal highlighted (color/style distinct from rest) | ✅ |
| 2.2 | Full reachability in chosen direction (upstream OR downstream OR both) | ✅ BFS works |
| 2.3 | Direction clearly labeled ("upstream" / "downstream" on graph) | ✅ |
| 2.4 | **Reference to source line(s) where this signal is assigned** | ❌ Most critical gap |
| 2.5 | Show *which assignment* drives the signal, not just *that it has drivers* | ❌ Edge labels exist in dataflow but not user-readable |
| 2.6 | Don't hide combinational dependencies silently — call out the gap | ✅ V6.1 comment |

### Optional

| # | Criterion | V6 status |
|---|-----------|-----------|
| 2.7 | Show *why* an edge exists (the assignment expression) | ⚠️ dataflow_viz shows `a+b` but teach doesn't |
| 2.8 | Group by sub-instance (separate sub-graphs per component) | ❌ |
| 2.9 | Highlight common upstream drivers (signals shared by multiple ancestors) | ❌ |

---

## §3. Scenario: Code review — "Is this module structured correctly?"

**User goal**: "I'm reviewing a module for quality issues."

### Required

| # | Criterion | V6 status |
|---|-----------|-----------|
| 3.1 | Major SV constructs visible (always blocks, case, if, assign) | ⚠️ Implicit (always→registers, case→values) but no first-class representation |
| 3.2 | Naming convention violations surfaced (`clk_i` vs `clk` vs `clock` vs `i_clk`) | ❌ |
| 3.3 | Wide-fanout signals (potential decode logic / routing issues) | ⚠️ Could derive from graph; not surfaced |
| 3.4 | Dead/unreferenced signals highlighted | ❌ |
| 3.5 | Cross-module dependencies (other modules this module calls/instantiates) | ⚠️ `module` cmd exists, not integrated |

### Optional

| # | Criterion | V6 status |
|---|-----------|-----------|
| 3.6 | Show file/line of declaration | ❌ |
| 3.7 | Show complexity metric (e.g., cyclomatic for case branches) | ❌ |

---

## §4. Scenario: Debug / root cause

**User goal**: "Why isn't signal X behaving as expected?"

### Required

| # | Criterion | V6 status |
|---|-----------|-----------|
| 4.1 | Filter by relevant signal type (only show ones that could be related) | ❌ |
| 4.2 | Highlight fan-in/out hotspots (signals with abnormally many connections) | ❌ |
| 4.3 | Show reset/clock interactions clearly | ⚠️ Color-coded but basic |
| 4.4 | Trace from "expected" to "actual" — locate where things diverge | ❌ |

### Optional

| # | Criterion | V6 status |
|---|-----------|-----------|
| 4.5 | Cross-reference to recent code changes | ❌ (out of scope) |
| 4.6 | Compare to golden / previous-version graph | ❌ |

---

## §5. Scenario: Verification coverage

**User goal**: "Which signals have tests, which don't?"

### Required

| # | Criterion | V6 status |
|---|-----------|-----------|
| 5.1 | Show coverage overlay (✓ vs 🚨) | ✅ |
| 5.2 | Distinguish SVA-covered vs Covergroup-covered (different colors or markers) | ⚠️ Both 🚨 same color, only "covered" vs "uncovered" |
| 5.3 | SVA → covered signal mapping must be accurate | ✅ V6.1 fixed |
| 5.4 | Allow filtering: "show me only uncovered signals" | ❌ |
| 5.5 | Show covered bins / coverpoints count | ⚠️ Show total count; not per-bin |

### Optional

| # | Criterion | V6 status |
|---|-----------|-----------|
| 5.6 | Surface coverage by edge (which edges connect uncovered nodes) | ❌ |
| 5.7 | Suggest test gaps based on usage ("state_q is read here but no SVA mentions it") | ❌ |

---

## §6. Scenario: Modification — "If I change X, what could break?"

**User goal**: "I'm about to modify a signal/module. What depends on it?"

### Required

| # | Criterion | V6 status |
|---|-----------|-----------|
| 6.1 | All consumers of signal X visible (downstream graph) | ✅ |
| 6.2 | All drivers of signal X visible (upstream graph) | ✅ |
| 6.3 | Allow "depth-N" reachability (how deep could this bug propagate) | ✅ |
| 6.4 | Filter by sub-instance / module hierarchy | ❌ |

### Optional

| # | Criterion | V6 status |
|---|-----------|-----------|
| 6.5 | Highlight safety-critical signals (clocks, resets, FSM state) | ❌ |
| 6.6 | Suggest regression points | ❌ (out of scope) |

---

## §7. Scenario: Documentation — "Explain this to a colleague"

**User goal**: "I need to explain a module to someone else without showing them the source."

### Required

| # | Criterion | V6 status |
|---|-----------|-----------|
| 7.1 | Self-contained visualization (no need to open source) | ⚠️ Names only; logic invisible |
| 7.2 | Textual summary alongside diagram | ⚠️ Counts only; no narrative |
| 7.3 | Hierarchical entry points (drill down from top) | ⚠️ `module` cmd, but not unified |
| 7.4 | Link back to source (so colleague can dig deeper) | ❌ |
| 7.5 | Embeddable in existing doc formats (markdown, HTML, etc.) | ⚠️ HTML via viz.js; not as inline markdown |

### Optional

| # | Criterion | V6 status |
|---|-----------|-----------|
| 7.6 | Generation of prose paragraph ("This module does X. Key signals: ...") | ❌ — would need LLM/heuristic |
| 7.7 | Auto-generated module documentation sheet | ❌ |

---

## §8. Scenario: Comparison — "How is A different from B?"

**User goal**: "Compare two versions of the same module, or two variants."

### Required

| # | Criterion | V6 status |
|---|-----------|-----------|
| 8.1 | Diff mode (show only added/removed/changed) | ❌ No diff viz |
| 8.2 | Side-by-side metrics ("module X has 50 regs, module Y has 30") | ❌ |
| 8.3 | Stable IDs across versions (signal `state_q` in v1 = `state_q` in v2) | ⚠️ Stable within one compilation, not version-stable |

### Optional

| # | Criterion | V6 status |
|---|-----------|-----------|
| 8.4 | Overlay two graphs to highlight differences | ❌ |

---

## §9. Summary scorecard (template for evaluating any new viz feature)

> Apply this checklist when adding or evaluating any visualization feature.
> Skip a row if inapplicable.

| Section | Question | Y / N / Partial | Notes |
|---------|----------|----------------|-------|
| §0.1 | Are signal names + edges accurate? | | |
| §0.2 | Does it cover the actual question? | | |
| §0.3 | Is the cognitive load reasonable? | | |
| §0.4 | Does it lead to a next action? | | |
| §0.5 | Does it own its limitations honestly? | | |
| §1.x | Does it help with first-glance module comprehension? | | |
| §2.x | Does it help trace signals? | | |
| §3.x | Does it help with code review? | | |
| §4.x | Does it help with debug? | | |
| §5.x | Does it help with coverage analysis? | | |
| §6.x | Does it help assess modification risk? | | |
| §7.x | Does it help with documentation? | | |
| §8.x | Does it help with comparison? | | |

**Pass criteria**: At least one row is "Y" AND no row is "N" without explicit plan to fix.

---

## §10. Lessons learned (so we don't repeat the cosmetic-improvement cycle)

1. **Don't measure understanding by what the graph looks like** — measure by whether
   the user can answer a specific question in less time.
2. **A cosmetic improvement (cluster, color, fold) rarely changes understanding**.
   It changes *how the graph looks*, not *what it tells you*.
3. **The graph is a navigation tool, not a teaching tool**. Treating it as the latter
   leads to disappointed users.
4. **The biggest unlock for understanding is not visualization — it's reverse-linking
   from node to source code**. Most graph features don't add real value until this
   exists.
5. **V6 teach's honest value**: structured navigation + summary stats + BFS reachability.
   It is NOT a teaching tool. Rename consideration: replace `teach` with `navigate` or
   `summary` to set correct user expectations.

---

*Created 2026-07-20 after critical self-evaluation. Will be used as the rubric for
evaluating any future "viz for understanding" feature requests.*
