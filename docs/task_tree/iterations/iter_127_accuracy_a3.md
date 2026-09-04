# Iteration 127: 准确性审计 A3 — 实例输出端口 internal 自环不计为驱动源

**Metadata**:
- **Iteration #**: 127
- **Task Tree Level**: L2 (signal graph 准确性审计 → 修复)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-04 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

按审计清单修 A3 (端口 DRIVER 自环计入驱动源, 轻微): fanin(实例输出端口)
会把"模块内部驱动"internal 自环标记自身列为一个源, 污染驱动集合,
truth 精确集断言被迫手动排除。

## 🔬 实际结果

### 根因诊断

自环分**两类**, 语义不同, 修复边界必须区分:

| 类型 | 产生点 | assign_type | 语义 | 处置 |
|---|---|---|---|---|
| 实例输出端口标记 | connection_extractor output 边1 (src=child_signal_id, dst=inst_port_id; 两 ID 恒相等 → 恒 src==dst) | `"internal"` | "该输出端口有模块内部驱动" 标记 | **跳过, 不计源** |
| 真操作数自环 | driver_extractor always_ff `state <= state+1` (LHS 与操作数同名) | `"nonblocking"` | 时序自更新真驱动 | **保留** |

- fanin 主循环 (`query/signal.py` 遍历 dst==signal_id 边) 对 src==dst **无条件**
  append 自身为驱动 (`# [NEW] 自环 (state = state) 应该被记录为驱动`) — A3 源。
- `_find_drivers` (depth=1 直接驱动路径) 同样无条件列 src — 第二处同病。
- 证据: `fanin(top.u_sub.y) = ['top.a', 'top.u_sub.y']` — 自身是 internal 标记。

### 修复 (查询层, 图结构不动)

`query/signal.py` 两处 (主循环 `_trace_drivers_recursive` + `_find_drivers`) 同规则:
src==dst 时查 `get_edges(src,dst)`, 若存在 `assign_type=="internal"` 且
`kind==DRIVER` 的自环 → `continue` (跳过); 否则 (nonblocking/continuous 真自环)
保留原 append。

选型: **A 查询层跳过** (最小影响: 图结构/序列化/可视化不变, internal 自环边
仍在图中供 out_edges 等使用; 只修 fanin 结果) vs B 改独立 marker 边 (图结构/
渲染/truth 大改)。选 A。

### 证据 (修复后)

- `fanin(top.u_sub.y)` (target, depth=None) `['top.a','top.u_sub.y'] → ['top.a']`
- `depth=1` → `['top.u_sub.a']` (直接真实驱动)
- no-target 类型级 → `['sub.a']` (forward-lookup 正常, 自环不再短路)
- `fanin(top.state)` (state<=state+1) 仍含 `top.state` — 真自环保留
- 图内 internal 自环边仍在 (out_edges/可视化用途不受影响)

### 验证

- 新增 unit 4 (test_accuracy_a1_a2.py TestA3SelfLoopNotDriverSource):
  depth=None 排除自身 / depth=1 排除自身 / state 自环保留 / 图边保留
- 全量回归: **2913 passed / 0 failed / 0 skipped** (零回归)

## 💡 关键发现 / 决策

1. "自环"不是单一概念: internal 标记 (端口级, 恒 src==dst, 非源) vs
   nonblocking 真自环 (操作数含自身, 是源)。按 assign_type 区分是精确边界,
   一刀切排除会破坏 `state<=state+1` 语义 (test_subroutine_params 依赖)。
2. 修复在**查询层**而非图构造层: internal 自环边对 out_edges/可视化仍有
   "此端口有内部驱动" 标记价值; 只是 fanin 语义不该把它当源。
3. depth=1 (`_find_drivers`) 与递归 (`_trace_drivers_recursive`) 是两条独立
   路径, 都需同规则, 否则 depth 参数行为不一致 (本次一并修)。

## 📌 状态

- ✅ A3 修复 + unit 4; 全量回归 2913 passed / 0 failed
- 审计清单 A1/A2/A3 全修; 待验证候选 (inout/struct/interface/时钟域) 仍开放
- A2 位对位折算 (总线粒度 → 位粒度) 仍在 backlog
