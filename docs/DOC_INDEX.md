# DOC_INDEX - 项目文档索引与任务追踪

> 创建时间: 2026-05-24
> 项目路径: /Users/fundou/my_dv_proj/sv_query
> 最后更新: 2026-05-24

---

## 📊 状态概览

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ **已完成** | 6 | DataFlow 已实现，ControlFlow 架构设计完成 |
| 🔄 **讨论中** | 2 | 正在讨论/评估中 |
| 📋 **待执行** | 4 | ControlFlow 等待实现 |
| 📦 **归档** | 19 | 已在 `docs/archive/`，仅供参考 |

---

## 一、架构设计文档 (已完成) ✅

这些文档已完成，其中 DataFlow 已实现，ControlFlow 仍为设计阶段。

### DataFlow 数据流分析
| 文档 | 状态 | 说明 |
|------|------|------|
| `FINAL_SCHEMA_DECISION.md` | ✅ 完成 | **核心架构决定** - DataFlow 基于 SignalGraph 构建 |
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | ✅ 完成 | DataFlow 三层架构设计 |
| `IMPLEMENTATION_RELATION.md` | ✅ 完成 | DataFlow 与源代码关系 |
| **`DATAFLOW_IMPLEMENTATION_PLAN.md`** | ✅ 已实现 | **DataFlow 实现完成** (2026-05-26) |

### ControlFlow 控制流分析
| 文档 | 状态 | 说明 |
|------|------|------|
| `CONTROL_FLOW_ANALYSIS.md` | ✅ 完成 | ControlFlow 架构设计 |
| `IMPLEMENTATION_RELATION_CONTROL_FLOW.md` | ✅ 完成 | ControlFlow 与源代码关系 |

### Schema 设计
| 文档 | 状态 | 说明 |
|------|------|------|
| `SCHEMA_COMPARISON_V2.md` | ✅ 完成 | 增强 data_models.py vs DataFlowAnalyzer 对比 |

---

## 二、讨论中 🔄

正在讨论或评估中，尚未形成最终方案。

### P2 任务讨论
| 文档 | 状态 | 说明 |
|------|------|------|
| `ARCHITECTURE_IMPROVEMENT.md` | 🔄 讨论中 | Visitor 单 dispatch 重构方案讨论 |
| `TODO.md` | 🔄 讨论中 | 项目待办清单 (P2/P3 任务) |

**讨论要点:**
- SignalExpressionVisitor 单 dispatch 重构是否值得做？
- 是否需要等待明确需求再开始？

---

## 三、待执行 📋

### DataFlow 实现 ✅ 已完成
| 任务 | 优先级 | 状态 | 说明 |
|------|--------|------|------|
| DataFlowSegment 实现 | P1 | ✅ 已完成 | 单步驱动 (from → to) |
| DataFlowPath 实现 | P1 | ✅ 已完成 | 完整路径 |
| DataFlowResult 实现 | P1 | ✅ 已完成 | 分析结果封装 |
| DataFlowAnalyzer 实现 | P1 | ✅ 已完成 | 主分析器 (基于 nx.all_simple_paths) |

### ControlFlow 实现
| 任务 | 优先级 | 说明 |
|------|--------|------|
| 实现 ConditionInfo | P2 | 条件信息结构 |
| 实现 StateTransition | P2 | 状态机转换 |
| 实现 ControlFlowResult | P2 | 控制流结果封装 |
| 实现 ControlFlowAnalyzer | P2 | 主分析器 |

**参考文档:** `docs/CONTROL_FLOW_ANALYSIS.md`

---

## 四、参考文档 (已完成)

这些文档已完成，但不需要后续实现。

### 项目基础
| 文档 | 说明 |
|------|------|
| `README.md` | 项目介绍 |
| `PROJECT_PLAN.md` | 项目计划 |
| `USER_GUIDE.md` | 用户指南 |
| `DOCS_INVENTORY.md` | 文档清单与清理记录 |

### 代码规范
| 文档 | 说明 |
|------|------|
| `CODE_DISCIPLINE_REVIEW.md` | 代码规范审查 |
| `VISITOR_USAGE_REVIEW.md` | Visitor 使用审查 |
| `REFACTOR_GUIDE_v2.md` | 重构指南 V2 |

### 问题追踪
| 文档 | 说明 |
|------|------|
| `ISSUES_SUMMARY.md` | 问题汇总 |
| `KNOWN_LIMITATIONS.md` | 已知限制 |

### QA 问题 (历史)
| 文档 | 说明 |
|------|------|
| `OPENCHIP_QA_ISSUES.md` | QA 问题汇总 |
| `OPENCHIP_QA_ROUND3_ISSUES.md` | QA Round 3 |
| `OPENCHIP_QA_ROUND4_ISSUES.md` | QA Round 4 |
| `OPENCHIP_QA_ROUND4_REPORT.md` | QA Round 4 报告 |

### 需求文档
| 文档 | 说明 |
|------|------|
| `REQ5_6_7_8_DRIVER_LOAD_ANALYSIS.md` | 需求 5-8 技术评估 |
| `REQ5_6_7_8_TECHNICAL_EVALUATION.md` | 需求 5-8 技术评估 |
| `REQ8_SIGNAL_TRACER_TECHNICAL_EVALUATION.md` | 需求 8 技术评估 |

---

## 五、文档索引

### 按功能分类

```
📁 架构设计 (已完成)
├── FINAL_SCHEMA_DECISION.md             ⭐ 核心
├── DATAFLOW_ANALYSIS_ARCHITECTURE.md
├── CONTROL_FLOW_ANALYSIS.md
├── SCHEMA_COMPARISON_V2.md
├── IMPLEMENTATION_RELATION.md
└── IMPLEMENTATION_RELATION_CONTROL_FLOW.md

📁 任务追踪
├── TODO.md                              🔄 讨论中
└── DOCS_INVENTORY.md                    ✅ 清理完成

📁 项目基础
├── README.md
├── PROJECT_PLAN.md
├── USER_GUIDE.md
└── KNOWN_LIMITATIONS.md

📁 代码规范
├── CODE_DISCIPLINE_REVIEW.md
├── VISITOR_USAGE_REVIEW.md
└── REFACTOR_GUIDE_v2.md

📁 问题追踪
├── ISSUES_SUMMARY.md
├── ARCHITECTURE_IMPROVEMENT.md           🔄 讨论中
└── OPENCHIP_QA_*.md                     (4个)

📁 需求文档
├── REQ5_6_7_8_*.md                      (2个)
└── REQ8_SIGNAL_TRACER_*.md

📁 已归档 (docs/archive/)
└── README.md                            说明
    └── ... 18 个过时文档
```

### 按状态分类

```
✅ 已完成 (5个架构文档)
├── FINAL_SCHEMA_DECISION.md
├── DATAFLOW_ANALYSIS_ARCHITECTURE.md
├── CONTROL_FLOW_ANALYSIS.md
├── IMPLEMENTATION_RELATION.md
└── IMPLEMENTATION_RELATION_CONTROL_FLOW.md
└── SCHEMA_COMPARISON_V2.md

🔄 讨论中 (2个)
├── ARCHITECTURE_IMPROVEMENT.md
└── TODO.md

📋 待执行 (架构已设计)
├── DataFlow 实现
└── ControlFlow 实现

📦 归档 (18个)
└── docs/archive/README.md
```

---

## 六、任务追踪看板

### DataFlow 数据流分析 ✅ 已完成

| 任务 | 优先级 | 状态 | 说明 |
|------|--------|------|------|
| DataFlowSegment 实现 | P1 | ✅ 已完成 | 单步驱动 |
| DataFlowPath 实现 | P1 | ✅ 已完成 | 完整路径 |
| DataFlowResult 实现 | P1 | ✅ 已完成 | 结果封装 |
| DataFlowAnalyzer 实现 | P1 | ✅ 已完成 | 路径搜索 (BIT_SELECT + Struct 支持) |

### ControlFlow 控制流分析

| 任务 | 优先级 | 状态 | 说明 |
|------|--------|------|------|
| ConditionInfo 实现 | P2 | 📋 待执行 | 条件信息 |
| StateTransition 实现 | P2 | 📋 待执行 | 状态转换 |
| ControlFlowResult 实现 | P2 | 📋 待执行 | 结果封装 |
| ControlFlowAnalyzer 实现 | P2 | 📋 待执行 | 分支覆盖分析 |

---

## 七、快速导航

| 需要查看 | 查看文档 |
|---------|----------|
| **DataFlow 是什么** | `FINAL_SCHEMA_DECISION.md` |
| **DataFlow 怎么实现** | `DATAFLOW_ANALYSIS_ARCHITECTURE.md` |
| **ControlFlow 是什么** | `CONTROL_FLOW_ANALYSIS.md` |
| **现在要做什么** | `TODO.md` |
| **项目介绍** | `README.md` |
| **遇到问题** | `ISSUES_SUMMARY.md`, `KNOWN_LIMITATIONS.md` |
| **历史归档** | `docs/archive/README.md` |

---

## 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-24 | 创建 DOC_INDEX，梳理文档状态 |