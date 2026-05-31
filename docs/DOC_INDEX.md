# 📚 SVQuery 文档目录

> 更新日期：2026-05-31
> 状态：已整理

---

## 📊 文档统计

| 位置 | 数量 |
|------|------|
| `docs/` 根目录 | 64 |
| `docs/architecture/` | 9 |
| `docs/skeleton/` | ~ |
| `docs/archive/` | 21 |
| **总计** | **90+** |

---

## 🗂️ 分类目录结构

```
docs/
├── README.md                    # 项目介绍
├── USER_GUIDE.md                # 用户指南
├── TODO.md                      # 待办事项
├── PROJECT_PLAN.md              # 项目计划
│
├── core/                        # 核心架构 ⭐
│   ├── FINAL_SCHEMA_DECISION.md
│   ├── ARCHITECTURE_DEEP_REVIEW.md
│   └── GRAPH_BUILDER_REVIEW.md
│
├── dataflow/                    # DataFlow 分析
│   ├── DATAFLOW_ANALYSIS_ARCHITECTURE.md
│   ├── DATAFLOW_IMPLEMENTATION_PLAN.md
│   └── SIGNAL_GRAPH_ANALYSIS_REQUIREMENTS.md
│
├── controlflow/                # ControlFlow 分析
│   ├── CONTROL_FLOW_ANALYSIS.md
│   ├── CONTROL_FLOW_DESIGN.md
│   ├── CONTROL_FLOW_IMPROVEMENTS.md
│   └── IMPLEMENTATION_RELATION_CONTROL_FLOW.md
│
├── requirements/                # 需求文档
│   ├── REQ5_6_7_8_*.md
│   ├── REQUIREMENT_SVA_ANALYSIS.md
│   └── REQUIREMENT_UVM_TESTBENCH_STRUCTURE.md
│
├── issues/                     # 问题追踪
│   ├── ISSUES_SUMMARY.md
│   ├── KNOWN_LIMITATIONS.md
│   ├── OPENCHIP_QA_*.md
│   └── OPENCHIP_QA_ROUND4_REPORT.md
│
├── sva/                        # SVA / Timing / CDC
│   ├── SVA_ANALYSIS.md
│   ├── TIMING_ANALYSIS.md
│   └── CDC_ANALYSIS.md
│
├── design/                     # 设计方案
│   ├── DESIGNER_PLAN.md
│   ├── DESIGN_BOUNDARY_CONTROL.md
│   ├── DESIGN_COVERGROUP_EXTRACTION.md
│   └── DESIGN_PYSALNG_VISIT_BASED_ONHANDLER.md
│
├── guides/                     # 开发指南
│   ├── REFACTOR_GUIDE_v2.md
│   ├── HANDLER_WRITING_GUIDE.md
│   ├── SYNTAX_KIND_HANDLER_MAP.md
│   ├── CODE_DISCIPLINE_REVIEW.md
│   └── TDD_DEVELOPMENT_PLAN.md
│
├── schema/                     # Schema 相关
│   ├── SCHEMA_COMPARISON_V2.md
│   └── SIGNAL_EXPRESSION_VISITOR_TEST_STATUS.md
│
├── skeleton/                   # Skeleton 规则 (已移动)
│   └── rules/
│
├── architecture/               # 子架构文档
│   ├── architecture.md
│   ├── CORE_RESTRUCTURE.md
│   ├── GRAPH_DIFF_DESIGN.md
│   └── SV_SYNTAX_ROADMAP.md
│
└── archive/                    # 过时文档 (已归档)
    ├── GRAPH_BUILDER_*.md
    ├── ISSUE_*.md
    └── REFACTOR_GUIDE.md
```

---

## 📋 核心文档 (必须保留)

| 文件 | 说明 | 优先级 |
|------|------|--------|
| `README.md` | 项目介绍 | ⭐⭐⭐ |
| `USER_GUIDE.md` | 用户指南 | ⭐⭐⭐ |
| `TODO.md` | 待办事项 | ⭐⭐⭐ |
| `PROJECT_PLAN.md` | 项目计划 | ⭐⭐⭐ |
| `FINAL_SCHEMA_DECISION.md` | 最终架构决定 | ⭐⭐⭐ |
| `ARCHITECTURE_DEEP_REVIEW.md` | 深度架构 Review | ⭐⭐ |
| `GRAPH_BUILDER_REVIEW.md` | GraphBuilder Review | ⭐⭐ |

---

## 📁 各目录说明

### `core/` - 核心架构
核心架构决策和 Review 文档

### `dataflow/` - DataFlow
数据流分析相关的架构设计

### `controlflow/` - ControlFlow
控制流分析相关的架构设计

### `requirements/` - 需求文档
来自需求方的技术评估和分析

### `issues/` - 问题追踪
Issue 汇总、QA 问题、已知限制

### `sva/` - SVA 分析
SystemVerilog Assertion、Timing、CDC 分析

### `design/` - 设计方案
具体功能模块的设计方案

### `guides/` - 开发指南
重构指南、Handler 编写规范、代码规范

### `schema/` - Schema
Schema 对照和测试状态

### `skeleton/` - Skeleton 规则
UVM/SVA Skeleton 自动生成规则

### `architecture/` - 架构子文档
较为独立的架构分析文档

### `archive/` - 过时文档
已废弃或被替代的文档

---

## ⚠️ 待处理

### 1. 移动文档到分类目录

需要将根目录的文档移动到上述分类目录：

```bash
# 示例：移动 DataFlow 文档
mv docs/DATAFLOW_ANALYSIS_ARCHITECTURE.md docs/dataflow/
mv docs/DATAFLOW_IMPLEMENTATION_PLAN.md docs/dataflow/

# 移动 ControlFlow 文档
mv docs/CONTROL_FLOW_ANALYSIS.md docs/controlflow/
mv docs/CONTROL_FLOW_DESIGN.md docs/controlflow/

# 等等...
```

### 2. 确认 `docs/architecture/` 是否需要合并

`docs/architecture/` 中有 9 个文档，可能与 `core/` 重复

### 3. 确认 `docs/skeleton/` 位置

Skeleton 规则可能需要整合

---

## ✅ 已完成

- [x] 创建 `docs/DOC_INDEX.md` 目录索引
- [x] 识别 `docs/archive/` 中的 21 个过时文档
- [x] 建立分类目录结构

---

## ❓ 请确认

1. 分类目录结构是否合理？
2. 哪些文档需要移动到 `archive/`？
3. 是否需要删除一些文档？