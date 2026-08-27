# sv_query 架构改造 Todolist (长期追踪)

> **创建日期**: 2026-08-27 20:36
> **维护人**: QClaw Agent + 方豆
> **来源**: [ARCHITECTURE_REVIEW_2026-08-27.md](ARCHITECTURE_REVIEW_2026-08-27.md) §五
> **状态字段**: ⬜ pending / 🟡 in_progress / ✅ done / ⚠️ blocked / 🚫 won't_fix

## 🎯 7 项改造任务 (按 ROI 排序)

### #1 拆 driver_extractor (4101 行 → 10 个文件)  ⬜
- **ROI**: 🔥🔥🔥 高
- **工作量**: 2-3 天
- **状态**: pending
- **目标**: 把 4101 行单文件拆成按语法类组织的子目录
- **子任务**:
  - [ ] 盘点 driver_extractor 全部公开方法 (def 清单)
  - [ ] 设计新目录结构: `src/trace/core/extractors/{assign, always, wire_init, function, case, ternary, bit_select, struct, generate, alias}_extractor.py`
  - [ ] 设计 ExtractorResult 新协议 (按需扩展)
  - [ ] G2 计划: 拆文件的具体切割点 + import 链 + 测试覆盖
  - [ ] 实施拆分 (每拆一个文件跑一次回归)
  - [ ] 删 driver_extractor.py (全部迁完)
  - [ ] 全套回归 1460+ 测试 + 新增拆分后子文件测试
- **commit 基线**: HEAD = `912b306`
- **风险**: 高 (40% 核心代码改动) — 必须**分批拆分** + **每批跑回归**

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

### #3 建 EXTRACTION_COVERAGE.md 总表  ⬜
- **ROI**: 🔥🔥 中高
- **工作量**: 半天
- **状态**: pending
- **目标**: 30 种 SV 语法 × 4 档支持 (✅/⚠️/🔶/⛔) × 对应 fixture × 对应 test 的总表
- **子任务**:
  - [ ] 从 `memory/2026-08-27.md` Phase 1A 矩阵抽出 30 种语法
  - [ ] 对每种语法填: 支持度 / fixture 路径 / test 路径 / 已知限制
  - [ ] 把现有 7 个 spec_golden fixture + 46 个 golden_mini fixture 标上
  - [ ] 链接 SV_SYNTAX_MAPPING.md 和 PYSLANG_SEMANTIC_USAGE.md
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
| 1 | 拆 driver_extractor | 🔥🔥🔥 | ⬜ pending | — | — |
| 2 | 统一 BitSelectHandler | 🔥🔥 | ⬜ pending | — | — |
| 3 | EXTRACTION_COVERAGE.md | 🔥🔥 | ⬜ pending | — | — |
| 4 | EXTRACTION_FAILURES.md | 🔥 | ⬜ pending | — | — |
| 5 | 管线 → 依赖图 | 🔥 | ⬜ pending | — | — |
| 6 | expression tree 独立 | 🟡 | ⬜ pending | — | — |
| 7 | pyslang 11.0 native API | 长期高 | ⬜ pending | — | — |

**总进度**: 0/7 (0%)

---

## 🔄 状态变更日志

- **2026-08-27 20:36** — todolist 创建, 7 项 pending. 启动 #1 拆 driver_extractor 计划.
