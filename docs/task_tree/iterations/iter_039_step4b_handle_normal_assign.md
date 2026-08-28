# Iteration 039: #1 Step 4b — 拆 _handle_normal_assign (329 行) 为 4 个 helper

**Metadata**:
- **Iteration #**: 039
- **Task Tree Level**: L2
- **Parent Task**: ARCHITECTURE_TODOLIST #1 (拆 driver_extractor)
- **Created**: 2026-08-28 17:30 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, 4 dispatch 分支探针 byte-identical

---

## 🎯 本次目标

用户指令: **"继续"** → 拆 `_handle_normal_assign` 329 行 (iter_038 留的
"行为重构不与搬文件混 commit" 的未完项)。

按 iter_038 文档中的设计 — 拆为 4 个具名 helper:

| helper | | 原行号 | 职责 |
|---|---|---|---|
| `_prepare_lhs_and_dst` | 53 | 251-287 | 解构 lhs/rhs/rhs_expr + 早返 + ScopedName 父节点 + dst 创建 |
| `_resolve_rhs_signals` | 78 | 288-349 | wrapper unwrap + compile-time 检查 + ternary 检测 + expr_str |
| `_build_ternary_edge_signals` | 183 | 351-517 | conditional 分支: 收集 cond / branch sigs / cond_map / 边 |
| |
| `_build_simple_edge_signals` | 62 | 519-567 | 非 ternary: 直接走 edge_factory 或 build_signal_source |

主函数 `_handle_normal_assign` 从 **329 行 → 33 行** (含 docstring), 仅保留控制流调度。

---

## 🔑 实施中的两个失误 (诚实标注)

### 失误 1: 早期 `return` 被复制成单值, 改了契约

原函数在 line 25 有 `return` (空函数早返, 没值); 我复制成 `return None` 时,
`None` 不能被元组解包 `lhs, rhs, rhs_expr, dst_node_id = _prepare_lhs_and_dst(...)` 接住。

**修复**: 改成 `return None, None, None, None` (4 元组), 主函数检测 `lhs is None` 早返。

### 失误 2: 复制 helper body 时忘了加 `return`

`seg_resolve` 末尾是 `expr_str = rhs or ""` 赋值 (原函数里后续还要用),
机械转换没识别为返回值, helper 缺 `return rhs_signals, ...`。

**症状**: `test_generate_for` 报 `TypeError: cannot unpack non-iterable NoneType`,
指向 `_resolve_rhs_signals(...)` 行。

**修复**: 加 `return rhs_signals, has_conditional, check_expr, ternary_condition, expr_str` 到末尾。

### 这两个失误的教训

1. **搬代码时, 复制"变量赋值"和"函数 return"语义不同** —— 转换脚本只看代码表面,
   不看语义。搬完后应当**对每个 `return` / 终末行做手动检查**, 不能只信语法 OK。
2. **当场跑测试发现失误, 没造成污染** — 失误被锁定在 1 次 commit (iter_039),
   没污染 git 历史。这是 WIP 不提交的纪律收益。

---

## 📈 验证 (git worktree A/B 对照, 基线 = `1c99947`)

### 回归: 全套 0 新增失败

| 测试套 | 基线 `1c99947` | Step 4b 后 | 结论 |
|---|---|---|---|
| `integration` | 13 failed | **13 failed** | ✅ 0 回归 |
| `cli` | 20 failed | **20 failed** | ✅ 0 回归 |
| `unit` | 4 failed (沙箱) | **4 failed** | ✅ 0 回归 |
| `test_case27_1to1_truth` | — | **4 passed** | ✅ 全绿 |
| 4 dispatch 分支探针 | — | **byte-identical** | ✅ |

`test_generate_for` (本次失误 2 暴露点) 在修复后 11 passed, 与基线一致。

### ruff

`assign_extractor.py`: **All checks passed!**

---

## 💡 关键发现 / 关键技术 / 决策

### 发现 1: 行为重构 vs 文件搬迁 的分离 **兑现价值**

iter_038 (Step 4) 拆分时如果同时把 329 行也拆了, 上述两个失误会更难归因 (怀疑"搬位置坏了行为"
还是"拆函数改了语义")。这次独立 commit, 失误立刻定位到**纯 helper 提取问题**, 与
搬文件无关。

纪律 "搬代码 commit 和重构代码 commit 分开" 在此 **得到验证**。

### 发现 2: 183 行的 `_build_ternary_edge_signals` 仍超阈值, 但合理

按 AGENTS.md "函数 ~50 行阈值" 标准, 183 行仍是巨型函数。但它内部含 3 个嵌套 helper
(`_collect_cond_signals` / `_collect_branch_signals` / `_build_ternary_cond_map`),
**总计 60 行** 的递归结构是原函数的固有复杂度, 进一步拆会让递归路径切断,
反而更难懂。

判断: **当函数主体是"调度递归 + 调子函数", 即使超阈值也是合理的**。
183 行是 3 个递归 helper + 主体的总和, 不是单层复杂度。

### 发现 3: 我的搬运脚本还不够"语义感知"

dedent + splice 行号 + 字符串拼接这种做法, 适合改"已知应该什么样子"的代码。
但对"return 是不是 return"这种问题, 它答不上来。

更可靠的做法: **写一个脚本能跑的最小探针**, 验证每个新 helper 在传入 1 个 mock
input 时返回正确签名; 测的是契约, 不是行为。

---

## 📌 下一步

Step 4b 完成, #1 进度 **9 步完成 5 步 + 4b 完成**。

- **Step 5: 拆 statement_flattener** (估 0.5 天) ← **下一步**
- Step 6: 拆 always_extractor (1.5 天, 最高风险)
- Step 7: 拆 function_extractor (1 天)