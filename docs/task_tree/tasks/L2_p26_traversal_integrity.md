# L2 — P26 遍历完整性与运行期系统函数

**Created**: 2026-10-31 GMT+8
**方豆**: "回到主线任务"（此前批准的 1/2/3 中的第 3 项）。

## P26.1 遍历完整性

- `fanin`/`fanout` 每 signal 输出：
  - `truncated_by_depth`: 有结果节点在 depth 边界仍存在未展开的边
  - `cycles_detected`: reachable 子图在当前遍历方向上有环；capped 三态（true/false/null）
- 不改变结果集合；只报告“结果可能不完整”的原因。
- `max_results` 的 `truncated` 保持独立。

## P26.2 运行期系统函数

- `$random` / `$urandom` / `$urandom_range` / `$time` / `$stime` / `$realtime` 等
  出现在表达式/条件 → 目标标 `runtime_system_call=true` + `precision=unknown`。
- `$clog2` / `$bits` 等 elaboration/常量内建**不标**。
- 下游/位子树传播（与 function_call 类似）；节点字段 + signal 字段。

## P26.3

- CLI 测试 + 序列化/缓存测试 + 文档。


## 完成记录（2026-10-31）

- P26.1 ✅ iter_321：truncated_by_depth / cycles_detected（capped null）
- P26.2 ✅ iter_322：$random 等 runtime_system_call=true + unknown；修对象 repr 节点 id
- P26.3 ✅ 6 新测试；3 golden 重生成；smoke 全 PASS；全量 2609 passed
