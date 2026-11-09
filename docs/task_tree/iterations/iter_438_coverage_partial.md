# Iteration 438: Coverage partial extraction（P131）

**状态**: ✅
**日期**: 2026-11-09

## 根因

pyslang CovergroupBody 内建名 `start`/`stop` 遮蔽外层标识符；
不是 inherited base member。

## 实现

- `SVCompiler.get_partial_root()`
- `CovergroupExtractor.extract(allow_partial=True)`
- `trace covergroups --partial`
- partial 时保留 errors，默认严格不变。

## 验证

- 新测试 3 passed；
- 现有 covergroup regression 87 passed；
- I2C 11 covergroups + 20 errors。

## 边界

只保证定义结构，不保证被遮蔽表达式的语义；未接 tool intent/TB snapshot。
