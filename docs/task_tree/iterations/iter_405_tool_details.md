# Iteration 405: svq_query details（P100）

**状态**: 进行中
**日期**: 2026-11-08

## 完成

- details=true 返回 id/kind/condition/distance；
- Node tests 14/14；
- mux snapshot 手工 probe：mux nodes/data sources 基本正确。

## 未解决

- selects 返回 top.sel 而非 top.u.sel；
- conditions 返回 4 条分支条件而非 2 条 select 条件；
- 需要 bounded neighborhood/alias 语义。
