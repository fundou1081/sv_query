# docs/archive/ - 历史文档归档

> **⚠️ 这些文档已过时，仅供获取历史信息，不适用于现在。**

---

## 归档说明

本目录存放已过时的文档，仅保留作为历史参考。

**当前项目架构请参阅:**
- `docs/FINAL_SCHEMA_DECISION.md` - 最终架构决定
- `docs/DATAFLOW_ANALYSIS_ARCHITECTURE.md` - DataFlow 架构设计
- `docs/CONTROL_FLOW_ANALYSIS.md` - ControlFlow 架构设计
- `docs/SCHEMA_COMPARISON_V2.md` - Schema 对照
- `docs/TODO.md` - 项目待办清单

---

## 归档文档列表

### 架构相关 (2个)
| 文件 | 原用途 | 归档原因 |
|------|--------|----------|
| `SCHEMA_COMPARISON.md` | Schema 对照 | 被 SCHEMA_COMPARISON_V2.md 替代 |
| `ARCHITECTURE_COMPARISON.md` | 架构对照 | 被 FINAL_SCHEMA_DECISION.md 整合 |

### Graph Builder 重构 (3个)
| 文件 | 原用途 | 归档原因 |
|------|--------|----------|
| `GRAPH_BUILDER_REFACTOR_PLAN.md` | 重构计划 | 被更详细版本替代 |
| `GRAPH_BUILDER_REFACTOR_DETAILED_PLAN.md` | 详细重构计划 | 重构已完成 |
| `GRAPH_BUILDER_DEEP_REVIEW.md` | 深度审查 | 重构已完成 |

### 语义 AST 重构 (2个)
| 文件 | 原用途 | 归档原因 |
|------|--------|----------|
| `SEMANTIC_AST_REFACTOR_ASSESSMENT.md` | 重构评估 | 重构已完成 |
| `SEMANTIC_AST_REFACTOR_TODO.md` | 重构待办 | 重构已完成 |

### Issue 追踪 (9个)
| 文件 | 原用途 | 归档原因 |
|------|--------|----------|
| `ISSUE_17_ROOT_CAUSE.md` | Issue 17 根因分析 | Issue 已修复 |
| `ISSUE_17_CASE_BS_MULT.md` | Issue 17 case 分析 | Issue 已修复 |
| `ISSUE_17_19_20_FIX_PLAN.md` | Issues 17/19/20 修复计划 | Issues 已修复 |
| `ISSUE_18_ROOT_CAUSE.md` | Issue 18 根因分析 | Issue 已修复 |
| `ISSUE_18_CONCLUSION.md` | Issue 18 结论 | Issue 已修复 |
| `ISSUE_DISCUSSION.md` | Issue 讨论 | 已整合 |
| `ISSUE_ROOT_CAUSE.md` | Issue 根因 | Issues 已修复 |
| `SVQUERY_ISSUES_AND_FIXES.md` | SVQuery 问题与修复 | Issues 已修复 |

### 重构指南 (1个)
| 文件 | 原用途 | 归档原因 |
|------|--------|----------|
| `REFACTOR_GUIDE.md` | 重构指南 | 被 REFACTOR_GUIDE_v2.md 替代 |

### API 迁移 (1个)
| 文件 | 原用途 | 归档原因 |
|------|--------|----------|
| `API_MIGRATION_trees_to_sources.md` | API 迁移指南 | 迁移已完成 |

---

## 归档时间

2026-05-24

## 归档操作

```bash
git mv docs/SCHEMA_COMPARISON.md docs/archive/
git mv docs/ARCHITECTURE_COMPARISON.md docs/archive/
# ... 共 17 个文档
```