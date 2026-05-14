# Architecture Documents

架构层面的设计文档，标记日期和时间。

---

## 目录

| 文档 | 日期 | 说明 |
|------|------|------|
| `signal_graph_mig_port_to_internal.md` | 2026-05-13 | SignalGraph + MIG port_to_internal 架构设计 |
| `code_framework_analysis.md` | 2026-05-13 | 代码框架核心模块职责分析 |
| `CONNECTION_vs_MIG_analysis.md` | 2026-05-13 | ConnectionExtractor vs MIG 功能对比分析 |
| `architecture.md` | - | sv_query 项目架构总览 |
| `CLASS_CONSTRAINT_PLAN.md` | 2026-05-11 | Class/Constraint 计划 |
| `SV_SYNTAX_ROADMAP.md` | 2026-05-10 | SV 语法路线图 |
| `GRAPH_DIFF_DESIGN.md` | 2026-05-14 | Graph Diff 设计方案（已实现 Phase 1-3） |
| `AI_REQUIREMENTS.md` | 2026-05-14 | AI 辅助开发需求文档 |
| `CORE_RESTRUCTURE.md` | 2026-05-14 | 核心模块重构计划 |

## 快照管理功能

- `svq snapshot save <file> -t <tag>` - 保存快照
- `svq snapshot list` - 列出快照
- `svq snapshot compare <tag1> <tag2>` - 对比两个快照
- 支持 `--git` 自动捕获 commit hash

---

## 文档更新记录

| 日期 | 时间 | 文档 | 更新内容 |
|------|------|------|----------|
| 2026-05-14 | 19:30 | `GRAPH_DIFF_DESIGN.md` | Phase 3 替代方案（方案一）+ SnapshotManager 已实现 |
| 2026-05-14 | 19:24 | `CORE_RESTRUCTURE.md` | 新增核心模块重构计划文档 |
| 2026-05-13 | 19:23 | 所有架构文档 | 从 docs/ 移动到 docs/architecture/ |
| 2026-05-13 | 19:16 | `signal_graph_mig_port_to_internal.md` | 新增：Option A 方案设计、数据流、代码变更 |
| 2026-05-13 | 14:45 | `code_framework_analysis.md` | 更新：整体架构分析 |
| 2026-05-13 | 01:47 | `CONNECTION_vs_MIG_analysis.md` | 初版 + 融合评估结论 |
| 2026-05-13 | 14:34 | `CONNECTION_vs_MIG_analysis.md` | MIG Phase 3 修复、语义区分 |

---

## 相关目录

- `../opentitan实战/` — OpenTitan RTL 实战验证文档