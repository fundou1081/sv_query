# Iteration 34: pyslang v11-only Cleanup (D5 enforcement)

**Metadata**:
- **Iteration #**: 34
- **Task Tree Level**: L2
- **Parent Task**: `L1_case27_signal_graph_completeness` (parent of iter_031 / iter_032 / iter_033)
- **Parent Decision**: `docs/architecture/case27_signal_graph_completeness_decision.md` (D5 locked at 2026-08-27 07:20 GMT+8)
- **Created**: 2026-08-27 07:25 GMT+8
- **Author**: 方豆 / QClaw
- **Status**: 🚧 **NOT STARTED** — doc written, plan listed, awaiting user OK before code changes

---

## 🎯 Goal

Per D5 ("pyslang v11 only — no v9/v10 compatibility"), remove all v9/v10 compat shims from `src/`. After this iteration, the codebase uses `pyslang.ast.*` (v11 submodule) directly, no version probes, no `hasattr` checks for v11-only attributes.

This is **prerequisite work** for iter_033's Direction 1 fix (SemanticAdapter + InstanceBodySymbol walker): we need the v11-only API surface clean before adding new walker code, otherwise the new code would inherit v9/v10 compat complexity.

---

## 📋 User directive (verbatim)

> **"那我们确定一下版本，以后仅支持 v11 api，之后都不要再考虑v9 和 v10兼容的事情。"** (07:20:11 GMT+8, `om_x100b67c3047874a0c44881d1ea50581`)
>
> ("Let's lock in the version: from now on only support v11 API, no more v9/v10 compatibility considerations")

> **"先写doc ，然后列计划，最后还代码。"** (07:23:16 GMT+8, `om_x100b67c31884b8a0de33a4c4326a902`)
>
> ("First write the doc, then list the plan, finally write the code")

---

## 📦 Scope of cleanup (T.96 inventory)

### A. `src/trace/core/_pyslang_compat.py` (8327 bytes) — main compat shim

| Item | Lines | Action |
|---|---|---|
| `_detect_version()` function | 63 | 🗑️ delete |
| `_KIND_ALIASES` table | 191 | 🗑️ delete (no aliases needed when v11-only) |
| `is_syntax_list()` function | 155 | ⚠️ evaluate: may not be needed in v11 (SyntaxList split) |
| `iter_syntax_list()` function | 172 | ⚠️ evaluate: same as above |
| `from pyslang import ...` (v10 re-exports) | 37, 57, 76, 85, 94, 103, 112, 121 | 🗑️ delete |
| Re-export `SyntaxKind`, `TokenKind`, etc. | various | 🔧 change to `from pyslang.ast import ...` |

### B. 5 import call sites that use `_pyslang_compat`

| File | Line | Currently imports | Change to |
|---|---|---|---|
| `src/trace/core/uvm_testbench_extractor.py` | 17-18 | `Compilation`, `SyntaxTree` | `from pyslang.ast import Compilation, SyntaxTree` |
| `src/trace/core/graph/viz/expression_tree.py` | 26 | `SyntaxKind` | `from pyslang.ast import SyntaxKind` |
| `src/trace/core/semantic_adapter.py` | 22 | `is_syntax_list`, `iter_syntax_list` | direct `pyslang.ast.*` (no helper needed) |
| `src/trace/core/builder/subroutine_expander.py` | 917 | `NamedValueExpression`, `ValueDriver` | `from pyslang.ast import NamedValueExpression, ValueDriver` |
| `src/trace/core/base.py` | 8 | `SyntaxKind`, `TokenKind`, `is_syntax_list`, `iter_syntax_list` | `from pyslang.ast import SyntaxKind, TokenKind` |

### C. 4 `hasattr` probes for v11-only attributes

| File | Line | Current code | After |
|---|---|---|---|
| `src/trace/core/mig_validator.py` | 290 | `hasattr(inst, 'hierarchicalPath')` | direct `inst.hierarchicalPath` |
| `src/trace/core/semantic_adapter.py` | 417 | `hasattr(self._root, 'topInstances')` | direct `self._root.topInstances` |
| `src/trace/core/semantic_adapter.py` | 696 | `hasattr(inst_sym, "portConnections")` | direct `inst_sym.portConnections` |
| `src/trace/core/graph_builder.py` | 328 | `hasattr(root, 'topInstances')` | direct `root.topInstances` |

### D. 6 `[Stage 6] v10/v11 兼容` comments

| File | Line |
|---|---|
| `src/trace/core/uvm_testbench_extractor.py` | 81 |
| `src/trace/core/semantic_adapter.py` | 22 |
| `src/trace/core/builder/subroutine_expander.py` | 917 |
| `src/trace/core/base.py` | 8 |
| `src/trace/core/base.py` | 1720 (KEEP — this is v11 truth documentation, not compat shim) |

---

## 🛠 Plan (5 steps)

| # | Step | Time | Risk |
|---|---|---|---|
| **P1** | **Backup compat state**: `git stash` working tree, branch from `f3cdd05`, name `chore/v11-only-cleanup` | 5 min | 🟢 |
| **P2** | **Migrate 5 imports** (Section B): change each `from ._pyslang_compat import X` → `from pyslang.ast import X` | 15 min | 🟢 |
| **P3** | **Replace 4 `hasattr` probes** (Section C): direct attribute access; remove guard branches | 10 min | 🟢 |
| **P4** | **Slim `_pyslang_compat.py`**: keep `is_syntax_list` / `iter_syntax_list` if still used, delete everything else; add deprecation comment if any function kept | 30 min | 🟡 (need to verify no callers broken) |
| **P5** | **Delete 5 `[Stage 6]` comments** (Section D, line 1720 in base.py KEEP) | 5 min | 🟢 |
| **P6** | **Verification**: run unit tests (2958) + 32 batch regression + case27 1:1 + 7 real projects (picorv32_wb etc.) | 30 min | 🟡 (could surface hidden compat callers) |
| **P7** | **Document** + **commit**: `chore(v11): cleanup v9/v10 compat shims (D5)` | 15 min | 🟢 |
| **Total** | | **~1.5 h** | |

### Step P4 sub-decision: keep or delete `is_syntax_list` / `iter_syntax_list`?

TBD before P4. Run a grep:
```bash
grep -rn "is_syntax_list\|iter_syntax_list" src/
```
- If 0 callers → delete both functions, cleanest.
- If callers → keep functions but move them to `ast_utils.py` (utility module, not compat shim) and rename to clarify they're not version-specific.

---

## 🧪 Verification gate (per V101 T.45 policy)

Before commit:
1. ✅ All 2958 unit tests pass (no regression from import changes)
2. ✅ 32 batch regression (`sim/tests/golden/dataflow_open_source/`) pass
3. ✅ case27 1:1 check (Gap 3 still documented as known issue; not regressed)
4. ✅ 7 real projects visualize: picorv32_wb, picorv32_core, picorv32_pcpi_mul, picorv32_pcpi_div, picorv32_axi, picorv32_regs, darkriscv
5. ✅ Golden regression 5/5

---

## 📝 Doc updates required (post-fix)

| Doc | Update |
|---|---|
| `KNOWN_LIMITATIONS.md` | Move "5. pyslang 版本兼容代码" from "to-fix" to "已修复" |
| `ARCHITECTURE_EVOLUTION.md` | Append iter_034 outcome to Section 八 |
| `case27_signal_graph_completeness_decision.md` | Mark D5 as "executed 2026-08-27" |
| `iter_034_*.md` (this file) | Final outcome + commit hash |

---

## 🔗 Resume method

```bash
cd ~/my_dv_proj/sv_query
git log --oneline -5                          # last commits
git status                                    # working tree state
cat docs/task_tree/iterations/iter_034_*.md   # this file
# Wait for user "OK 开工" before starting P1
# Then:
git checkout -b chore/v11-only-cleanup
# P2-P7 per plan above
```

---

## 🛑 Status snapshot (2026-08-27 07:25 GMT+8)

- Doc (this file): ✅ Written
- Plan (P1-P7): ✅ Listed
- Code: ⏳ Not started — awaiting user "OK 开工"
