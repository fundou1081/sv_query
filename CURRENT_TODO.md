# CURRENT_TODO — 当前正在做的事

> **唯一入口**: 本文件是"此刻在做什么"的**唯一稳定追踪点**。
> **位置固定**: 根目录 `CURRENT_TODO.md`, 路径永不变更。
> **更新时机**: 每次开始任务 / 完成 sub-task / 被打断切换任务时, 立即更新。
> **最后更新**: 2026-08-28 19:10 GMT+8

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

**任务**: 架构改造 #1 — 拆 driver_extractor (4101 行 → 10 个文件)
**来源**: `docs/ARCHITECTURE_TODOLIST.md` #1
**状态**: 🟡 in_progress — **7/9 步完成** (Step 6 ✅)
**下一步**: **Step 7 拆 function_extractor** (估 1 天)

### Sub-task 勾选

- [x] 盘点 driver_extractor 全部公开方法 — 67 顶层 + 11 嵌套 = 78 def
- [x] 设计新目录结构 `src/trace/core/extractors/*_extractor.py`
- [x] Step 1+2 拆 alias_extractor — commit `b6708b5`, 0 regression
- [x] Step 3 拆 wire_init 核心 — commit `a2dac7c`, 净减 262 行 (-6.4%)
- [x] ✅ Step 3b 拆 `_create_net_decl_edges` → `net_decl_extractor.py` (commit `15770af`, 3836→3754 行)
- [x] ✅ Step 4 拆 assign phase (5 方法 + 2 专属 helper, 580 行) → `assign_extractor.py`, 引入 `AssignHelpers` dataclass 打包注入 13 个共享 helper. 3754→3211 行. 4 分支探针 byte-identical.
- [x] ✅ Step 4b 拆 `_handle_normal_assign` (329 行) → 4 个具名 helper, 主函数 329 → 33 行
- [x] ✅ Step 5 拆 statement_flattener (8 方法/204 行) → `statement_flattener.py`; 3211→3035 行; flattener 全路径探针 byte-identical
- [x] ✅ Step 6 拆 always_extractor (9 方法/~790 行) → `always_extractor.py`; 3035→2292 行; always 全路径探针 byte-identical
- [ ] Step 7 拆 function_extractor (1 天) ← **下一步**
- [ ] Step 8 删 driver_extractor.py 主体 (0.5 天)
- [ ] Step 9 全套最终回归 (0.5 天)

## ✅ 最近完成 (保留 3 条, 更早的看 git log + docs/task_tree/)

| 完成时间 | 任务 | 产出 |
|---|---|---|
| **2026-08-28 11:40** | **架构改造 #2 — BitSelect 改用 pyslang Semantic API** | 两条路径均消除 regex + silent fallback 清零; **0 回归**, 另修好 3 个 `test_visualize_graph_source`. commit `bec0f51` + 本次未提交改动. 见 [iter_035](docs/task_tree/iterations/iter_035_bitselect_semantic_api_decision.md) / [iter_036](docs/task_tree/iterations/iter_036_bitselect_g3_cleanup.md) |
| 2026-08-27 23:48 | 架构改造 #3 — EXTRACTION_COVERAGE.md 总表 | `docs/EXTRACTION_COVERAGE.md` (33 语法 × 5 档 × 101 fixture), commit `54e854d` |
| 2026-08-27 21:33 | 架构改造 #1 Step 3 | commit `a2dac7c` |
| 2026-08-27 20:38 | 架构改造 #1 Step 1+2 | commit `b6708b5`, 1461 tests 0 regression |

---

## 📋 下一个候选 (未启动, 不要自己开工 — 先问方豆)

- #8 (新发现) — 修 generate-for 动态位选不产生 BIT_SELECT 边 (#2 已完成, 此项独立)
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
