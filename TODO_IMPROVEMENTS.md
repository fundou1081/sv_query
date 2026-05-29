# 改进计划进度总结 (2026-05-25)

## ✅ 已完成

| 任务 | 状态 | 说明 |
|------|------|------|
| P0-1 | ✅ 完成 | Condition 提取 |
| P0-2 | ✅ 完成 | Driver Expression 提取（修复 Concatenation 问题） |
| P1-3 | ✅ 部分 | 源码位置（SemanticAdapter 限制） |
| P1-4 | ✅ 完成 | Clock/Reset Domain 追溯 |
| P1-5 | ✅ 完成 | Loads 追溯 |
| P2-6 | ✅ 完成 | Width 格式优化（保持现状） |

---

## 📋 发现的问题 (TODO)

### P3-1: Part-Select 驱动边
**状态**: ✅ 设计决策（位精确性）

**说明**:
- 拼接表达式 `{rx, sreg_q[10:1]}` 拆成多个驱动边是正确的
- 每个 part-select 描述对不同 bit 的驱动（位精确性）
- `sreg_q[10:1] -> sreg_d` 是有效驱动，描述 bits[10:1] 的驱动
- `rx -> sreg_d` 是主驱动，描述 bit[0] 的驱动

**结论**: 不是 bug，是位精确性设计优先的体现

---

### P3-2: 字面量作为驱动边
**状态**: ✅ 设计决策（值驱动建模）

**说明**:
- 字面量 `4'b0`, `1'b1`, `11'd0` 作为驱动边是正确的
- 字面量描述"驱动值"，condition 描述"何时驱动"
- `11'd0 -> sreg_q (condition: !rst_ni)` 描述"复位时 reg 被赋值为 0"

- `1'b1 -> idle_q (condition: !rx_enable)` 描述"失能时 idle 被赋值为 1"


**结论**: 不是 bug，是值驱动建模设计的体现

---

### P3-3: 添加时钟/复位上下文
**状态**: ✅ 已修复 (2026-05-25)

**问题**: 
- `sreg_d` 的 `clock_domain` 为空，无法区分时序/组合逻辑
- `trace_detailed()` 返回的 DriverInfo 缺少时钟/复位信息

**修复方案**:
- 添加 `_infer_clock_reset_for_drivers()` 方法
- 通过后继节点的 CLOCK/RESET 边反推时钟域信息
- 在 `trace_fanin_detailed()` 调用后自动补全缺失的 clock_domain

**修复后输出**:
```
[1] uart_rx.rx
    clock: clk_i      ✅ 已补全
    reset: !rst_ni    ✅ 已补全
```

**优先级**: P3-3 (中) - ✅ 完成

---

### P3-4: Width 格式优化
**问题**: 
- 当前 `width: "(1, 0)"` 不直观
- 人类阅读困难

**当前**: `width: (7, 0)` → **期望**: `width: "[7:0]"` 或 `"8bit"`

**方案**:
- 添加格式化方法
- 支持多种格式输出

**优先级**: P3-4 (低) - 已决定保持现状

---

### P3-5: 边信息缺失
**状态**: ✅ 已修复 (2026-05-25)


**问题**:
- DriverInfo 缺少边的 expression 信息
- `trace_detailed()` 返回的 DriverInfo 没有边的 expression

**修复方案**:
- 添加 `full_statement` property 方法
- 自动组装完整的驱动语句: `if (cond) LHS assign_op RHS; // @clock`

**修复后输出**:
```
[1] if (!!rx_enable && ...) uart_rx.rx <= {rx, sreg_q[10:1]}; // @clk_i
[2] if (!!rx_enable) uart_rx.sreg_q <= sreg_q; // @clk_i
[3] if (!rx_enable) 11'd0 <= 11'd0; // @clk_i
```

**优先级**: P3-5 (中) - ✅ 完成

---

### P3-6: 组装完整驱动语句
**状态**: ✅ 已修复 (2026-05-25)

**问题**:
- DriverInfo 只保存字段，不包含完整语句
- debug 时需要手动组装

**修复方案**:
- 添加 `full_statement` property 到 DriverInfo
- 自动组装: `if (cond) dst assign_op expression; // @clock`

**修复后输出**:
```
[1] if (!!rx_enable && !idle_q && ...) uart_rx.rx <= {rx, sreg_q[10:1]}; // @clk_i
[2] if (!!rx_enable) uart_rx.sreg_q <= sreg_q; // @clk_i
```

**优先级**: P3-6 (中) - ✅ 完成

---

## 📊 测试状态

- 996 passed, 1 skipped ✅

## 📁 相关文件

- 测试用例: `~/my_dv_proj/opentitan/hw/ip/uart/rtl/uart_rx.sv`
- 核心模块: `~/my_dv_proj/sv_query/src/trace/`