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

### P3-1: 过滤 Part-Select 重复边
**问题**: 
- 拼接表达式 `{rx, sreg_q[10:1]}` 被拆成两个驱动源
- `sreg_q[10:1] -> sreg_d` 不应该作为独立驱动源
- `rx -> sreg_d` 和 `sreg_q[10:1] -> sreg_d` 条件完全相同，造成重复

**影响**: 
- 输出冗余，用户难以快速理解
- AI 分析时产生误导

**方案**:
- 在 DriverInfo 输出前过滤 part-select 驱动
- 或者合并相同条件的多条边

**优先级**: P3-1 (高)

---

### P3-2: 字面量不应与信号混在一起
**问题**: 
- `4'b0`, `1'b1` 等字面量被列为驱动源
- 字面量是赋值，不是驱动源

**当前输出**:
```
[5] 驱动源: 4'b0
[10] 驱动源: 1'b1
```

**方案**:
- 分离字面量和信号驱动源
- 添加 `is_literal` 标记

**优先级**: P3-2 (中)

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