# Pipeline Data Path Rule

> 版本: 1.0
> 日期: 2026-05-30

---

## 规则元数据

```yaml
name: pipeline_data_path
type: sva_pipeline
description: |
  数据路径流水线断言模板
  适用于 stage1_data → stage2_data → result 等多级流水线
priority: 2
```

---

## 触发条件

```yaml
trigger:
  conditions:
    - path_type: pipeline
      description: 流水线数据传递特征
    - path_length: >= 2
      description: 路径深度 >= 2 级寄存器
    - signal_pattern: [data, stage]
      description: 包含 data 或 stage 前缀的信号
  examples:
    - stage1_data → stage2_data → result
    - pipe_s1 → pipe_s2 → pipe_s3 → out
    - din → s1 → s2 → s3 → dout
```

---

## 断言规则

### 规则 1: 数据传递（无延迟）

```systemverilog
// 规则 1: 数据从 stage1 传递到 stage2（1 周期后）
// 适用场景: 标准流水线，每级 1 周期
property data_transfer_1cycle;
    @(posedge clk) disable iff (!rst_n)
    stage1_valid && stage1_data == $past(stage1_data)
    |=> stage2_valid && stage2_data == $past(stage1_data);
endproperty
```

### 规则 2: 数据传递（多周期延迟）

```systemverilog
// 规则 2: 数据从 stage1 传递到 stage3（2 周期后）
// 适用场景: 带组合逻辑的流水线，可能有额外延迟
// TODO: 确认延迟周期数
property data_transfer_2cycle;
    @(posedge clk) disable iff (!rst_n)
    stage1_valid
    |=> ##2 stage3_valid && stage3_data == $past(stage1_data);
endproperty
```

### 规则 3: 无气泡传递

```systemverilog
// 规则 3: 连续 valid 时，中间不应出现气泡
// 适用场景: 流水线不允许中间停顿
// 注意: 如果设计允许气泡，删除此规则
property no_bubble_continuous;
    @(posedge clk) disable iff (!rst_n)
    stage1_valid && stage2_valid && result
    |=> stage1_valid throughout (stage2_valid && result);
endproperty
```

### 规则 4: 数据不突变

```systemverilog
// 规则 4: 流水线数据在传递过程中不应发生未预期的变化
// 适用场景: 验证数据在流水级之间保持稳定
property data_stable_in_pipeline;
    @(posedge clk) disable iff (!rst_n)
    stage1_valid && stage2_valid
    |-> stage2_data == $past(stage1_data);
endproperty
```

---

## 模板代码

```systemverilog
// sva_pipeline_{id}.sv
// ============================================================
// 数据路径流水线断言骨架
// 目标: 验证流水线数据传递的正确性
// 生成日期: {date}
// 路径: {path}
// 深度: {depth} 级
// 风险: {risk_level}
// ============================================================

`timescale 1ns/1ps

module sva_pipeline_{id};
    // ------------------------------------------------------------
    // 流水线信号
    // ------------------------------------------------------------
    // TODO: 替换为实际信号
    // input logic clk;
    // input logic rst_n;
{interface_definitions}

    // ------------------------------------------------------------
    // 断言规则
    // ------------------------------------------------------------
    // 规则 1: 数据传递（1 周期延迟）
    // TODO: 确认延迟周期数
    property pipeline_data_transfer;
        @(posedge clk) disable iff (!rst_n)
        {stage1_valid} && {stage1_data}
        |=> {stage2_valid} && {stage2_data} == $past({stage1_data});
    endproperty

    // 规则 2: 无气泡传递
    // TODO: 如果设计允许气泡，删除此规则
    property no_bubble;
        @(posedge clk) disable iff (!rst_n)
        {stage1_valid} && {stage2_valid}
        |=> {stage1_valid} throughout {stage2_valid};
    endproperty

    // ------------------------------------------------------------
    // 断言实例化（默认禁用）
    // ------------------------------------------------------------
    // a_pipeline_transfer: assert property (pipeline_data_transfer);
    // a_no_bubble: assert property (no_bubble);

endmodule
```

---

## 填充说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `{id}` | 唯一标识符 | `0`, `1`, `pipeline_0` |
| `{date}` | 生成日期 | `2026-05-30` |
| `{path}` | 完整路径 | `din → s1 → s2 → s3 → dout` |
| `{depth}` | 流水线深度 | `3` |
| `{risk_level}` | 风险等级 | `CRITICAL`, `HIGH` |
| `{stage1_valid}` | 第1级有效信号 | `stage1_valid` |
| `{stage1_data}` | 第1级数据信号 | `stage1_data` |
| `{stage2_valid}` | 第2级有效信号 | `stage2_valid` |
| `{stage2_data}` | 第2级数据信号 | `stage2_data` |

---

## 风险阈值

| 风险等级 | 条件 | 说明 |
|----------|------|------|
| CRITICAL | depth >= 5 | 超深流水线（5+ 级） |
| HIGH | depth >= 3 | 深流水线（3-4 级） |
| MEDIUM | depth >= 2 | 一般流水线（2 级） |
| LOW | 其他 | 短流水线 |

---

## Review 检查清单

```
工程师 Review 时检查：
1. [ ] 信号名称是否与实际一致
2. [ ] 延迟周期数（|=> 后面）是否符合设计
3. [ ] 是否需要添加/删除某些规则
4. [ ] 气泡规则是否允许
5. [ ] 是否有遗漏的边界条件（如 reset、stall）
```

---

## 相关规则

- `handshake.md` - 握手协议（带流控的流水线）
- `cdc.md` - CDC 规则（跨时钟域流水线）

---

*等待补充更多流水线规则...*