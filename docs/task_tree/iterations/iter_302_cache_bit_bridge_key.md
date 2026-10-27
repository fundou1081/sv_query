# Iteration 302: 图缓存 key 纳入位桥模式（PLAN P13.1 / P0 修复）

**Metadata**:
- **Iteration #**: 302
- **Task Tree Level**: L2（[L1_cache_bit_bridge_mode](../tasks/L1_cache_bit_bridge_mode.md) / PLAN `P13.1`）
- **Created**: 2026-10-27 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "嗯，开始修"）
- **Outcome**: ✅ 完成（静默错误修复；2494 passed）

## 🎯 问题（P0）

`UnifiedTracer._graph_cache_key` = 内容 hash + `-v2-t{target}`，**不含 `SVQ_BIT_BRIDGE` 模式**：

```
one 建图（5 节点）→ 切 SVQ_BIT_BRIDGE=full → 命中旧图仍 5 节点（应 37）
full 建图（37 节点）→ 切回 one → 拿到过度展开的图
```

查询结果静默错误（不报错、不变慢）。

## 🔧 修复

- `_graph_cache_key` 末尾加 `-bb{one|full}`；非法值按 `one` 归一（与 GraphBuilder 一致）
- 旧 key 无该后缀 → 自然失效重建（**不需要** bump `CACHE_VERSION`，保持 1.4）

## 📊 效果（实测）

| 序列 | 修复前 | 修复后 |
|---|---|---|
| one → full | 5（错误，命中 old key） | **37**（重建） |
| full → one | 37（错误，过度展开） | **5**（重建/命中 one key） |
| one → one（同模式） | 命中 | **命中**（不新增条目） |
| 缓存条目数 | 1（串模式） | **2**（两种模式各一份） |

## 🧪 测试

新增 `test_bit_bridge_cache.py`（5 个）：
- key 含 `-bbone`/`-bbfull`；非法模式归一到 one
- 端到端 one→full→one 节点数 5→37→5
- 同模式仍命中缓存（条目数不增）
- full 模式独立缓存条目（2 份）

更新 `test_graph_cache_scope.py` 的 key 后缀断言（`-tall` → `-tall-bbone`）。

## ✅ 验证

- 全量：2489 → **2494 passed / 0 failed**
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿
- 缓存版本保持 1.4（key 语义变化即可失效）

## 🔗 相关

- 计划: [PLAN.md P13.1](../../../PLAN.md)
- 评审: [trace_capability_review_2026-10-27](../../architecture/trace_capability_review_2026-10-27.md)
