# Iteration 400: skill pilot（P96）

**状态**: ✅（负结果）
**日期**: 2026-11-07

## 设计

- 3 cells（AXI / SERV / Pico）；
- DeepSeek-Flash；
- prompt vs prompt+可用 skill；
- 检查 DSH session 的 skill 调用。

## 结果

- 准确率 3/3 both；
- mean 46.5s prompt vs 62.7s skill；
- skill 条件 0 次 `skill` 工具调用（最终 session）；
- 因此不能归因于 skill 内容。

## 结论

模型不按 prompt 加载 skill；需要 harness 强制注入/allowlist，不扩 24 cells。
