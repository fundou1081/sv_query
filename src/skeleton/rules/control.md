# Control Signal Rule

> 版本: 1.0
> 日期: 2026-05-30

---

## 规则元数据

```yaml
name: control_signal
type: sva_control
description: |
  控制信号断言模板
  适用于 mode, enable, stall 等控制信号
priority: 3
```

---

## 触发条件

```yaml
trigger:
  conditions:
    - signal_type: control
      description: 控制信号类型
    - signal_pattern: [mode, enable, stall, valid, ready]
      description: 控制信号特征
    - fanout: >= 2
      description: 高扇出控制信号
  examples:
    - mode
    - enable
    - stall_req
    - pipeline_stall
```

---

## 断言规则

### 规则 1: 控制信号有效性

```systemverilog
// 规则 1: 控制信号在有效期间应保持稳定
// 适用场景: mode、enable 等信号在操作期间不应变化
property control_signal_stable;
    @(posedge clk) disable iff (!rst_n)
    $changed(mode) && $past(mode) != '0 |-> mode throughout ($past(mode)[->1]);
endproperty
// 注意: 此规则假设 mode 在操作期间应保持不变
```

### 规则 2: 控制信号状态机

```systemverilog
// 规则 2: 控制信号应遵循状态机规则
// 适用场景: mode 等信号有明确定义的状态转换
// TODO: 根据实际状态机定义填充状态转换规则
property mode_state_transition;
    @(posedge clk) disable iff (!rst_n)
    // 示例: idle -> run -> done -> idle
    mode == 2'b00 |-> ##1 mode inside {2'b00, 2'b01};  // idle 可保持或转到 run
    mode == 2'b01 |-> ##1 mode inside {2'b01, 2'b10};  // run 可保持或转到 done
    mode == 2'b10 |-> ##1 mode == 2'b00;              // done 必须回到 idle
endproperty
```

### 规则 3: 控制信号使能条件

```systemverilog
// 规则 3: 使能信号在特定条件下应有效
// 适用场景: enable、valid 等信号在特定条件下应拉高
// TODO: 根据实际协议填充使能条件
property enable_condition;
    @(posedge clk) disable iff (!rst_n)
    // 示例: enable 在 not_stall 时应有效
    !stall |-> enable;
endproperty
```

---

## 模板代码

```systemverilog
// sva_control_{id}.sv
// ============================================================
// 控制信号断言骨架
// 目标: 验证控制信号的正确性
// 生成日期: {date}
// 信号: {signal_name}
// 风险: {risk_level}
// ============================================================

`timescale 1ns/1ps

module sva_control_{id};
    // ------------------------------------------------------------
    // 控制信号
    // ------------------------------------------------------------
    // TODO: 替换为实际信号
    // input logic clk;
    // input logic rst_n;
    // input logic [{width}-1:0] {signal_name};
{other_signals}

    // ------------------------------------------------------------
    // 断言规则
    // ------------------------------------------------------------
    // 规则 1: 信号稳定性（在有效期间）
    // TODO: 确认信号是否应在操作期间保持稳定
    property signal_stable;
        @(posedge clk) disable iff (!rst_n)
        {signal_name} && !($past({signal_name}) == '{default_value})
        |-> {signal_name} throughout ($past({signal_name})[->1]);
    endproperty

    // 规则 2: 使能条件
    // TODO: 根据实际协议填充条件
    property enable_when_ready;
        @(posedge clk) disable iff (!rst_n)
        {condition} |-> {signal_name};
    endproperty

    // ------------------------------------------------------------
    // 断言实例化（默认禁用）
    // ------------------------------------------------------------
    // a_signal_stable: assert property (signal_stable);
    // a_enable: assert property (enable_when_ready);

endmodule
```

---

## 填充说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `{id}` | 唯一标识符 | `0`, `ctrl_0` |
| `{date}` | 生成日期 | `2026-05-30` |
| `{signal_name}` | 控制信号名 | `mode`, `enable` |
| `{risk_level}` | 风险等级 | `HIGH`, `MEDIUM` |
| `{width}` | 信号位宽 | `2` (mode[1:0]) |
| `{default_value}` | 默认值 | `0` |
| `{condition}` | 使能条件 | `!stall` |

---

## 风险阈值

| 风险等级 | 条件 | 说明 |
|----------|------|------|
| HIGH | fanout >= 5 | 高扇出控制信号 |
| MEDIUM | fanout >= 2 | 一般控制信号 |
| LOW | 其他 | 低扇出 |

---

## Review 检查清单

```
工程师 Review 时检查：
1. [ ] 信号名称是否与实际一致
2. [ ] 稳定性规则是否适用（某些信号允许随时变化）
3. [ ] 使能条件是否正确
4. [ ] 状态转换规则是否符合设计
```

---

## 相关规则

- `pipeline.md` - 流水线（带 stall 控制的流水线）
- `handshake.md` - 握手协议（带 valid-ready 的流控）

---

*等待补充更多控制信号规则...*