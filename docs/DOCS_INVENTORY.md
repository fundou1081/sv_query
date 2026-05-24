# docs/ 目录文档梳理

> 创建时间: 2026-05-24
> 状态: 待清理

---

## 文档总数统计

| 类别 | 数量 | 说明 |
|------|------|------|
| 总文档数 | 40 | |
| 核心文档 | 4 | TODO, PROJECT_PLAN, README, USER_GUIDE |
| 架构设计 | 8 | DataFlow/ControlFlow 相关 |
| 开发指南 | 5 | 重构指南、代码审查 |
| 问题追踪 | 12 | Issues、QA 问题 |
| 需求文档 | 3 | 需求技术评估 |
| **过时/冗余** | **17** | 建议删除 |

---

## 分类文档清单

### 【核心文档 - 保持更新】✅

| 文件 | 最后修改 | 说明 |
|------|----------|------|
| `TODO.md` | 2026-05-24 10:40 | 项目待办清单 (最新) |
| `PROJECT_PLAN.md` | 2026-05-23 11:04 | 项目计划 |
| `README.md` | 2026-05-15 07:36 | 项目介绍 |
| `USER_GUIDE.md` | 2026-05-17 12:01 | 用户指南 |

### 【架构设计 - DataFlow/ControlFlow】✅

| 文件 | 最后修改 | 说明 |
|------|----------|------|
| `FINAL_SCHEMA_DECISION.md` | 2026-05-24 10:40 | **最终架构决定** ⭐ 核心 |
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | 2026-05-24 09:42 | DataFlow 架构设计 |
| `CONTROL_FLOW_ANALYSIS.md` | 2026-05-24 10:07 | ControlFlow 架构设计 |
| `IMPLEMENTATION_RELATION.md` | 2026-05-24 10:43 | 实现关系 DataFlow |
| `IMPLEMENTATION_RELATION_CONTROL_FLOW.md` | 2026-05-24 10:44 | 实现关系 ControlFlow |
| `SCHEMA_COMPARISON_V2.md` | 2026-05-24 10:29 | Schema 对照 V2 ⭐ |
| `SCHEMA_COMPARISON.md` | 2026-05-24 09:57 | Schema 对照 (旧) ⚠️ |
| `ARCHITECTURE_COMPARISON.md` | 2026-05-24 09:54 | 架构对照 (旧) ⚠️ |

### 【开发指南】⚠️ 部分过时

| 文件 | 最后修改 | 说明 |
|------|----------|------|
| `REFACTOR_GUIDE_v2.md` | 2026-05-19 21:59 | 重构指南 V2 |
| `REFACTOR_GUIDE.md` | 2026-05-19 16:02 | 重构指南 (旧) ⚠️ |

### 【代码审查】⚠️ 部分过时

| 文件 | 最后修改 | 说明 |
|------|----------|------|
| `ARCHITECTURE_IMPROVEMENT.md` | 2026-05-24 08:50 | 架构改善 (Visitor 重构) |
| `CODE_DISCIPLINE_REVIEW.md` | 2026-05-23 11:10 | 代码规范审查 |
| `VISITOR_USAGE_REVIEW.md` | 2026-05-23 11:44 | Visitor 使用审查 |
| `GRAPH_BUILDER_DEEP_REVIEW.md` | 2026-05-23 11:13 | Graph Builder 深度审查 |

### 【问题追踪】⚠️ 大部分已过时

| 文件 | 最后修改 | 说明 |
|------|----------|------|
| `ISSUES_SUMMARY.md` | 2026-05-18 10:05 | 问题汇总 |
| `KNOWN_LIMITATIONS.md` | 2026-05-23 10:54 | 已知限制 |

### 【需求文档】✅ 保留参考

| 文件 | 最后修改 | 说明 |
|------|----------|------|
| `REQ5_6_7_8_DRIVER_LOAD_ANALYSIS.md` | 2026-05-17 00:09 | 需求 5-8 技术评估 |
| `REQ5_6_7_8_TECHNICAL_EVALUATION.md` | 2026-05-17 00:18 | 需求 5-8 技术评估 |
| `REQ8_SIGNAL_TRACER_TECHNICAL_EVALUATION.md` | 2026-05-17 00:04 | 需求 8 技术评估 |

---

## 过时/冗余文档清单

以下 17 个文档建议删除或归档:

### 架构相关 (5个)
| 文件 | 原因 |
|------|------|
| `SCHEMA_COMPARISON.md` | 被 SCHEMA_COMPARISON_V2.md 替代 |
| `ARCHITECTURE_COMPARISON.md` | 被 FINAL_SCHEMA_DECISION.md 整合 |
| `GRAPH_BUILDER_REFACTOR_PLAN.md` | 有更详细的版本 |
| `GRAPH_BUILDER_REFACTOR_DETAILED_PLAN.md` | 项目已完成重构，此文档过时 |
| `SEMANTIC_AST_REFACTOR_*.md` | 语义 AST 重构已完成 |

### Issue 相关 (9个)
| 文件 | 原因 |
|------|------|
| `ISSUE_17_ROOT_CAUSE.md` | Issue 17 已修复 |
| `ISSUE_17_19_20_FIX_PLAN.md` | Issues 17/19/20 已修复 |
| `ISSUE_17_CASE_BS_MULT.md` | Issue 17 已修复 |
| `ISSUE_18_ROOT_CAUSE.md` | Issue 18 已修复 |
| `ISSUE_18_CONCLUSION.md` | Issue 18 已修复 |
| `ISSUE_DISCUSSION.md` | 已整合到 ISSUE_ROOT_CAUSE.md |
| `ISSUE_ROOT_CAUSE.md` | 已整合到其他文档 |
| `SVQUERY_ISSUES_AND_FIXES.md` | 问题已修复，文档过时 |
| `ISSUE_DISCUSSION.md` | 已整合到 ISSUE_ROOT_CAUSE.md |

### 重构指南 (1个)
| 文件 | 原因 |
|------|------|
| `REFACTOR_GUIDE.md` | 被 REFACTOR_GUIDE_v2.md 替代 |

### API 迁移 (1个)
| 文件 | 原因 |
|------|------|
| `API_MIGRATION_trees_to_sources.md` | API 迁移已完成 |

### QA 问题 (1个)
| 文件 | 原因 |
|------|------|
| `OPENCHIP_QA_*.md` | QA 问题已处理 |

---

## 清理建议

### 方案: 移动到 docs/archive/ 目录

```bash
mkdir -p docs/archive

# 移动过时文档
git mv SCHEMA_COMPARISON.md docs/archive/
git mv ARCHITECTURE_COMPARISON.md docs/archive/
git mv GRAPH_BUILDER_*.md docs/archive/
git mv SEMANTIC_AST_*.md docs/archive/
git mv ISSUE_*.md docs/archive/
git mv REQ8_SIGNAL_TRACER_TECHNICAL_EVALUATION.md docs/archive/
git mv REFACTOR_GUIDE.md docs/archive/
git mv API_MIGRATION_trees_to_sources.md docs/archive/
```

### 保留的核心文档 (12个)

```
docs/
├── TODO.md                              # 项目待办
├── FINAL_SCHEMA_DECISION.md             # 架构决定 ⭐
├── DATAFLOW_ANALYSIS_ARCHITECTURE.md    # DataFlow 架构
├── CONTROL_FLOW_ANALYSIS.md             # ControlFlow 架构
├── SCHEMA_COMPARISON_V2.md               # Schema 对照 ⭐
├── IMPLEMENTATION_RELATION.md           # 实现关系
├── IMPLEMENTATION_RELATION_CONTROL_FLOW.md
├── PROJECT_PLAN.md                      # 项目计划
├── README.md                            # 项目介绍
├── USER_GUIDE.md                        # 用户指南
├── KNOWN_LIMITATIONS.md                # 已知限制
└── REQ5_6_7_8_*.md                     # 需求文档
```

---

## 执行清理

### Step 1: 创建归档目录
```bash
mkdir -p docs/archive
```

### Step 2: 移动文档
```bash
git mv docs/SCHEMA_COMPARISON.md docs/archive/
git mv docs/ARCHITECTURE_COMPARISON.md docs/archive/
# ... etc
```

### Step 3: 提交
```bash
git add -A && git commit -m "docs: archive outdated documents"
```

---

## 更新日志

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-05-24 | 创建 | 文档梳理完成 |