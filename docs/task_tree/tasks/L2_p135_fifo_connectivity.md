# Task: FIFO / bus connectivity（P135）

**状态**: ✅ 完成
**日期**: 2026-11-09

## 目标

修复 P134 的 FIFO 读/写跨边界断链与父总线 orphan。

## 交付

- EdgeKind.FIFO + FifoBridgeBuilder；
- `paths --through-fifo` 显式跨 FIFO；
- 父总线 fanin 聚合 bit driver；
- FIFO visibility 回归测试（directed/undirected/dataflow/verify/fanin）。

## 边界

FIFO 边是 sequential boundary；默认查询不可见；旧 snapshot 无该边。
