# SVQuery 文档中心

> **文档索引** - 所有文档的入口
> 
> 目录：`/docs/`
> 
> **分类浏览**：
> - [核心文档](#核心文档)
> - [架构设计](#架构设计)
> - [模块设计](#模块设计)
> - [需求文档](#需求文档)
> - [问题追踪](#问题追踪)
> - [SVA/CDC/Timing](#svacdctiming)
> - [开发指南](#开发指南)
> - [子目录](#子目录)
> - [归档文档](#归档文档)

---

## 📌 快速导航

| 类别 | 入口文档 |
|------|----------|
| **项目介绍** | [README.md](./README.md) |
| **用户指南** | [USER_GUIDE.md](./USER_GUIDE.md) |
| **待办事项** | [TODO.md](./TODO.md) |
| **项目计划** | [PROJECT_PLAN.md](./PROJECT_PLAN.md) |
| **架构决定** | [FINAL_SCHEMA_DECISION.md](./FINAL_SCHEMA_DECISION.md) |
| **Visitor 测试** | [SIGNAL_EXPRESSION_VISITOR_TEST_STATUS.md](./SIGNAL_EXPRESSION_VISITOR_TEST_STATUS.md) |

---

## 核心文档

| 文件 | 说明 | 更新日期 |
|------|------|----------|
| [README.md](./README.md) | 项目介绍、环境配置、快速开始 | 2026-05-15 |
| [USER_GUIDE.md](./USER_GUIDE.md) | 用户使用指南 | 2026-05-17 |
| [TODO.md](./TODO.md) | 项目待办清单 | 2026-05-24 |
| [PROJECT_PLAN.md](./PROJECT_PLAN.md) | 项目开发计划 | 2026-05-23 |
| [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) | 已知限制 | 2026-05-23 |
| [PENDING_FEATURES.md](./PENDING_FEATURES.md) | 待实现功能 | - |

---

## 架构设计

### 核心架构 ⭐

| 文件 | 说明 |
|------|------|
| [FINAL_SCHEMA_DECISION.md](./FINAL_SCHEMA_DECISION.md) | **最终架构决定** - DataFlow 与 Schema 关系 |
| [ARCHITECTURE_DEEP_REVIEW.md](./ARCHITECTURE_DEEP_REVIEW.md) | 深度架构 Review (signal_expression_visitor 优先级最高) |
| [GRAPH_BUILDER_REVIEW.md](./GRAPH_BUILDER_REVIEW.md) | GraphBuilder Review (不需要拆分) |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 架构文档总览 |
| [ARCHITECTURE_IMPROVEMENT.md](./ARCHITECTURE_IMPROVEMENT.md) | SignalExpressionVisitor 架构改善提案 |
| [ARCHITECTURE_REFACTOR_IMPACT.md](./ARCHITECTURE_REFACTOR_IMPACT.md) | 重构影响评估 |

### 架构演进

| 文件 | 说明 |
|------|------|
| [ARCHITECTURE_EVOLUTION.md](./ARCHITECTURE_EVOLUTION.md) | 架构演进历史 |
| [ARCHITECTURE_ANALYSIS.md](./ARCHITECTURE_ANALYSIS.md) | 代码架构分析报告 |
| [ARCHITECTURE_COMPARISON.md](./ARCHITECTURE_COMPARISON.md) | 架构对比分析 |
| [ARCHITECTURE_UNDERLYING_ABSTRACTION.md](./ARCHITECTURE_UNDERLYING_ABSTRACTION.md) | 底层抽象对比分析 |
| [ARCHITECTURE_SIGNAL_CONNECTION.md](./ARCHITECTURE_SIGNAL_CONNECTION.md) | Signal + Connection 底层抽象 |
| [ARCHITECTURE_REPORT_v1.md](./ARCHITECTURE_REPORT_v1.md) | 架构报告 v1 |

### Schema 对照

| 文件 | 说明 |
|------|------|
| [SCHEMA_COMPARISON_V2.md](./SCHEMA_COMPARISON_V2.md) | **Schema 对照 V2** - 新旧 Schema 详细对比 |

---

## 模块设计

### DataFlow 数据流

| 文件 | 说明 |
|------|------|
| [DATAFLOW_ANALYSIS_ARCHITECTURE.md](./DATAFLOW_ANALYSIS_ARCHITECTURE.md) | DataFlow 分析架构方案 |
| [DATAFLOW_IMPLEMENTATION_PLAN.md](./DATAFLOW_IMPLEMENTATION_PLAN.md) | DataFlowGraph 实现计划 |
| [IMPLEMENTATION_RELATION.md](./IMPLEMENTATION_RELATION.md) | 源代码与 DataFlow 提案关系 |

### ControlFlow 控制流

| 文件 | 说明 |
|------|------|
| [CONTROL_FLOW_ANALYSIS.md](./CONTROL_FLOW_ANALYSIS.md) | 控制流分析架构提案 |
| [CONTROL_FLOW_DESIGN.md](./CONTROL_FLOW_DESIGN.md) | ControlFlow 功能设计 |
| [CONTROL_FLOW_IMPROVEMENTS.md](./CONTROL_FLOW_IMPROVEMENTS.md) | ControlFlow 改进方案 |
| [CONTROL_FLOW_DEBUG.md](./CONTROL_FLOW_DEBUG.md) | ControlFlow 调试记录 |
| [IMPLEMENTATION_RELATION_CONTROL_FLOW.md](./IMPLEMENTATION_RELATION_CONTROL_FLOW.md) | 源代码与 ControlFlow 提案关系 |

### 图谱

| 文件 | 说明 |
|------|------|
| [GRAPH_CATALOG.md](./GRAPH_CATALOG.md) | 图谱总览 |
| [SIGNAL_GRAPH_ANALYSIS_REQUIREMENTS.md](./SIGNAL_GRAPH_ANALYSIS_REQUIREMENTS.md) | SignalGraph 需求 |
| [SIGNAL_QUERY_IMPROVEMENT_PLAN.md](./SIGNAL_QUERY_IMPROVEMENT_PLAN.md) | SignalQuery 改进计划 |
| [SIGNAL_QUERY_OUTPUT_FEEDBACK.md](./SIGNAL_QUERY_OUTPUT_FEEDBACK.md) | SignalQuery 输出反馈 |

---

## 需求文档

| 文件 | 说明 |
|------|------|
| [REQ5_6_7_8_DRIVER_LOAD_ANALYSIS.md](./REQ5_6_7_8_DRIVER_LOAD_ANALYSIS.md) | 需求 5-8 驱动/负载分析 |
| [REQ5_6_7_8_TECHNICAL_EVALUATION.md](./REQ5_6_7_8_TECHNICAL_EVALUATION.md) | 需求 5-8 技术评估 |
| [REQ8_SIGNAL_TRACER_TECHNICAL_EVALUATION.md](./REQ8_SIGNAL_TRACER_TECHNICAL_EVALUATION.md) | SignalTracer 技术评估 |
| [REQUIREMENT_SVA_ANALYSIS.md](./REQUIREMENT_SVA_ANALYSIS.md) | SVA 需求分析 |
| [REQUIREMENT_COVERGROUP_ANALYSIS.md](./REQUIREMENT_COVERGROUP_ANALYSIS.md) | Covergroup 需求分析 |
| [REQUIREMENT_FUNCTION_CALL_GRAPH.md](./REQUIREMENT_FUNCTION_CALL_GRAPH.md) | 函数调用图需求 |
| [REQUIREMENT_UVM_TESTBENCH_STRUCTURE.md](./REQUIREMENT_UVM_TESTBENCH_STRUCTURE.md) | UVM Testbench 需求 |

---

## 问题追踪

| 文件 | 说明 |
|------|------|
| [ISSUES_SUMMARY.md](./ISSUES_SUMMARY.md) | Issue 汇总 |
| [OPENCHIP_QA_ISSUES.md](./OPENCHIP_QA_ISSUES.md) | QA 问题汇总 |
| [OPENCHIP_QA_ROUND3_ISSUES.md](./OPENCHIP_QA_ROUND3_ISSUES.md) | QA Round 3 |
| [OPENCHIP_QA_ROUND4_ISSUES.md](./OPENCHIP_QA_ROUND4_ISSUES.md) | QA Round 4 |
| [OPENCHIP_QA_ROUND4_REPORT.md](./OPENCHIP_QA_ROUND4_REPORT.md) | QA Round 4 报告 |

---

## SVA/CDC/Timing

| 文件 | 说明 |
|------|------|
| [SVA_ANALYSIS.md](./SVA_ANALYSIS.md) | SVA 分析 |
| [CDC_ANALYSIS.md](./CDC_ANALYSIS.md) | CDC 检测 |
| [TIMING_ANALYSIS.md](./TIMING_ANALYSIS.md) | Timing 分析 |

---

## 开发指南

### 重构与规范化

| 文件 | 说明 |
|------|------|
| [REFACTOR_GUIDE_v2.md](./REFACTOR_GUIDE_v2.md) | **重构指南 V2** |
| [REFACTOR_DETAILED_PLAN.md](./REFACTOR_DETAILED_PLAN.md) | 详细重构计划 |
| [CODE_DISCIPLINE_REVIEW.md](./CODE_DISCIPLINE_REVIEW.md) | 代码纪律 Review |
| [DISCIPLINE_VIOLATIONS.md](./DISCIPLINE_VIOLATIONS.md) | 纪律违反记录 |

### Handler 开发

| 文件 | 说明 |
|------|------|
| [HANDLER_WRITING_GUIDE.md](./HANDLER_WRITING_GUIDE.md) | Handler 编写指南 |
| [SYNTAX_KIND_HANDLER_MAP.md](./SYNTAX_KIND_HANDLER_MAP.md) | SyntaxKind → Handler 映射 |
| [DESIGN_PYSALNG_VISIT_BASED_ONHANDLER.md](./DESIGN_PYSALNG_VISIT_BASED_ONHANDLER.md) | 基于 pyslang.visit() 的 Handler 设计 |
| [PROPOSAL_REFLECTION_BASED_HANDLER.md](./PROPOSAL_REFLECTION_BASED_HANDLER.md) | 反射 Handler 提案 |

### Visitor 使用

| 文件 | 说明 |
|------|------|
| [VISITOR_USAGE_REVIEW.md](./VISITOR_USAGE_REVIEW.md) | Visitor 使用审查 |
| [TDD_DEVELOPMENT_PLAN.md](./TDD_DEVELOPMENT_PLAN.md) | TDD 开发计划 |

### 设计与实现

| 文件 | 说明 |
|------|------|
| [DESIGNER_PLAN.md](./DESIGNER_PLAN.md) | 设计工程师版开发计划 |
| [DESIGN_BOUNDARY_CONTROL.md](./DESIGN_BOUNDARY_CONTROL.md) | 边界控制与 Selective 遍历设计 |
| [DESIGN_COVERGROUP_EXTRACTION.md](./DESIGN_COVERGROUP_EXTRACTION.md) | Covergroup 结构化提取设计 |
| [SPEC_UVM_TESTBENCH_EXTRACTOR.md](./SPEC_UVM_TESTBENCH_EXTRACTOR.md) | UVM Testbench Extractor 规格 |
| [RISK_ANALYSIS.md](./RISK_ANALYSIS.md) | 风险分析 |
| [VISUALIZATION.md](./VISUALIZATION.md) | 可视化 |

---

## 子目录

### `docs/architecture/` - 架构子文档

| 文件 | 说明 |
|------|------|
| [architecture/ARCHITECTURE.md](./architecture/architecture.md) | 架构文档 |
| [architecture/CORE_RESTRUCTURE.md](./architecture/CORE_RESTRUCTURE.md) | 核心重构 |
| [architecture/GRAPH_DIFF_DESIGN.md](./architecture/GRAPH_DIFF_DESIGN.md) | Graph Diff 设计 |
| [architecture/SV_SYNTAX_ROADMAP.md](./architecture/SV_SYNTAX_ROADMAP.md) | SV 语法路线图 |
| [architecture/code_framework_analysis.md](./architecture/code_framework_analysis.md) | 代码框架分析 |
| [architecture/README.md](./architecture/README.md) | 架构子目录说明 |

### `docs/images/` - 图片资源

包含架构图、时序图等可视化资源

### `docs/skeleton/` - Skeleton 规则

UVM/SVA Skeleton 自动生成规则（如果存在）

---

## 归档文档

### `docs/archive/` - 已废弃文档

> 以下文档已归档，可能包含有价值的历史信息，但不再维护

| 文件 | 说明 |
|------|------|
| archive/GRAPH_BUILDER_*.md | GraphBuilder 相关 (已重构完成) |
| archive/ISSUE_*.md | Issue 根因分析 (已修复) |
| archive/SEMANTIC_AST_*.md | 语义 AST 重构 (已完成) |
| archive/SCHEMA_COMPARISON.md | Schema 对照 (旧版本) |
| archive/REFACTOR_GUIDE.md | 重构指南 (旧版本) |
| archive/API_MIGRATION_*.md | API 迁移 (已完成) |
| archive/README_legacy.md | 遗留 README |

查看归档：`cat archive/README.md`

---

## 📊 文档统计

| 类别 | 数量 |
|------|------|
| 根目录文档 | 65 |
| `architecture/` | 10 |
| `images/` | 5+ |
| `archive/` | 21 |
| **总计** | **100+** |

---

## 🔄 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-31 | 创建完整文档索引 |
| 2026-05-24 | 首次文档梳理 (DOCS_INVENTORY.md) |

---

## 📝 文档编写规范

1. **头部信息**：每个文档应包含更新日期
2. **分类标签**：根据内容添加到合适的分类
3. **交叉引用**：使用相对路径链接相关文档

---

*本文档由 QClaw 自动生成 - 如有问题请联系维护者*