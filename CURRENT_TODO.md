# CURRENT_TODO — 当前正在做的事

> **唯一入口**: 本文件是"此刻在做什么"的**唯一稳定追踪点**。
> **位置固定**: 根目录 `CURRENT_TODO.md`, 路径永不变更。
> **更新时机**: 每次开始任务 / 完成 sub-task / 被打断切换任务时, 立即更新。
> **最后更新**: 2026-08-28 07:50 GMT+8

---

## 📍 分工 (避免和其他文件重复)

| 文件 | 职责 | 时间尺度 |
|---|---|---|
| **CURRENT_TODO.md** (本文件) | **此刻**在做的 1 个任务 + 它的 sub-task 勾选 | 小时 ~ 天 |
| `docs/ARCHITECTURE_TODOLIST.md` | 架构改造 7 项的长期追踪 (ROI / 工作量 / 状态变更日志) | 周 ~ 月 |
| `docs/TODO.md` | 版本级功能待办 (V6.8 / V6.9 / V7.0 ...) | 月 ~ 季 |
| `docs/task_tree/` | 任务迭代记录 (每次迭代一个文件, 详见 AGENTS.md) | 每次迭代 |

**规则**: 本文件**只写当前**。任务做完 → 归档到 `docs/task_tree/` + 更新对应长期 todolist → 从本文件移走。

---

## 🔥 当前任务

**任务**: 架构改造 #2 — BitSelect 提取改用 pyslang Semantic API (替代 regex)
**来源**: `docs/ARCHITECTURE_TODOLIST.md` #2 / G3 选项 3
**状态**: 🔴 **in_progress — 实现基本完成但引入 9 个回归, 不可提交**
**开始**: 2026-08-28 06:23
**最近进展**: 2026-08-28 07:50 (iter_035 补充核实)
**决策记录**: `docs/architecture/bitselect_semantic_api_decision.md`
**并行报告**: `docs/BITSELECT_HANDLER_G3_OPTION3_REPORT.md` (QClaw 产出, 结论需修正见下)

### Sub-task 勾选

- [x] 对比两套实现的输出 diff — `sim/tests/integration/test_bitselect_handler_diff.py`
- [x] 边界 fixture 实测 (parameter / generate / nested / struct) — 06:33
- [x] **G3 决策 = 选项 3 (pyslang semantic API 治本)** — 方豆 06:36 + 07:46 两次确认
- [x] 路径 B 改造 (`_common.py` +492 / `graph_builder.py` +145) — ⚠️ **WIP 未提交**
- [ ] 🔴🔴 **最高优先: 修 for-loop / generate-for 驱动源丢失 (1 → 0)** — 真 bug
- [ ] 🔴 **修 silent fallback** `_common.py:441` — 违反核心纪律 #2
- [ ] 🔴 **路径 A 改造** `bit_select_handler.py:290` 仍是 regex
- [ ] 清理 `graph_builder.py:442` 残留 `import re`
- [ ] 回归 + 提交 (代码与文档同一 commit)

### ⚠️ 当前风险: 有未提交的 WIP

```
 M src/trace/core/extractors/_common.py       (+492 行)
 M src/trace/core/graph_builder.py            (+145 行)
?? sim/tests/unit/test_common_bit_selects.py  (未跟踪)
```
**不要 `git checkout` / `stash drop` 这些文件** — 是选项 3 的半成品实现。

### 🔴 已实测确认: 净引入 9 个回归 (07:50 git stash A/B 对照)

| 测试套 | 带 WIP | 干净 HEAD | 净引入 |
|---|---|---|---|
| `sim/tests/unit` | 13 failed | 13 failed | ✅ 0 |
| `sim/tests/integration` | **25 failed** | **16 failed** | 🔴 **9** |
| `test_case27_1to1_truth.py` | 4 passed | — | ✅ 全绿 |

**其中 2 个是功能 bug, 不是 golden 差异**:
```
test_for_loop_in_always: AssertionError: 0 != 1  应有 1 个驱动源 (data)
test_generate_for:       AssertionError: 0 != 1  应有 1 个驱动源 (clk)
```
→ **for-loop / generate-for 内位选的驱动关系被弄丢了**

⚠️ **QClaw 报告建议"重新生成 golden"不可直接采纳** — 会把上面这个真 bug
固化成新 baseline, 违反 `AGENTS.md` "禁止为通过而改 assertion/golden"。

### ✅ 已验证 (iter_035 实测)

- bitselect 测试: 12 passed / 1 failed (失败项 fixture `data[3:0][1:0]` 是**非法 SV**, 非代码缺陷)
- `test_case27_1to1_truth.py`: 4 passed
- ⚠️ **07:46 曾误判 "WIP 引入 0 回归"** — 当时只跑了 `unit + cli`, **漏跑 integration**,
  而回归全在 integration。07:50 重测已更正 (见上方"净引入 9 个回归")。
- `sim/tests/unit + cli` 那 33 项失败根因: `~/.svq/cache` 在 AI 沙箱外不可写
  (`ast_cache.py:30` 用 `Path.home()`), **属 AI 执行环境限制, 方豆本地应正常**

### 📌 关键发现 (本任务)

- 两套实现的**边/节点存在性完全一致** (0 差异)
- 唯一差异: RangeSelect 节点 4 个属性 (`bit_range` / `parent_bit_*` / `width`) 路径 B 漏设
- **regex 比预想鲁棒** — pyslang elaboration 会折叠 `W-1`→`7`, struct 前缀也可匹配
- 🔴 真实额外 bug: **generate-for 动态位选 (`acc[i]`) 不产生 BIT_SELECT 边** → 已记为 #8
- 🔴 新架构债: **两套实现都不用 pyslang API, 全是 regex** — 违反项目 "pure semantic API" 方向

---

## ⏸️ 已启动但暂停的任务

**任务**: 架构改造 #1 — 拆 driver_extractor (4101 行 → 10 个文件)
**状态**: 🟡 in_progress (9 步完成 3 步)
**暂停原因**: 切去做 #2, 未完成不代表放弃
**下一步**: Step 3b 拆 `_create_net_decl_edges` (~123 行, 依赖 7 个 helper, `_build_signal_source` 需先提到 `_common`)
**已完成**: Step 1+2 alias_extractor (`b6708b5`) / Step 3 wire_init 核心 (`a2dac7c`, 净减 262 行 -6.4%)
**剩余**: Step 3b → 4 assign → 5 statement_flattener → 6 always (最高风险) → 7 function → 8 删主体 → 9 全套回归

---

## ✅ 最近完成 (保留 3 条, 更早的看 git log + docs/task_tree/)

| 完成时间 | 任务 | 产出 |
|---|---|---|
| 2026-08-27 23:48 | 架构改造 #3 — EXTRACTION_COVERAGE.md 总表 | `docs/EXTRACTION_COVERAGE.md` (33 语法 × 5 档 × 101 fixture), commit `54e854d` |
| 2026-08-27 21:33 | 架构改造 #1 Step 3 | commit `a2dac7c` |
| 2026-08-27 20:38 | 架构改造 #1 Step 1+2 | commit `b6708b5`, 1461 tests 0 regression |

---

## 📋 下一个候选 (未启动, 不要自己开工 — 先问方豆)

- #8 (新发现) — 修 generate-for 动态位选不产生 BIT_SELECT 边
- #4 — `docs/EXTRACTION_FAILURES.md` 集中表 (1 天)
- #5 — UnifiedTracer 20 步管线 → 依赖图 (2 天)
- #6 — expression tree 提取独立成 builder (2 天, 建议 #1 完成后做)
- #7 — 迁 pyslang 11.0 native API (1-2 周, 长期高 ROI)

---

## 📝 维护说明

1. **同时只有 1 个"当前任务"** — 多任务并行是错觉, 会导致两边都做不完
2. **切换任务前**, 把当前任务移到"已启动但暂停", 写清楚下一步是什么
3. **任务完成后**: 写 `docs/task_tree/iterations/iter_NNN_*.md` → 更新长期 todolist → 移到"最近完成"
4. **阻塞时必须写明**: 阻塞在什么、需要谁决策、有哪些选项和代价
5. **本文件必须和实际工作同步更新** — 文档更新和实际工作同等重要。
   任务开始前设为当前任务, 进行中逐项勾选, 完成后立即清出。
   完成判定 = **代码 ✅ + 测试 ✅ + 文档 ✅**, 只写完代码不算完成。
   详见 `AGENTS.md` → "📓 开发日志与迭代记录 → 任务前后必须更新文档"
