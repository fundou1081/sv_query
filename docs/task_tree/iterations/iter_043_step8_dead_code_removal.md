# Iteration 043: #1 Step 8 — 删除死代码 (4 方法 / 255 行)

**Metadata**:
- **Iteration #**: 043
- **Task Tree Level**: L2
- **Parent Task**: ARCHITECTURE_TODOLIST #1 (拆 driver_extractor)
- **Created**: 2026-08-28 20:20 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, 4 探针全部 byte-identical

---

## 🎯 本次目标

用户指令: **"继续"** → Step 8 删 driver_extractor.py 主体。

**实际含义澄清**: 1687 行里大部分是**共享 helper 和薄壳**（被 6 个 extractor 模块
注入使用，必须留在类里）。Step 8 的真正内容 = **删除死代码**。

---

## 🔬 调查: 4 个真死代码方法 (255 行)

| 方法 | 行数 | 死因 |
|---|---|---|
| `_expand_and_append_assignment` | 85 | 全仓无调用 (仅注释提及) |
| `_collect_assignments_from_stmt` | 98 | 只有自递归, 无外部调用者 |
| `_legacy_collect_stmts_with_context` | 22 | 直接 `raise NotImplementedError` 的弃用桩 |
| `_extract_condition_str` | 50 | 全仓无引用 |

**验证方法**: 全仓 `grep` 确认无调用（含被拆走的 extractor 模块——它们通过
`h.xxx` 注入引用共享 helper，但死代码方法不在注入列表里）。

**重要区分**: 之前用"driver_extractor 内 `self.xxx(` 计数=0"判死代码是**错的**——
`_build_signal_source`（89行）在 driver_extractor 内 0 调用，但被 assign/always
通过 `h.build_signal_source` 注入使用。必须**全仓搜索**才能确认真死代码。

---

## 🔴 实施失误: 第一次删除把 extract() 也删了

第一次用行号区间删除，`_expand_and_append_assignment` 的 span 计算把
extract()（1429-1532）错误并入 → **extract() 被删** → 7 个测试失败
(`AttributeError: 'DriverExtractor' object has no attribute 'extract'`)。

**根因**: 我的 spans 计算 `end = idx[i+1][0]`（下一个方法起始行），但
`_expand_and_append_assignment`（1344）的下一个方法**不是** extract()——
等等，实际上 extract() 在 1429，确实在 `_expand_and_append_assignment` 之后。
但 span 应该正确结束于 1428。

**真正问题**: 我之前统计"189 行"是把 extract() 也数进去了（grep `_expand_and_append_assignment`
的调用点延伸）。删除时区间 `[1343:1428]` 是 0-based，但可能边界差 1。

**修复**: 改用**带 extract 保护的删除**——精确定位每个死方法区间，**检查区间内是否
意外包含 `def extract`，包含则跳过**。恢复后重新执行，extract 保留。

**教训**: 行号区间删除极易出边界错误。**删除前打印每个区间首尾行内容做人工确认**，
或加"区间内不得包含目标方法"的保护断言。

---

## 📈 验证 (git worktree A/B, 基线 = `c3047a0`)

### 回归: 全套 0 新增失败

| 测试套 | 基线 `c3047a0` | Step 8 后 | 结论 |
|---|---|---|---|
| `integration` | 13 failed | **13 failed** | ✅ 0 回归 |
| `cli` | 20 failed | **20 failed** | ✅ 0 回归 |
| `unit` | 4 failed (沙箱) | **4 failed** | ✅ 0 回归 |
| `test_case27_1to1_truth` | — | **4 passed** | ✅ 全绿 |

### 🔑 行为等价: 4 个探针全部 byte-identical

| 探针 | 覆盖 | 结果 |
|---|---|---|
| `probe_assign` | assign 4 分支 | ✅ byte-identical |
| `probe_flatten` | if/case/loop/timing | ✅ byte-identical |
| `probe_always` | ff+reset/comb/ternary | ✅ byte-identical |
| `probe_func` | function/task 调用 | ✅ byte-identical |

死代码删除**理论上不可能改行为**，但用探针验证了没有误删在用代码。

### lint

- 删 `warnings` 未用 import（`_legacy_collect_stmts_with_context` 删后）
- 剩 1 个先期 `side_kind` F841

---

## 📊 进度

| 指标 | 值 |
|---|---|
| `driver_extractor.py` | 1687 → **1432 行** (净减 255) |
| 累计拆出 (#1 全程) | 4101 → 1432, **净减 2669 行** |
| #1 步骤 | **8.5/9 完成** (只剩 Step 9 最终回归) |

---

## 📌 下一步

- **Step 9: 全套最终回归** (0.5 天) — 完整跑 unit + integration + cli + truth,
  确认整个 #1 拆分链条无回归
