# Iteration 289: 位级 drive/load 精度审计（反例排查）

**Metadata**:
- **Iteration #**: 289
- **Task Tree Level**: L1（审计；无代码改动）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "能做到精确位级别 drive load 映射吗？测试充分吗？试着找针对性反例。"）
- **Outcome**: ⚠️ 部分精确；找到 3 类反例 + 测试缺口；已登记 KNOWN_LIMITATIONS §3.6

## 方法

15 个最小 fixture，逐一跑 `fanin/fanout`，与"按位预期"比对：
同模块位赋值 / 寄存器位 / struct 成员位 / generate per-entry / 跨模块（子模块有位逻辑 vs
纯总线）/ 拼接 / 切片 / 偏移 / 多驱动 / 动态索引 / 表达式取位。

## 结论

- ✅ **局部精确**：显式位赋值、寄存器位、struct 成员位、generate per-entry、
  两侧都有位节点的跨模块连接（与 iter_137/143 既有测试一致）。
- ❌ **普遍不精确**：纯总线直连、拼接、切片、动态索引 → 总线/切片粒度（既定契约）。
- ⚠️ **3 类反例**（答案含不成立源 / 断链，不只是"粗"）：

| # | RTL | 实际 | 问题 |
|---|---|---|---|
| 1 | `assign y[7:4]=a; assign y[3:0]=4'h0;` | `fanin(y[5])={a, 4'b0}` | 4'b0 与 bit5 无关 |
| 2 | `assign y=a; assign y[3]=1'b1;` | `fanin(y[4])={a, 1'b1}` | 1'b1 只驱动 bit3 |
| 3 | `assign s=a&b; assign y=s[3];` | `fanin(y)={s[3]}` | 缺 a/b（位节点死胡同） |

## 测试充分性

位相关 27 个测试，但多为"节点/边存在 / `>=1`"断言；A2 测试明确接受总线粒度；
**无**逐位对应/无跨位污染的断言 → 不足以支撑"位精确"表述。

## 根因

1. 缺位回退不带位索引 → slice 节点聚合无法按位过滤（`_trace_missing_node`）
2. 位节点死胡同：提升条件 `not drivers` 挡住（`_maybe_lift_to_parent_bus`）
3. 位桥只在两侧都有位节点时建（`_expand_bus_conn_bit_bridges`）

## 建议

F1 位索引过滤（正确性）→ F2 死胡同补父总线（完整性）→ F3 slice 按位展开（精度）→
F4 合成位桥（需方豆拍板，涉及"不造假节点"旧决策）。

## 交付

- 无代码改动（审计）
- `docs/KNOWN_LIMITATIONS.md` §3.6 登记（含反例与根因）
