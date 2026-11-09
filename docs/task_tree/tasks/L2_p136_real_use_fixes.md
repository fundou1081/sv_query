# Task: P136 real-use fixes

**状态**: ✅ 完成
**日期**: 2026-11-09

## 目标

修复 P134 使用场景中暴露的纪律/可用性问题。

## 交付

- source-known warning（真实 module declaration，非 raw text）；
- architecture `--from-snapshot`；
- TB→RTL candidate join（single/multiple/not_found）；
- unknown machine flag（显式 unknown_kind）；
- solve…before / dist 使用 semantic syntax AST，不是 regex；
- 统一 constraint serialization；
- 回归：FIFO visibility、warning、architecture snapshot、TB join、solve/dist、unknown。
