# Architecture Decision: case27 Signal Graph Completeness (2026-08-26)

**Status**: 🔒 **LOCKED** (D1-D4 at 23:00 GMT+8 `om_x100b67dbb9a3d8acc363f6f98e6bd89`; D5 added 07:20 GMT+8 `om_x100b67c3047874a0c44881d1ea50581`)
**Owner**: 方豆 / QClaw
**Scope**: signal-graph extraction → visualization pipeline + pyslang version policy
**Affects**: `src/trace/core/semantic_adapter.py`, `src/trace/core/driver_extractor.py`, `src/trace/core/graph/viz/*`, `src/trace/core/_pyslang_compat.py`

---

## 📌 Context (why this decision exists)

The case27 (`golden_dataflow_27_generate_loop.sv`) signal graph investigation (iter_031 + iter_032) surfaced **three gaps** between SV code and viz labels:

| Gap | Symptom | Root cause |
|---|---|---|
| **Gap 1** | `acc[i]` shows as `[i]` template label, not `[0..4]` | Semantic API does not elaborate genvar substitutions in LHS expressions |
| **Gap 2** | `*` op nodes missing for `prod[0..3]` (4 `wire prod = data * weights[i];` declarations inside `generate for` block) | `SemanticAdapter` does not walk into generate-block body; `semantic_adapter.py:669` returns empty list for generate blocks (pyslang v9 limitation still encoded as legacy comment) |
| **Gap 3** | `?:` op nodes missing for `sum_out` (module-top-level ternary assign) | `_handle_normal_assign` early-returns when RHS is folded to `ConstantValue` by pyslang (parameter folding: `W`, `N` get resolved before our AST walk) |

T.66 + T.83 + T.85 + T.87 architecture deep-read traced these to a deeper architectural question: **what level of pyslang API should sv_query rely on?**

---

## 🎯 Decision (locked)

### D1. **Use Semantic API only** — no Syntax API, no mixed-layer

- **Rationale**: Semantic API gives elaborated, bound, type-checked AST. Only this gives us accurate cross-module references, typed expressions, and signal-type information that downstream viz, evidence, and risk commands depend on.
- **Rejected alternatives**:
  - ❌ **PyslangAdapter** (`base.py`): is a **mixed-layer** (Syntax-side entry `parser`, but uses `SyntaxKind.GenerateBlock` for routing). Not pure semantic.
  - ❌ **Pure pyslang native API (`comp.topInstances`)** from 2026-06-25 plan: also walks generate-block contents, which we explicitly do not want (see D2).
- **Constraint**: keep `SemanticAdapter` (`semantic_adapter.py`) as the canonical adapter for `DriverExtractor`.

### D2. **Give up on generate-block internal information** — case27 Gap 1 + Gap 2 are no longer bugs

- **Rationale**: Semantic API in pyslang v11 still has limits on get-block body elaboration (the `semantic_adapter.py:669` legacy comment reflects a real limitation). Pursuing this forces us to either fall back to Syntax API (violates D1) or do hand-rolled genvar substitution (brittle, error-prone, and the resulting viz would be misleading — genvar `[i]` is *intended* to look templated).
- **What we lose**:
  - `prod[0..3]` 4 internal nodes (inside generate for) will NOT appear as viz nodes
  - `acc[i]` template label stays as `[i]` (no `[0..4]` expansion in viz labels)
- **What we keep**:
  - module-top-level wires, continuous assigns, always blocks, ports — all visible and complete
  - cross-module traces via `InstanceSymbol.body` (this is what PR3 `92e60c1` already does)

### D3. **Visualization is fully flattened** — generate blocks treated as invisible substructure

- **Implication**: viz does not represent generate-block hierarchy. All signals visible at module top-level appear flat.
- **Visualization contract**:
  - module ports → viz nodes (✓)
  - module top-level wires → viz nodes (✓)
  - module top-level continuous assigns → viz edges (✓)
  - always blocks → viz sub-graphs (✓)
  - generate-block internal signals → **not represented** (D2)

### D4. **"Signal graph information completeness" is the core invariant** — definition pending

- **User intent** (verbatim, 23:00 GMT+8): *"更关键的，我们必须保证signal graph 的信息完整…"* ("More critically, we must guarantee the signal graph's information is complete.")
- **Definition**: ⏳ **OPEN** — user has been asked to choose A / B / C / D via Feishu message `om_x100b67dbb56028a4dd2e6b204608c4f`:
  - **A** 节点完整 — module 顶层所有 wire decls + continuous assigns + always blocks 100% 出现在 viz 节点集
  - **B** 表达式完整 — 每个 viz 节点的 expression field 不丢信息 (Gap 3 表达式污染修复)
  - **C** 1:1 对应 — 任何代码里有的逻辑, viz 里有对应 op 节点 (T.45 流程)
  - **D** 三层都要 — A + B + C 全过
- **Working assumption (until user clarifies)**: A is the minimum, C is the gold standard. We will implement A first (Gap 3 fix), then layer C (1:1 verification), and the user can promote to D if B is also required.

---


### D5. **pyslang v11 only — no v9/v10 compatibility** (added 2026-08-27 07:20 GMT+8)

- **User intent** (verbatim, 07:20 GMT+8): *"那我们确定一下版本，以后仅支持 v11 api，之后都不要再考虑v9 和 v10兼容的事情。"* ("Let's lock in the version: from now on only support v11 API, no more v9/v10 compatibility considerations")
- **What this kills**:
  - ❌ `_pyslang_compat.py` version-detection shim (`_detect_version()` etc.)
  - ❌ `_KIND_ALIASES` (kind name v10/v11 cross-reference table)
  - ❌ All `hasattr(node, 'topInstances')` style probes — v11 always has them
  - ❌ All `[Stage 6] v10/v11 兼容` comments throughout `src/`
  - ❌ Test matrix covering v9/v10 — only v11
- **What this enables**:
  - ✅ SemanticAdapter walker can be written **for v11 specifically** (no dual code paths)
  - ✅ Case27 Gap 3 fix uses v11 native API (`comp.topInstances[0].body...`) directly
  - ✅ Code is simpler — fewer branches, fewer comments, fewer tests
- **Migration path**:
  - All pyslang imports go through `pyslang.ast` submodule (v11 API surface)
  - `from pyslang.ast import Compilation, SyntaxKind, SyntaxTree, TokenKind, ValueDriver, NamedValueExpression`
  - `is_syntax_list` / `iter_syntax_list` re-evaluated: in v11, `SyntaxList` was split into a plain list — these helpers may no longer be needed
- **Decision doc**: `iter_034_pyslang_v11_only_cleanup.md` (to be created)
- **Risk**: 🟢 LOW — current installed pyslang is v11 (confirmed in T.93+T.94+T.96); no real-world v10 users in this repo.

---

## 🚫 Explicitly rejected alternatives (record for posterity)

| Approach | Why rejected |
|---|---|
| Switch to `PyslangAdapter` (`base.py`) | Mixed-layer, not pure Semantic. Violates D1. |
| pyslang native API (`comp.topInstances`, `inst.body`, `inst.portConnections`) from 2026-06-25 plan | Native API still walks generate-block contents. Violates D2. |
| `_create_net_decl_edges` add generate-block recursion | Forces us to hand-roll genvar substitution. Violates D2. |
| PR3 MIG fallback (`_find_drivers_via_mig`, `_find_loads_via_mig`) extended to DriverExtractor | Same violation as above. PR3 stays for cross-module port edges only. |
| Fix `_get_readable_expr` to return clean RHS-only syntax (T.75.2 partial fix, reverted) | Symptom-level fix only; does not address Gap 3 root cause (pyslang parameter folding). |
| T.74 pyslang v11 `RootSymbol.members` direct access | API doesn't exist in v11. Dead end. |

---

## 📋 Consequences & required follow-ups

### Required code changes (post-decision)

| # | Change | File | Status |
|---|---|---|---|
| 1 | Fix Gap 3 — module-top-level ternary `?:` op nodes in viz | `src/trace/core/driver_extractor.py` (`_handle_normal_assign`) + `src/trace/core/graph/viz/expression_tree.py` (`_store_expr_tree`) | ⏳ next iteration (iter_033) |
| 2 | Write "signal graph completeness" verification test | `sim/tests/test_signal_graph_completeness.py` | ⏳ next iteration |
| 3 | 1:1 batch regression (32 cases) — confirm no semantic regressions from Gap 3 fix | existing `sim/tests/golden/dataflow_open_source/` | ⏳ next iteration |

### Required doc updates

| Doc | Update |
|---|---|
| `docs/KNOWN_LIMITATIONS.md` | Remove Gap 1 + Gap 2 from "active bugs" — they're now **accepted limitations** under D2. Add Gap 3 to "to-fix" list. |
| `docs/ARCHITECTURE_EVOLUTION.md` | Add 2026-08-26 entry for this decision. |
| `docs/VIZ_DESIGN_SPEC.md` | Add "Flattened visualization" section documenting D3. |
| `docs/task_tree/iterations/iter_033_*.md` | New iteration journal entry for the Gap 3 fix. |

### NOT required (explicit non-goals)

- ❌ Generate-block traversal anywhere in `DriverExtractor`
- ❌ Hand-rolled genvar substitution
- ❌ PyslangAdapter integration
- ❌ pyslang native API migration (deferred indefinitely)

---

## 🔗 Related commits & prior work

| Commit | Relevance |
|---|---|
| `92e60c1` (PR3, 2026-06-15) | SignalTracer MIG fallback — kept for cross-module port edges, NOT extended to generate-block body |
| `2d268b4`, `3cdcba5`, `beb55bd` | arch command MIG namespace rewrite — orthogonal, unaffected |
| `c146b0a` (iter_031) | viz_engine.walk_e back-edge snap — visual layer only, kept |
| `488932e` (iter_032) | case27 3-gap known-issues journal — this decision supersedes Gap 1 + Gap 2 |
| `f3cdd05` (HEAD) | V100 docs sync — last commit before this decision |

---

## 📞 Contact / questions

Owner: 方豆 (`ou_76eb22c34f9fb57c520bd4cf89a7b977` on Feishu)
Working dir: `~/my_dv_proj/sv_query/`
Resume keyword: `iter_033` (next iteration)