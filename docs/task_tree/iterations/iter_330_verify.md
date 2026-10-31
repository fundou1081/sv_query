# Iteration 330: verify 双向一致性 + claim（PLAN P34.1）

**Metadata**:
- **Iteration #**: 330
- **Task Tree Level**: L2（PLAN `P34.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "按这个顺序逐个来做"）
- **Outcome**: ✅ 完成（consistency + claim；2653 passed）

## 🎯 目标

把工具从“查询”推进到“客观检查”：
- fanin/fanout 互逆；
- path 正/反向；
- connection 双向映射；
- bit parent/bit_range 自洽；
- claim 三态（verified/contradicted/unknown）。

## 🔧 实现

新增 core 命令：

```
svq verify consistency [--checks reciprocity,bit,connection] [--signal] [--max-nodes 200]
svq verify claim --claim JSON | --claim-file ...
```

### consistency

- **reciprocity**：抽样信号节点（默认 200；`--signal` 限定），查 fanin/fanout 互逆；
  跳过实例/常量/表达式/parent-child 聚合（它们不是 fanin/fanout 语义边）。
- **bit_mapping**：parent 存在、parent bit 范围、节点宽度、id 前缀；动态位元数据缺失 → skipped。
- **connection**：MIG port→internal；internal/port 节点存在。
- 输出 `verified` / `total_violations` / `unknown_checks` / 每项 violations。

### claim

| type | 判定 |
|---|---|
| driver | 在 fanin(depth=1 或 transitive) |
| path | 给定 nodes 逐边；`bidirectional=true` 同时查反向；无 nodes 查可达 |
| connection | MIG port.internal_signal 相等 |
| bit | target/source 位节点直接边 |

- `ok=true` 表示命令执行成功；结论看 `result.status`；
- 无法证明 → `unknown`（例如位节点缺失、端点未解析），不伪造 contradicted。

## 🐛 发现并规避

1. `trace_fanout(..., include_control=True)` 引用不存在的 `EdgeKind.CONTROL`
   → AttributeError；verify 不使用该 flag（已记录为待修 API 缺口）。
2. 直接把所有节点纳入互逆检查会误报：
   - 实例节点 `top.u` 的 fanin 包含端口聚合；
   - 父总线/位切片是聚合关系；
   - 常量 `0/1` 的 fanout 不互逆。
   修正为只检查信号 kind + 跳过 parent-child。
3. `verified` 不能只看 violations=0：connection check 不可用时是 unknown，
   `verified=false` 且 `unknown_checks` 显式列出。

## 🧪 测试

新增 `test_verify.py`（9）：
consistency clean / bit，driver 正反，path 正反 + 双向，connection 正反，
bit 正反，位节点缺失 unknown，invalid claim。

契约测试 +2：verify consistency/claim 字段。
全量 **2653 passed / 0 failed**。

## ⚠️ 边界

- reciprocity 是**抽样**（默认 200），不是全图证明；`truncated` 标识。
- connection 依赖 MIG；无 MIG 时 status=unknown。
- bit claim 只验证直接边，不做跨多跳位映射证明。
- `include_control` 仍是已知 API 缺口（后续单修）。

## 🔗 相关

- 计划: [PLAN.md P34.1](../../../PLAN.md)
- 产品方向: [product_direction_2026-10-31](../../architecture/product_direction_2026-10-31.md)
