# Task: P139 boundary-aware guided trace

**状态**: ✅ 完成（worker independent review: APPROVE WITH NITS，nits 已修）
**日期**: 2026-11-09

## 交付

- `trace frontier` 命令（fanin/fanout/both）；
- 通用 boundary reason + next probes；
- 不自动分类 FIFO、不添加图边；
- agent 协议 `docs/agent/GUIDED_TRACE.md`；
- 5 个回归测试；
- worker 独立验证（MiniMax `svq-p139-review2`）。

## 边界

跨项目边界仍需显式 adapter/boundary map；不是 two-endpoint auto relation。
