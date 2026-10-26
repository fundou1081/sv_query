# Iteration 293: F4 bus↔bus 位桥（缺位侧合成）（PLAN P5.5）

**Metadata**:
- **Iteration #**: 293
- **Task Tree Level**: L2（[L1_bit_precision](../tasks/L1_bit_precision.md) / PLAN `P5.5`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "要f4"）
- **Outcome**: ✅ 完成（两种模式 `one` 默认 / `full` 可选；2416 passed）

## 🎯 决策

iter_126 曾定"纯总线直连不造假节点"（保持总线粒度）。F4 与它冲突，
方豆拍板"要 f4" → 允许为位桥**合成**位节点。

落地方案：**默认保守、可选激进**

| 模式 | 环境变量 | 行为 | verilog-axi 图规模 |
|---|---|---|---|
| `one`（默认） | `SVQ_BIT_BRIDGE=one` | 只给"一侧已有位节点"的连接补另一侧 | 14,182 节点 / 29,760 边（+381） |
| `full` | `SVQ_BIT_BRIDGE=full` | 纯总线连接也两侧合成（`i ↔ i`） | 31,510 节点 / 39,108 边（+17,709） |

默认选 `one` 的理由：`full` 让图变成 2.2×（gzip 0.4→0.7MB，构建时间不变），
在 CVA6/OpenTitan 这类大工程上会撞 `MAX_NEW_NODES=30000` 上限并产生**部分展开**；
`one` 已能覆盖"一侧有位逻辑"的绝大多数真实调试场景。

## 🔧 实现：`_synthesize_missing_bit_bridges`（新 pipeline stage）

位置：`bus_bit_bridges` 之后（`bit_nodes` → … → `bus_bit_bridges` → `bit_bridge_synth`）。

| 规则 | 说明 |
|---|---|
| CONNECTION（端口/网络） | 同索引 `i ↔ i` 建位边（网络连接恒成立）；`one` 补缺位侧，`full` 两侧合成 |
| DRIVER（总线赋值） | **仅直接拷贝**（`assign y = a`，所有 DRIVER 边 `expression == 源短名`）；算术/逻辑表达式跳过（`a+b` 有进位，不同索引） |
| 多驱动保护 | 目标已有位级驱动时不做总线拷贝展开（避免与已有位驱动混淆） |
| 聚合边 | 合成位节点**不加 BIT_SELECT**（防父总线提升污染） |
| 稳定性 | 最多 3 轮迭代到不动点（合成会让"另一侧有位"的 pair 变为可处理，消除边的遍历顺序依赖） |
| 上限 | 新节点 30000，超限显式 warning 停止 |

## 📊 效果（fixture）

```
纯总线 passthrough（full）:
  fanin(y[3]) = {u.a[3], a[3]}          （以前: {u.y}）
  fanout(a[3]) = {u.a[3], u.y[3], y[3]} （以前: {u.a, u.y, y}）

子模块有位逻辑（one，默认）:
  fanin(w[3]) = {u.a[3], a[3]}          （以前: {u.y}）
```

## 🧪 测试（`test_bit_bridge_f4.py`，8 个）

| 组 | 覆盖 |
|---|---|
| `one` 默认 | 一侧有位 → 补齐贯通；纯总线仍粗粒度（iter_126 契约） |
| `full` | 纯总线位精确（fanin+fanout）；直接拷贝 `assign y=a` 位精确 |
| 安全 | 算术表达式 `a+b` 即使 full 也不展开；合成位无 BIT_SELECT 聚合边 |
| 模式 | 非法 env 回落 `one`；显式 `one` 可复现默认 |

图基线：`scheduler_minimal` 因 `one` 模式新增位节点**有意重生成**
（73→88 节点 / 228→236 边），迭代记录注明原因。

## ✅ 验证

| 项 | 结果 |
|---|---|
| 全量门禁 | 2408 → **2416 passed / 0 failed**（+8） |
| 图基线 | conf 5 个不变；scheduler 有意更新 |
| 构建时间 | 24.5s（one）/ 24.8s（full）—— elaboration 主导，位桥不是瓶颈 |

## 📌 剩余（KNOWN_LIMITATIONS §3.6）

- 表达式驱动的位映射（`s=a+b` 的逐位依赖）：需要驱动侧按位展开运算语义
- 常量源切片值位映射 / 动态 part-select
- `full` 模式在超大设计上可能撞上限（30000）→ 部分展开；默认 `one` 规避

## 🔗 相关

- 计划: [PLAN.md P5.5](../../../PLAN.md)
- 前序: [iter_289](iter_289_bit_precision_audit.md) / [iter_290](iter_290_bit_precision_fix.md) / [iter_291](iter_291_slice_bit_expansion.md) / [iter_292](iter_292_load_side_bit_precision.md)
- 历史契约: `docs/architecture/signal_graph_accuracy_audit.md` A2（iter_126/137/143）
