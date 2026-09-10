# 归档: 2026-09-08 文档清理 (iter_171)

> **来源**: 方豆 "先进行A，先把文档清理" — A 路线第一项。
> **原则**: **只归档不删除** (信息不丢, 历史可追); 归档 ≠ 无效, 只是不再是
> 现行真相源 (现行文档见 [../../INDEX.md](../../INDEX.md))。

## 为什么归档 (63 份)

| 类别 | 份数 | 原因 |
|---|---|---|
| 可视化历史稿 (VIZ_* / viz_v2_* / ELK_* / ARCH_VISUALIZATION / DATAFLOW_VIZ_SPEC / V100_ELK_COMPOUND_GRAPH) | 13 | L4 可视化当前 focus 之外; 现行入口 = `docs/VISUALIZATION.md` + `VIZ_COMMANDS.md` + `VIZ_DESIGN_SPEC.md` |
| 计划/重构稿 (P1_GRAPH_BUILDER_REFACTOR / REFACTOR_* / BITSELECT_* / REQUIREMENT_* / PENDING_FEATURES / SIGNAL_GRAPH_ANALYSIS_REQUIREMENTS / SIGNAL_TRACER_REQUIREMENTS 等) | 20 | 已完成或已被现行 Spec/规划取代 |
| 审计与一次性报告 (ARCHITECTURE_REVIEW_* / OPENCHIP_QA_* / SCAN_REPORT / ISSUES_SUMMARY / doc_vs_code_audit / CODE_DISCIPLINE* / DISCIPLINE_VIOLATIONS / NAPLESPU_TEST_ISSUES) | 15 | 时点报告; 纪律类已由 `AGENTS.md` 取代 |
| 已合并索引 (DOC_INDEX.md / LLM_INDEX.md) | 2 | 合并进 `docs/INDEX.md` (唯一入口) |
| 专向参考稿 (SYNTAX_KIND_HANDLER_MAP / HANDLER_WRITING_GUIDE / GRAPH_CATALOG / SIGNAL_GRAPH_TECH_TEST_MAP / DESIGN_COVERGROUP_EXTRACTION / DESIGN_pipeline_dag / DESIGN_PYSALNG_VISIT_BASED_ONHANDLER) | 7 | 对应机制已重构/被现行文档吸收 |
| 实验功能薄文档 (CDC_ANALYSIS / TIMING_ANALYSIS / RISK_ANALYSIS / BACKPRESSURE_HANDSHAKE_DEV_PLAN) | 4 | 实验功能入口 = `docs/EXPERIMENTAL_FEATURES.md` |
| 重复文档 (docs/TESTING.md) | 1 | 根 `TESTING.md` 为唯一测试入口 (AGENTS 设施表) |
| sim 旧报告 (TEST_REPORT / TEST_REPORT_FULL / TEST_PLAN / DEVELOPMENT_PLAN) | 4 | 时点报告, 计数已失真 |
| 根目录过期设计稿 (DESIGN_composition_chain / DESIGN_cross_module_tracking) | 2 | 05-12 稿, 已被现行架构文档取代 |

## 引用约定

- 现行文档**不要**再链接归档内文件 (由 `tools/check_docs.py` 检查)。
- 历史记录 (CHANGELOG / memory/ / task_tree/iterations/) 允许保留归档引用 — 它们是快照。
