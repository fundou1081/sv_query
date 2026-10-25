# Iteration 292: F5 load 方向按位（PLAN P5.6）

**Metadata**:
- **Iteration #**: 292
- **Task Tree Level**: L2（[L1_bit_precision](../tasks/L1_bit_precision.md) / PLAN `P5.6`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续5.6"）
- **Outcome**: ✅ 完成（load 方向位精度与 fanin 对称；+6 测试；2408 passed）

## 🎯 背景

F3（iter_291）把切片赋值展开成逐位节点后，**load 方向也顺带精确了**：

```
y[7:4] = a;   fanout(a[1]) = {y[5]}   （以前: {y[7:4]}）
y = a[7:4];   fanout(a[6]) = {y[2]}
q[3] <= d[1]; fanout(d[1]) = {q[3]}
```

但还剩一个 **false-empty**：位节点存在、却没有位级负载（负载挂在父总线上）时，
`fanout(bit)` 返回空集，而 `fanout(总线)` 有答案 —— 与 fanin 的 F2 不对称。

## 🔧 改动：`_load_bus_fallback`

`trace_fanout` 入口（缺位回退之后）：

```
位节点存在
  + 没有任何 DRIVER/CONNECTION 出边（不含自环）
  + 父总线存在且有负载
  → 用父总线的负载回答（总线粒度）
```

与 fanin 的 F2 规则完全对称；有负载时保持位精度，不回退（不引入噪声）。

## 📊 效果

| 查询 | 修复前 | 修复后 |
|---|---|---|
| `fanout(a[1])`（`y[7:4]=a`） | `{y[7:4]}`（F3 前）/ `{y[5]}`（F3 后） | `{y[5]}` ✅ |
| `fanout(a[6])`（`y=a[7:4]`） | `{a[7:4]}` 总线 | `{y[2]}` ✅ |
| `fanout(d[1])`（`q[3]<=d[1]`） | `{q}` 总线 | `{q[3]}` ✅ |
| `fanout(w[4])`（位节点无负载） | `{}` | `{z}`（父总线负载） ✅ |
| `fanout(a[3])`（`s=a&b`） | `{s}` | `{s}`（表达式仍粗，已文档） |

## 🧪 测试（`test_bit_precision.py` 25 → 31）

| 用例 | 断言 |
|---|---|
| LHS 切片 fanout | `fanout(a[1]) == {y[5]}` |
| RHS 切片 fanout | `fanout(a[6]) == {y[2]}` |
| 寄存器位 fanout | `fanout(d[1]) == {q[3]}` |
| 相邻位不串 | `a[1]` 不含 `y[4]/y[6]/y[7]` |
| 无负载位回退 | `fanout(w[4]) == {z}` |
| 表达式粗粒度 | `fanout(a[3]) == {s}`（契约） |

## 📊 量化

| 指标 | 值 |
|---|---|
| 全量门禁 | 2402 → **2408 passed / 0 failed**（+6） |
| 图结构 | **无变化**（纯查询层改动） |
| 真实项目 | 见 INDEX 基线；verilog-axi 冒烟正常 |

## 📌 剩余（已登记 KNOWN_LIMITATIONS §3.6）

- F4 合成位桥（bus↔无位节点侧）：需方豆拍板（与 iter_126「不造假节点」冲突）
- 表达式驱动的位映射：需驱动侧按位展开运算语义（成本高）
- 常量源切片值位映射 / 动态 part-select 展开

## 🔗 相关

- 计划: [PLAN.md P5.6](../../../PLAN.md)
- 前序: [iter_289 审计](iter_289_bit_precision_audit.md) / [iter_290 F1+F2](iter_290_bit_precision_fix.md) / [iter_291 F3](iter_291_slice_bit_expansion.md)
