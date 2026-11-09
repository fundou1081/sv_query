# Task: P138 Project adaptation policy

**状态**: ✅ 完成
**日期**: 2026-11-09

## 决策

方案 A：core 不允许自动 FIFO 识别。

## 交付

- 删除 FifoBridgeBuilder / EdgeKind.FIFO / --through-fifo；
- 保留通用 bit fanin 聚合；
- `examples/project_adaptations/` 显式 boundary map 模板；
- `AGENTS.md` 铁律 12 + `docs/dev/PROJECT_ADAPTATION.md`。

## 边界

跨 FIFO 需要未来显式 adapter；core 不承诺自动跨 FIFO。
