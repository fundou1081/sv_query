# L1 — 图缓存 key 纳入 SVQ_BIT_BRIDGE 模式（P13.1）

**Status**: ✅ 完成（iter_302）
**Created**: 2026-10-27

## 问题（P0 静默错误）

`UnifiedTracer._graph_cache_key` = `{content_hash}-v2-t{target}`，未含位桥模式。
实测：`one` 建图（5 节点）后切 `SVQ_BIT_BRIDGE=full` 仍命中旧图（应为 37 节点）；
反方向 `full→one` 会拿到过度展开的图。查询静默错误。

## 修法

- key 加 `-bb{one|full}`（非法值按 `one` 归一，与 GraphBuilder 行为一致）
- 旧 key 无后缀 → 自然失效重建（不需要 bump CACHE_VERSION）
- 回归测试：两种模式 key 不同；端到端切换模式节点数正确；同模式仍命中

## 验收

- [x] `_graph_cache_key` 在 one/full/非法值下分别正确
- [x] one→full 重建（节点数变）；full→one 重建（节点数变）
- [x] 同模式重复 build 仍命中缓存
- [x] 全量门禁 0 failed
