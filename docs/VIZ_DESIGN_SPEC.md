# Visualization Design Spec

> Created 2026-07-12. Single source of truth for what each viz command should show
> and how to keep diagrams easy to understand.

## 1. Unified Standards

Every viz diagram must follow these 4 rules:

1. **One diagram answers ONE question.** `arch` does not draw timing; `pipeline`
   does not draw anomalies; each command has a single focus.
2. **Nodes < 100.** If a diagram has more than ~100 nodes, it is information
   overload. Use `--module` / `--max-*` flags to scope, or pick a different
   viz command.
3. **Direction is fixed.** Time flows left→right (`rankdir=LR`). Structure
   flows top→bottom (`rankdir=TB`). Consistency beats aesthetics.
4. **3-second test.** A reader who has never seen the design should find the
   answer to the question in 3 seconds. If not, simplify.

Additionally:
- Every diagram includes a one-line **TL;DR label** at the top.
- Diagrams > 1 page (PNG > 4000px wide or tall) should auto-paginate or
  warn the user.
- No CONST (literal) nodes rendered as standalone boxes (`4'b1011`, `32'd0`,
  etc.). Literal info is preserved as edge labels.

---

## 2. Per-Command Spec

### 2.1 `arch` — Project Architecture

| Field | Value |
|-------|-------|
| **Purpose** | "What modules exist and how do they connect?" |
| **Key questions** | (1) How many sub-modules? (2) Any cross-edges? (3) User code vs vendored IP? |
| **Audience** | New engineer onboarding to the project |
| **Direction** | TB (top-down): root at top, sub-modules below |
| **Max nodes** | 100 |

**Visual rules:**
- Top module in center, sub-modules around it
- Same `module_type` → same color (hash-based, deterministic)
- RTL anomalies (X_DRIVER, DANGLING, ORPHAN) shown as orange diamonds in
  a dedicated cluster at the bottom
- Cross-module port edges shown as dashed grey lines

**TL;DR template:** `Architecture of <target>: <N> sub-modules, <M> anomalies`

**Current status:** ✅ Compliant

---

### 2.2 `dataflow` — Data Flow Graph

| Field | Value |
|-------|-------|
| **Purpose** | "How does data flow from inputs to outputs?" |
| **Key questions** | (1) Which nodes are registers vs combinational? (2) Data vs control? (3) Where are MUXes / arithmetic ops? |
| **Audience** | Designer debugging a specific signal path |
| **Direction** | LR (left-right): time flows |
| **Max nodes** | 100 |

**Visual rules:**
- REG nodes: thick border, bold
- Combinational nodes: thin border, light fill
- MUX targets (multiple sources): bold edge
- Data edges: solid blue with expression label
- Control edges: dashed orange
- Clock/Reset nodes (with `--with-clk-rst`): distinct color
- **No CONST (literal) nodes** rendered as boxes

**TL;DR template:** `Data Flow: <target>, <N> data + <M> control + <K> clock nodes`

**Improvements planned:**
- [ ] **Module-level pagination**: when total nodes > 100, split by sub-module.
      One PNG per sub-module + a top-level overview.
- [ ] **Legend**: show color/edge meaning in the corner

**Current status:** ⚠️ Needs pagination — picorv32 darksocv renders 21884px wide.

---

### 2.3 `pipeline` — Pipeline Stages

| Field | Value |
|-------|-------|
| **Purpose** | "How many pipeline stages, and what's in each?" |
| **Key questions** | (1) How many stages? (2) What's in each stage? (3) Which control signals affect which stage? |
| **Audience** | Designer understanding timing / latency |
| **Direction** | LR (left-right): stage 0 on left, increasing to right |
| **Max nodes** | 50 stages × ~5 nodes/stage = 250 |

**Visual rules:**
- Each stage = one `subgraph cluster_stageN` (dashed border, light blue)
- Pipeline regs in stage: thick blue box
- Combinational nodes in stage: thin light-blue box
- **Control signals in HEADER ROW** at top (`rank=min`), color-coded by target
  stage, label includes `→SN`
- Edges from control to target stage: dashed, color-matched to control node
- Default `--max-control-nodes` = 8 (was 30, too overwhelming)

**TL;DR template:** `Pipeline: <target>, <S> stages, <R> pipeline regs`

**Improvements planned:**
- [ ] **Stage folding**: when stages > 30, fold every N stages into a summary
      cluster. User can `--unfold` to see all.
- [ ] **Legend**: stage colors / control-color mapping

**Current status:** ⚠️ picorv32's 150 stages produces ~4800px tall PNG.

---

### 2.4 `chain` — Data Chain

| Field | Value |
|-------|-------|
| **Purpose** | "What path does data take from input port to output port?" |
| **Key questions** | (1) Input port → output port path? (2) Path depth (cycles)? (3) Any branches / anomalies on the way? |
| **Audience** | Verification engineer tracing a specific data flow |
| **Direction** | LR |
| **Max nodes** | 30 edges (`--max-edges`) |

**Visual rules:**
- Only the actual data path is shown (no unrelated regs)
- Edges labeled with cycle delta: `+1 cycle`, `+2 cycle`
- Critical path edges (max depth) highlighted in red
- Ghost edges for anomalies (X_DRIVER, DANGLING) shown dashed orange,
  capped at 20 to avoid clutter
- Default `--max-edges` = 30

**TL;DR template:** `Data Chain: <target>, <E> edges from <N> paths`

**Current status:** ✅ Compliant

---

### 2.5 `timing` — Critical Path Analysis

| Field | Value |
|-------|-------|
| **Purpose** | "What's the longest combinational path? Where's the timing risk?" |
| **Key questions** | (1) Longest path depth (cycles)? (2) Which path is critical (red)? (3) RTL anomaly indicators? |
| **Audience** | Designer doing timing closure / synthesis prep |
| **Direction** | LR |
| **Max nodes** | 50 (paths) + anomaly cluster |

**Visual rules:**
- Critical paths (top N deepest) highlighted red with `penwidth=3`
- Combinational nodes: blue boxes
- REG nodes: square boxes
- RTL anomalies (X_DRIVER, DANGLING, ORPHAN) in dedicated cluster at bottom
- Default `--max-paths` = 5

**TL;DR template:** `Critical Paths: <target>, top <P> paths, depth <D> cycles`

**Current status:** ✅ Compliant

---

## 3. Implementation Roadmap

Tracked as Phase 6 sub-tasks:

- [ ] **6.1 Dataflow pagination** — when nodes > 100, split by sub-module.
      Output: one `dataflow_<sub>.dot` per sub-module + overview.
- [ ] **6.2 Pipeline stage folding** — when stages > 30, fold every N into
      a summary cluster.
- [ ] **6.3 Legend overlay** — small legend box in top-right of each
      diagram explaining colors / shapes.
- [ ] **6.4 TL;DR label** — each viz command emits a one-line summary at
      the top of the DOT (`label="..."`).
- [ ] **6.5 Tests + golden regen** — update golden tests for new layouts.

Each item must include:
- Updated DOT generation code
- Regenerated golden file (if applicable)
- At least one screenshot showing the result

---

## 4. Conventions

- **Colors** (used consistently across all viz):
  - REG (pipeline): `#4488cc` (blue), thick border
  - Combinational: `#88bbdd` (light blue), thin border
  - Critical path: `#cc2222` (red), `penwidth=3`
  - State reg: `#cc8844` (orange)
  - Control signal: 4-color cycle by target stage:
    - `#cc6633` (warm orange) → stage N%4 == 0
    - `#aa5599` (purple)     → stage N%4 == 1
    - `#5599aa` (teal)       → stage N%4 == 2
    - `#aa8855` (brown)      → stage N%4 == 3
  - RTL anomaly: `#cc0000` (DANGLING), `#cc8800` (X_DRIVER), `#888888` (ORPHAN)
  - CONST (literal): NOT rendered as box (edge label only)

- **Edge styles**:
  - Data: solid blue `#226699`, `penwidth=1.5`
  - Control: dashed, color-matched to source node
  - Critical: solid red `#cc2222`, `penwidth=3`
  - Cross-module port: dashed grey `#999999`