# sv_query 架构改造 Todolist (长期追踪)

> **创建日期**: 2026-08-27 20:36
> **维护人**: QClaw Agent + 方豆
> **来源**: [ARCHITECTURE_REVIEW_2026-08-27.md](ARCHITECTURE_REVIEW_2026-08-27.md) §五
> **状态字段**: ⬜ pending / 🟡 in_progress / ✅ done / ⚠️ blocked / 🚫 won't_fix

## 🎯 7 项改造任务 (按 ROI 排序)

### #1 拆 driver_extractor (4101 行 → 10 个文件)  🟡
- **ROI**: 🔥🔥🔥 高
- **工作量**: 6 天 (实测, review 估 2-3 天是乐观)
- **状态**: 🟡 **in_progress (Step 1+2 alias_extractor ✅ commit b6708b5, 准备 Step 3)**
- **目标**: 把 4101 行单文件拆成按语法类组织的子目录
- **子任务**:
  - [x] 盘点 driver_extractor 全部公开方法 (def 清单) — 67 顶层 + 11 嵌套 = 78 def
  - [x] 设计新目录结构: `src/trace/core/extractors/{assign, always, wire_init, function, case, ternary, bit_select, struct, generate, alias}_extractor.py`
  - [x] 设计 ExtractorResult 新协议 (按需扩展)
  - [x] G2 计划: 拆文件的具体切割点 + import 链 + 测试覆盖 — G2 plan 完成
  - [x] **Step 1+2: 拆 alias_extractor** (0.5 天, 极低风险) — commit `b6708b5`, 1461 tests 0 regression
  - [x] **Step 3: 拆 wire_init_extractor** (0.3 天, 完成核心) — commit `a2dac7c`, 1461 tests 0 regression. _create_var_nodes (22 行) 已拆, _create_net_decl_edges (~123 行) 依赖 7 个 helper, 留 Step 3b
  - [ ] **Step 3b: 拆 _create_net_decl_edges** (1+ 天, _build_signal_source 需先提到 _common)
  - [ ] Step 4: 拆 assign_extractor (1 天)
  - [ ] Step 5: 拆 statement_flattener (0.5 天)
  - [ ] Step 6: 拆 always_extractor (1.5 天, 最高风险)
  - [ ] Step 7: 拆 function_extractor (1 天)
  - [ ] Step 8: 删 driver_extractor.py 主体 (0.5 天)
  - [ ] Step 9: 全套最终回归 (0.5 天)

### #2 统一 BitSelectHandler (去重 graph_builder 那套)  ⬜
- **ROI**: 🔥🔥 中高
- **工作量**: 1 天
- **状态**: pending
- **目标**: 选一套保留 (推荐 graph_builder._create_hierarchical_bit_nodes), 另一套标 deprecated → 删除
- **子任务**:
  - [ ] 对比两套实现的输出 diff (golden fixture 跑两次)
  - [ ] 决定保留哪套
  - [ ] 删另一套, 更新所有 import
  - [ ] 回归测试
- **依赖**: 无

### #3 建 EXTRACTION_COVERAGE.md 总表  ✅
- **ROI**: 🔥🔥 中高
- **工作量**: 半天 (估)
- **状态**: ✅ **done (2026-08-27 23:48)** — commit pending
- **目标**: 33 种 SV 语法 × 5 档支持 (✅/⚠️/🔶/❌/🔸) × 对应 fixture × 对应 test 的总表
- **子任务**:
  - [x] 从 `memory/2026-08-27.md` Phase 1A 矩阵抽 33 种语法
  - [x] 对每种语法填: 支持度 / fixture 路径 / test 路径 / 已知限制 / 实施建议
  - [x] 把现有 7 个 spec_golden fixture + 32 个 orphan_regression + 30+ golden_dataflow + 7 demo = 101 fixture 全标上
  - [x] 链接 SV_SYNTAX_MAPPING.md + PYSLANG_SEMANTIC_USAGE.md + SIGNAL_GRAPH_SPEC.md
  - [x] **修正 2 个 Phase 1A 误报**: alias 方向 (Bug #1) + function 递归 (Bug #4), 加 "🟢 已确认误报修正" 章节
- **产出**: [docs/EXTRACTION_COVERAGE.md](EXTRACTION_COVERAGE.md) (7814 bytes, 33 语法 × 5 档)
- **依赖**: 无

### #4 建 docs/EXTRACTION_FAILURES.md 集中表  ⬜
- **ROI**: 🔥 中
- **工作量**: 1 天
- **状态**: pending
- **目标**: 集中记录所有已知 fallback 路径 + 触发条件 + 用户如何避免
- **子任务**:
  - [ ] grep 全部 silent fallback / try-except-pass / sentinel default 模式
  - [ ] 分类: API fallback / 端口 fallback / 表达式 fallback / 位宽 fallback / 等等
  - [ ] 每条写: 位置 / 触发条件 / 行为 / 修复建议
  - [ ] 跟 Bug #2/#3 (刚修的) 关联
- **依赖**: 无

### #5 UnifiedTracer 20 步管线 → 依赖图  ⬜
- **ROI**: 🔥 中
- **工作量**: 2 天
- **状态**: pending
- **目标**: 引入显式依赖声明 (类似 Airflow DAG), 让每步声明 inputs/outputs
- **子任务**:
  - [ ] 盘点 20 步的真正依赖关系 (哪些可并行 / 哪些必须串行)
  - [ ] 设计 PipelineStep 协议 (input_keys / output_keys)
  - [ ] 重构 UnifiedTracer.build_graph 用 DAG 拓扑排序
  - [ ] 测试: 故意打乱顺序看是否报错
- **依赖**: 无

### #6 expression tree 提取独立成 builder  ⬜
- **ROI**: 🟡 低中
- **工作量**: 2 天
- **状态**: pending
- **目标**: driver_extractor 只负责"原始 driver 边", 表达式树/常量/函数信息独立
- **子任务**:
  - [ ] 找 driver_extractor 里所有写 expr_trees/const_map/func_info 的位置
  - [ ] 抽到独立 extractor
  - [ ] ExtractorResult 协议加 build 顺序约束
  - [ ] 回归
- **依赖**: 跟 #1 (拆 driver_extractor) 部分重叠, 建议 #1 完成后做

### #7 迁 pyslang 11.0 native API  ⬜
- **ROI**: 长期高
- **工作量**: 1-2 周
- **状态**: pending
- **目标**: 用 `inst.hierarchicalPath` / `inst.portConnections` / `inst.body` 替代自建 MIG
- **子任务**:
  - [ ] 评估 11.0 native API 在 CVA6/coralNPU/darkriscv/zipcpu/riscv_core/vortex 上的等价性
  - [ ] 写 native API vs 自建 MIG 的 diff 验证脚本
  - [ ] G3 计划: 替换点 + 风险 + 回退策略
  - [ ] 实施 (分批: 先 hierarchicalPath, 再 portConnections, 再 body)
  - [ ] 性能 benchmark (预期 4x speedup)
  - [ ] 回归全套
- **依赖**: MEMORY.md 2026-06-25 用户指示 "先记录下来", 等你后续触发

---

## 📊 进度总览

| # | 任务 | ROI | 状态 | 启动 | 完成 |
|---|---|---|---|---|---|
| 1 | 拆 driver_extractor | 🔥🔥🔥 | 🟡 in_progress | 20:38 | Step 1+2/3 ✅ |
| 2 | 统一 BitSelectHandler | 🔥🔥 | ⬜ pending | — | — |
| 3 | EXTRACTION_COVERAGE.md | 🔥🔥 | ✅ done | 23:48 | 23:48 |
| 4 | EXTRACTION_FAILURES.md | 🔥 | ⬜ pending | — | — |
| 5 | 管线 → 依赖图 | 🔥 | ⬜ pending | — | — |
| 6 | expression tree 独立 | 🟡 | ⬜ pending | — | — |
| 7 | pyslang 11.0 native API | 长期高 | ⬜ pending | — | — |

**总进度**: #1 进行中 (Step 1+2/3b/4-9 完成 3/9, 子任务 6/9 还在 pending); #3 done; 其他 5 项 pending. **总 1.5/7 (21%)**.

---

## 🔄 状态变更日志

- **2026-08-27 20:36** — todolist 创建, 7 项 pending. 启动 #1 拆 driver_extractor 计划.
- **2026-08-27 20:38** — #1 启动 Step 1+2 (alias_extractor), G2 plan 完成. 预计 6 天总工作量.
- **2026-08-27 21:33** — #1 Step 3 完成 (commit `a2dac7c`). _get_signal/_fold_constant/_create_var_nodes 拆出, driver_extractor 净减 262 行 (-6.4%). 新增 Step 3b 后续处理 _create_net_decl_edges.
- **2026-08-27 23:46** — todolist 进度总览表修正 (之前显示 0/7 但实际 #1 已 in_progress). 修后续梳理下一步.
- **2026-08-27 23:48** — #3 EXTRACTION_COVERAGE.md 完成 (7814 bytes, 33 语法 × 5 档 × 101 fixture). 修正 2 个 Phase 1A 误报 (alias 方向 / function 递归). 总进度 1.5/7 (21%).
