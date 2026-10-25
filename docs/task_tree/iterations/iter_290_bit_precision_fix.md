# Iteration 290: 位级精度修复 F1 + F2（PLAN P5.1 / P5.2 / P5.3）

**Metadata**:
- **Iteration #**: 290
- **Task Tree Level**: L2（[L1_bit_precision](../tasks/L1_bit_precision.md) / PLAN `P5`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "构建针对性计划，开始修复，记得把测试也加强"）
- **Outcome**: ✅ 3 类反例全部消除；+19 个回归；2396 passed

## 🎯 目标

按 iter_289 审计的 3 类反例修**正确性**（不是粒度）：
- F1：缺位回退 `X[n]` 时，父总线的切片必须按位过滤
- F2：位节点无 incoming 驱动（死胡同）时，补父总线的真实驱动
- 测试：逐位对应 + 负向（不得跨位/不得断链）固化

## 🔧 F1：缺位回退按位过滤

`SignalTracer`：

| 改动 | 说明 |
|---|---|
| `_trace_drivers_recursive(..., bit_filter=None)` | 新增内部参数，只在"回退到父总线"这一跳传递 |
| `_trace_missing_node` | `X[n]` 缺位 → 回退父总线时带 `bit_filter=n`（不再丢位索引） |
| `_expand_incoming_bit_select(..., bit_filter)` | 父总线的 BIT_SELECT 子节点只追覆盖该位的切片 |
| 主循环 | `BIT_SELECT` 入边同样按位过滤（防 `_pick_driver_edge` 路径绕过） |
| `_bit_index_of` / `_bit_in_range` | 位索引解析（id 解析 + `parent_bit_start/end` 优先） |

效果：

```
assign y[7:4]=a; assign y[3:0]=4'h0;
  fanin(y[5]): {a, 4'b0} → {a}
  fanin(y[2]): {a, 4'b0} → {4'b0}
assign y=a; assign y[3]=1'b1;
  fanin(y[4]): {a, 1'b1} → {a}
```

顺带修正一条**旧测试的错误期望**：切片外悬空位 `top.y[3]` 过去断言
`{top.u_sub.y}`（总线回退）——u_sub.y 只驱动 `y[7:4]`，算到 bit3 上正是跨位污染；
现在正确为**空集**（该位未被赋值）。

## 🔧 F2：位节点死胡同补父总线

`_maybe_lift_to_parent_bus` 旧门槛"drivers 非空就 return"挡住了死胡同位节点
（它作为别人的驱动项被 append，但自己没有任何 incoming）。新规则：

```
位节点（能解析出 bit 索引）
  + 父总线存在 **且父总线有 incoming**
  → 带位索引补追父总线（总线粒度）
父总线无 incoming（顶层输入位）→ 不提升（保持原行为，避免噪声）
```

效果：

```
assign s=a&b; assign y=s[3];   fanin(y): {s[3]} → {s[3], a, b}
assign z=w[3]; (w 由子模块驱动) fanin(z): {w[3]} → {w[3], u.y}
```

## 🧪 测试加强（19 个，`test_bit_precision.py`）

| 组 | 数量 | 内容 |
|---|---|---|
| A 精确 | 6 | bit 对 bit / 寄存器位 / struct 成员位 / 位链 / 跨模块有位逻辑 / generate entry 隔离 |
| B 防污染（F1） | 5 | 切片内外位、多驱动、重叠切片、悬空位 |
| C 防断链（F2） | 4 | 表达式取位、三目取位、子模块线网取位、顶层输入位不提升 |
| D 粗粒度契约 | 4 | 拼接、纯总线连接、load 方向总线粒度、总线查询仍聚合 |

每条断言都是**精确集合**或**负向包含**，不再用 `len>=1`。

## 📊 量化

| 指标 | 值 |
|---|---|
| 全量门禁 | 2377 → **2396 passed / 0 failed**（+19） |
| 图基线 | 6 fixture 零差异（只改查询层，图结构未动） |
| 真实项目 | verilog-axi `drivers/loads` 正常（24.4s / 0.6s 缓存命中） |

## 📌 未做（明确记录）

| 项 | 原因 |
|---|---|
| F3 slice 按位展开 | 精度升级，需评估大设计图规模；当前 F1 保证"不假" |
| F4 合成位桥 | 与 iter_126「不造假节点」冲突，需方豆拍板 |
| load 方向位精度 | 表达式驱动只有总线级边，需驱动侧补逐位边（成本高） |

## 🔗 相关

- 审计: [iter_289](iter_289_bit_precision_audit.md)
- 计划: [PLAN.md P5](../../../PLAN.md)
- 限制登记: [KNOWN_LIMITATIONS §3.6](../../KNOWN_LIMITATIONS.md)
