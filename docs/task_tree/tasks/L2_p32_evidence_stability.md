# L2 — P32 trace evidence 稳定性

**Created**: 2026-10-31 GMT+8
**方豆**: "主功能还是 focus 在 trace，并能提供稳定的 evidence 上。"

## 现状问题

- `always` 驱动的 evidence 可能只有 `enclosing_if`，缺 `enclosing_always`
- `source_text` 可能为空（即使 `source_location` 存在）
- credibility 0.4 等低分没有明确原因

## 验收

- 有 driver 边、有 source_location 的 always/continuous evidence：source_text 非空
- always_ff/comb 场景补 enclosing_always（即使 condition_ast 存在）
- evidence 字段与契约一致；新增稳定性测试
- 全量门禁 0 failed

## 完成记录（2026-10-31）

- P32.1/P32.2 ✅ iter_328：always 回退、LHS 赋值行、snippet 关键字、行号修正
- 新增 3 个 evidence 稳定性测试；全量 2635 passed
