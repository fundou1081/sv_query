# Handshake Protocol Rule

> 版本: 1.0
> 日期: 2026-05-30

---

## 规则元数据

```yaml
name: handshake_protocol
type: sva_handshake
description: |
  Valid-Ready 握手协议断言模板
  适用于 din_valid → din_ready 或类似握手信号对
priority: 1
```

---

## 触发条件

```yaml
trigger:
  conditions:
    - path_type: handshake
      description: 握手协议特征
    - signal_pattern: [valid, ready]
      description: 同时包含 valid 和 ready 信号
    - path_length: 1-2
      description: 路径较短，通常是直接连接
  examples:
    - din_valid → din_ready
    - wr_valid → wr_ready
    - req → ack
```

---

## 断言规则

### 规则 1: 握手有效条件

```systemverilog
// 规则 1: valid 和 ready 同时为高时，握手成功
// 适用场景: 标准 valid-ready 协议
property handshake_success;
    @(posedge clk) disable iff (!rst_n)
    valid && ready |-> ##1 ready throughout (valid[->1]);
endproperty
// 说明: valid 和 ready 同时为高的下一个周期起，ready 保持高直到 valid 撤消
```

### 规则 2: valid 稳定期间不能撤消（除非 ready）

```systemverilog
// 规则 2: valid 在 ready 为低时不能撤消
// 适用场景: AXI 风格的 no-drop-when-not-ready 协议
// 注意: 如果设计允许 valid 撤消，删除此规则
property valid_no_drop_without_ready;
    @(posedge clk) disable iff (!rst_n)
    valid && !ready |-> valid until_with ready;
endproperty
```

### 规则 3: ready 可随时撤消

```systemverilog
// 规则 3: ready 可以在任何时刻撤消
// 说明: 此规则通常不需要断言，仅作设计说明
// 如果需要验证 ready 撤消后的行为，添加此规则
property ready_can_drop;
    @(posedge clk) disable iff (!rst_n)
    ready ##1 !ready |-> !valid until_with (valid && ready);
endproperty
```

---

## 模板代码

```systemverilog
// sva_handshake_protocol.sv
// ============================================================
// 握手协议断言骨架
// 目标: 验证 valid-ready 握手机制的正确性
// 生成日期: {date}
// 路径: {path}
// 风险: {risk_level}
// ============================================================

`timescale 1ns/1ps

module sva_handshake_protocol_{id};
    // ------------------------------------------------------------
    // 接口定义
    // ------------------------------------------------------------
    // TODO: 替换为实际信号
    // input logic clk;
    // input logic rst_n;
    // input logic {valid_signal};
    // input logic {ready_signal};

    // ------------------------------------------------------------
    // 断言规则
    // ------------------------------------------------------------
    // 规则 1: 握手成功条件
    // TODO: 确认协议是否符合此规则
    property handshake_success;
        @(posedge clk) disable iff (!rst_n)
        {valid_signal} && {ready_signal} |-> ##1 {ready_signal} throughout ({valid_signal}[->1]);
    endproperty

    // 规则 2: valid 不在 ready 低时撤消
    // TODO: 如果协议允许 valid 撤消，删除此规则
    property valid_no_drop_without_ready;
        @(posedge clk) disable iff (!rst_n)
        {valid_signal} && !{ready_signal} |-> {valid_signal} until_with {ready_signal};
    endproperty

    // ------------------------------------------------------------
    // 断言实例化（默认禁用，工程师确认后启用）
    // ------------------------------------------------------------
    // a_handshake_success: assert property (handshake_success);
    // a_valid_no_drop: assert property (valid_no_drop_without_ready);

endmodule
```

---

## 填充说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `{valid_signal}` | valid 信号名 | `din_valid` |
| `{ready_signal}` | ready 信号名 | `din_ready` |
| `{id}` | 唯一标识符 | `0`, `1`, `2` |
| `{date}` | 生成日期 | `2026-05-30` |
| `{path}` | 路径描述 | `din_valid → din_ready` |
| `{risk_level}` | 风险等级 | `HIGH`, `MEDIUM` |

---

## 风险阈值

| 风险等级 | 条件 | 说明 |
|----------|------|------|
| HIGH | fanout >= 3 | 高扇出握手信号 |
| MEDIUM | fanout >= 1 | 一般握手信号 |
| LOW | 其他 | 低风险 |

---

## Review 检查清单

```
工程师 Review 时检查：
1. [ ] 信号名称是否与实际一致
2. [ ] 协议规则是否符合设计规范
3. [ ] 是否需要删除/修改某些规则
4. [ ] TODO 部分是否需要填充
5. [ ] 断言实例化是否需要启用
```

---

## 相关规则

- `pipeline.md` - 数据路径规则（当握手后有数据传递时）
- `cdc.md` - CDC 规则（跨时钟域握手时）

---

*等待补充更多握手协议规则...*