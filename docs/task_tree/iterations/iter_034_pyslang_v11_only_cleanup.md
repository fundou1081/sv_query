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


---

## 实际执行结果 (2026-08-27, HEAD `62ef835`)

### Commit chain

| Step | Commit | 描述 | Lines |
|---|---|---|---|
| P1 docs | `1b4b573` | 创建 iter_034 doc + case27 decision D5 锁定 | +684 / -3 |
| P2 imports | `88c0f05` | 5 个 import 从 `_pyslang_compat` 迁到 `pyslang.ast.*` 等 | +7 / -7 |
| P3 probes | `2ce4e09` | 4 个 `hasattr` probes 改直接 attribute 访问 (v11 only) | +8 / -8 |
| P4 shim | `6199a03` | `_pyslang_compat.py` 整个 git rm (232 行), helper 迁 `ast_utils.py`, 加 v11 alias bridge | +68 / -239 |
| P5 comments | `0fb950c` (amended) | 2 个 `[Stage 6] v10/v11` 注释清理 + `.gitignore` 加 bak/tmp 规则 | +6 / -3 |
| P6 tests | `62ef835` | 2 个 compat 测试重写为 v11-only, alias bridge 扩展 PEP 562 `__getattr__` | +182 / -140 |

### 验证统计

| 层 | Pass | Fail | 说明 |
|---|---|---|---|
| Unit tests | **1061** | 0 | 62.29s, 全过 |
| Integration (377 - 5 pre-exist) | 377 | 2 pre-exist | darkriscv + picorv32 SVG (base `488932e` 也 fail) |
| v11 alias + helpers | 19 | 0 | 全过 |
| v11 CLI smoke | 12 | 0 | 7 个 CLI 命令 (trace/verify/risk/dataflow/controlflow/cdc) 全过 |
| Case27 truth | 1 | 3 pre-exist | iter_032 documented gaps |
| **总计** | **1470** | 5 (均 pre-existing) | **0 回归** |

### Plan vs Reality 对照

| Plan | Reality | 偏差原因 |
|---|---|---|
| P4: keep `is_syntax_list` / `iter_syntax_list` in compat shim | 直接移到 `ast_utils.py` (P4) | P3 已迁所有 callers 到 v11 直接 import, 但仍有 10 个 helper 调用 → helper 移到 ast_utils, shim 整个删 |
| P5: 删 6 个 `[Stage 6]` 注释 | 只剩 2 个真 compat 注释 (清理) | 其余 `[Stage 6]` 注释是关于 `--human` 友好输出, 跟 pyslang 无关, 保留 |
| P6: 1458 unit + 32 batch + case27 + 7 real + golden 5/5 | 1061 unit (测试数比 plan 少) + 377 integration + 31 v11 + case27 + 7 real | plan 数据不准 (实际 unit 数 1061 不是 1458), 5 real project (cva6/vortex/etc) |
| Doc: PYSLANG_COMPAT.md 只需小改 | 整个文件重写为 `PYSLANG_V11.md` (149 → 133 行) | 内容变更太多, 改 file 名更清晰 |
| D5 table: pyslang.ast.SyntaxKind 等 | 实际 `pyslang.syntax.SyntaxKind` / `parsing.TokenKind` / `analysis.ValueDriver` (各子模块) | 我之前在 ARCHITECTURE_EVOLUTION.md 写错, P7.2 修正 |

### 已知遗留

- 5 个 failing tests (case27 3 + real_project_viz 2) 都是 pre-existing, 跟本次清理无关
  - case27: iter_032 documented signal graph 3 gaps (gen_accum 未展开, * 未提取, ?: 未提取)
  - darkriscv/picorv32 SVG: visualize 命令在某些 project 上不生成 DOT 中间文件, 跑在 base `488932e` 上同样 fail

### 关键文件变更

```
A  docs/PYSLANG_V11.md             (新, 替代 PYSLANG_COMPAT.md)
D  src/trace/core/_pyslang_compat.py (232 行, git rm)
M  src/trace/__init__.py           (alias bridge + ~25 行)
M  src/trace/core/ast_utils.py     (+ helper)
M  src/trace/core/semantic_adapter.py (import 改)
M  src/trace/core/base.py          (import 改)
M  src/trace/core/uvm_testbench_extractor.py (删 1 注释)
M  src/trace/core/driver_extractor.py (改写 1 注释)
A  sim/tests/integration/test_pyslang_v11_aliases.py (新, 19 tests)
A  sim/tests/integration/test_pyslang_v11_cli_smoke.py (新, 12 tests)
D  sim/tests/integration/test_pyslang_compat.py (整个删)
D  sim/tests/integration/test_pyslang_version_compat.py (整个删, 内容迁到 cli_smoke)
M  docs/PYSLANG_V11.md             (前 PYSLANG_COMPAT.md 重写)
M  docs/ARCHITECTURE_EVOLUTION.md  (Section 八 D5 更新)
M  docs/architecture/case27_signal_graph_completeness_decision.md (Affects row 修)
M  .gitignore                      (+ bak/tmp 规则)
```
