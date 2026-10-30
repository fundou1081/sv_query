# L2 — P22 fanin/fanout 条件输出

**Created**: 2026-10-30 GMT+8
**方豆指令**: "先1 后2"（P22 为第 2 项）。

## 验收

- `fanin`/`fanout` 每个结果节点输出 `condition` / `conditions`
- signal 级输出 `conditions`（直接边并集）
- 无条件查询字段存在且为空
- if/else、ternary、嵌套条件、fanout 测试
- 不做路径条件组合（depth>1 边界记录）

## 完成记录（2026-10-30）

- P22.1 ✅ iter_318：直接边条件进 JSON；跳过 BIT_SELECT；异常不吞
- P22.2 ✅ 新增 5 测试；3 golden 重生成；全量 2591 passed
