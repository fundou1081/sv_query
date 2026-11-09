# Iteration 447: P136.4 unknown machine flag

**状态**: ✅
**日期**: 2026-11-09

## 实现

`verify claim` 的 unknown 增加：
- `machine.unknown_kind = unresolved_endpoint | unverifiable`
- `machine.unresolved_endpoint`

verified/contradicted schema 不变。

## 验证

test_verify.py 12 passed；bit unknown 断言 machine。

## 剩余

P136.5 solve…before / dist 提取。
