# Iteration 416: Blind realistic validation（P110）

**状态**: ✅（partial pass）
**日期**: 2026-11-08

## 首轮

DeepSeek 3/5，2 false-confident：

- 1 个字段命名差异（benchmark alias）；
- 1 个真实 path 默认 bug（选最长变体绕路）。

## 修复

- path 默认最短；`granular=true` 才选最长；
- benchmark 统一 driver_ids/load_ids alias。

## fresh set B

- MiniMax 5/5，0 false-confident；
- DeepSeek 4/5，0 false-confident；
- DeepSeek 唯一失败为 JSON 单引号格式。

## 结论

false-confident 指标通过；exact 9/10；仍需 P111/P112。
