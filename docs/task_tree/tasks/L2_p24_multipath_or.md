# L2 — P24 多路径条件 OR

**Created**: 2026-10-31 GMT+8
**方豆指令**: "多路径条件 OR 这个也很重要，但要保留原本的多条件，这样我能区分出来"。

## 验收

- 同一 driver 多条路径：`condition = (c1 && c2) || (c3)`。
- 保留 `condition_paths`：每路径 `{condition, path:[原始条件...]}`。
- `conditions` 保留多条件（每路径组合），不折叠成单个字符串。
- 直接边多条件同样 OR + 保留列表。
- 枚举有上限（per-node 路径数/深度/展开预算）；超限 `condition_truncated=true`。
- 无条件路径存在时：整体 `condition=""` + `condition_unconditional=true`（不能把“总是成立”错写进 OR）。

## 完成记录

- P24.1 ✅ iter_320：多路径 DFS OR；conditions/condition_paths 保留原条件；
  无条件路径优先；depth=1 不组合；truncated 标记
- P24.2 ✅ 4 新测试；3 golden 重生成；真实 smoke 全 PASS；全量 2598 passed
