# Task: P137 discipline remediation

**状态**: ✅ 完成
**日期**: 2026-11-09

## 背景

Worker independent discipline audit verdict = BLOCK：
- solve/dist regex 导致 `check_semantic_regex` 失败；
- FIFO 边无条件进入共享图，verify/dataflow/paths/fanin 语义泄漏；
- 其他 schema/一致性/回归问题。

## 交付

- semantic syntax AST solve/dist；
- 统一 `edge_visibility`，FIFO 默认不可见/显式 build；
- verify/dataflow/paths/fanin 回归；
- unknown_kind 显式、constraint dict 单实现；
- source-known 用真实 ModuleDeclarationSyntax；
- task/overview/docs 补齐；
- `check_crap --base` commit range。

## 边界

`_analyze_block` O(E²) 性能 nit 未改（不影响正确性）。
