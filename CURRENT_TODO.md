# CURRENT_TODO — 当前正在做的事

> **唯一入口**: 本文件是"此刻在做什么"的**唯一稳定追踪点**。
> **位置固定**: 根目录 `CURRENT_TODO.md`, 路径永不变更。
> **更新时机**: 每次开始任务 / 完成 sub-task / 被打断切换任务时, 立即更新。
> **最后更新**: 2026-09-01 GMT+8 (测试资产补强 A/B/C 启动)

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

**任务**: 测试资产补强 A/B/C (方豆 "先记录 A B C, 我们逐个做")
详见 [L2_test_assets_abc.md](docs/task_tree/tasks/L2_test_assets_abc.md)

**A — 补主路径语法独立 regression** (进行中):
- [ ] assign / always_comb / wire 顶层 / 拼接 / alias / 三元 / parameter / generate-for
      各建独立 regression 行为断言文件 (对齐 constraint/covergroup 密度)
- [ ] 每个文件 ≥3 测试 (正例边断言 + 反例 + 有效性)

**B — 修 integration 14 个 pre-existing 失败** (待做):
- [ ] benchmark_picorv32 / benchmark_regression / human_output(4) / tree_output(5) /
      real_project_viz(2) 逐个诊断 (fixture/功能/断言 归因顺序)

**C — 扩 truth 层 1:1 金标准** (待做):
- [ ] case27 之外的模块 1:1 truth

**迭代记录**: iter_080 (最近, A/B/C 记录在 L2_test_assets_abc.md)

---
## ✅ 最近完成 (保留 3 条, 更早的看 git log + docs/task_tree/)

| 完成时间 | 任务 | 产出 |
|---|---|---|
| **2026-09-01** | **#42/#43 task 调用站点形参映射** | flattener 保留 Call 整体 + `_parse_invocation_call` 放行 Assignment 实参 → `my_task(din,dout)` 真边 din→dout, 多参数独立映射, EmptyArgument 占位边消失; 2 新测试 + 1 升级, regression 766 passed. [iter_076](docs/task_tree/iterations/iter_076_fix_gap42_43.md) |
| **2026-08-30** | **#41 class 方法体赋值** | class_graph_builder 方法体赋值提取 → 成员 DRIVER 边; 修 id() 复用非确定 bug; 2 测试, regression 764 passed. [iter_075](docs/task_tree/iterations/iter_075_fix_gap41.md) |
| **2026-08-29** | **#6 — 测试写法修正 — AST 断言升级为行为断言** | 4 文件行为断言补齐 (constraint/sva/covergroup), 772 passed. [iter_064](docs/task_tree/iterations/iter_064_test_behavior_assertions.md) |
| **2026-08-28 23:40** | **#6 — expression tree 独立 builder** | expr_tree_builder.py, 0 回归, tree 探针 byte-identical. [iter_050](docs/task_tree/iterations/iter_050_expr_tree_builder.md) |
| **2026-08-28 23:10** | **#5 — 管线 → 显式 DAG** | 新建 pipeline.py, 11 步 DAG, 0 回归. [iter_049](docs/task_tree/iterations/iter_049_pipeline_dag.md) |
| **2026-08-28 22:30** | **#4 清理 — 36 违规+20 边界** | 58 处日志/收窄, 0 回归. [iter_048](docs/task_tree/iterations/iter_048_fallback_cleanup.md) |
| **2026-08-28 21:45** | **#4 — EXTRACTION_FAILURES.md 集中表** | 登记 113+121 处 fallback, 5 类分类, P0-P3 清理优先级. [iter_046](docs/task_tree/iterations/iter_046_extraction_failures_table.md) |
| **2026-08-28 21:30** | **#8 — generate-for 动态位选修复** | BIT_SELECT+DRIVER+CLOCK 边全齐, 0 回归, 新测试有效. [iter_045](docs/task_tree/iterations/iter_045_generate_bitselect_fix.md) |
| **2026-08-28 20:45** | **架构改造 #1 — 拆 driver_extractor** | 4101→1431 行, 拆出 7 模块, 9 步全 done, 6 探针 byte-identical, 0 回归. [iter_044](docs/task_tree/iterations/iter_044_step9_final_regression.md) |
| **2026-08-28 11:40** | **架构改造 #2 — BitSelect 改用 pyslang Semantic API** | 两条路径均消除 regex + silent fallback 清零; **0 回归**, 另修好 3 个 `test_visualize_graph_source`. commit `bec0f51` + 本次未提交改动. 见 [iter_035](docs/task_tree/iterations/iter_035_bitselect_semantic_api_decision.md) / [iter_036](docs/task_tree/iterations/iter_036_bitselect_g3_cleanup.md) |
| 2026-08-27 23:48 | 架构改造 #3 — EXTRACTION_COVERAGE.md 总表 | `docs/EXTRACTION_COVERAGE.md` (33 语法 × 5 档 × 101 fixture), commit `54e854d` |
| 2026-08-27 21:33 | 架构改造 #1 Step 3 | commit `a2dac7c` |
| 2026-08-27 20:38 | 架构改造 #1 Step 1+2 | commit `b6708b5`, 1461 tests 0 regression |

---

## 📋 下一个候选 (未启动, 不要自己开工 — 先问方豆)

- ~~#7 — 迁 pyslang 11.0 native API~~ ✅ **已完成** (2026-08-29, iter_053-059,
  8/8: 5 调用方全量 native + GAP-1~7 + 等价性 3/6 + benchmark native 2.14x)。
  遗留: 子任务 1 的 CVA6/coralNPU/vortex 3 项目 strict 编译受阻 (pyslang↔项目
  语义不兼容), 见 ARCHITECTURE_TODOLIST §#7。

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
