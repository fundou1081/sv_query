# L2 — P33 Grounding P0：canonical signal identity

**Created**: 2026-10-31 GMT+8
**方豆**: "按这个方向推进"（产品方向 P0 grounding）。

## 目标

1. **精确解析**：完整 id 直接命中。
2. **相对解析**：`u.a` / `a` 唯一后缀命中 → 解析到完整 id。
3. **位回退**：`y[3]` 位节点不存在但 `y` 总线存在 → found + bit_base_fallback。
4. **not_found**：无任何匹配 → `E_SIGNAL_NOT_FOUND`，不能返回 ok=true 空结果。
5. **ambiguous**：多个匹配 → `E_SIGNAL_AMBIGUOUS` + candidates，让 agent 消歧。
6. **resolved_signal / resolution** 进入 trace JSON 契约。

## 验收

- fanin/fanout/impact/evidence 的未知信号显式错误；
- 相对名唯一可解析；歧义给候选；
- 现有位查询行为保持；
- 测试 + 契约 + 文档；全量门禁 0 failed。

## 完成记录（2026-10-31）

- P33.1/P33.2 ✅ iter_329：5 种 resolution + 4 命令接入 + 契约/测试
- 全量 2642 passed；golden 重新生成
