# CDC Cross Clock Domain Rule

> 版本: 1.0
> 日期: 2026-05-30

---

## 规则元数据

```yaml
name: cdc_path
type: sva_cdc
description: |
  跨时钟域路径断言模板
  适用于 clk_a → clk_b 的 CDC 路径
priority: 1
```

---

## 触发条件

```yaml
trigger:
  conditions:
    - path_type: cdc
      description: 跨时钟域特征
    - clock_domain: different
      description: 源时钟域 ≠ 目标时钟域
    - sync_type: [NONE, 2-FLOP, 3-FLOP]
      description: 同步器类型
  examples:
    - data_a (clk_a) → data_sync (clk_b)
    - req (clk_a) → req_sync (clk_b)
```

---

## 断言规则

### 规则 1: CDC 数据稳定性（2-FLOP 同步器）

```systemverilog
// 规则 1: 目标域数据在稳定后不再变化
// 适用场景: 2-FLOP 同步器（标准 CDC 保护）
// 注意: 假设 2 周期延迟
property cdc_data_stable_2flop;
    @(posedge clk_b) disable iff (!rst_n)
    $changed(data_in) |=> ##2 data_sync == $past(data_in, 2);
endproperty
```

### 规则 2: CDC 数据稳定性（3-FLOP 同步器）

```systemverilog
// 规则 2: 目标域数据在稳定后不再变化
// 适用场景: 3-FLOP 同步器（更高安全性）
// 注意: 假设 3 周期延迟
property cdc_data_stable_3flop;
    @(posedge clk_b) disable iff (!rst_n)
    $changed(data_in) |=> ##3 data_sync == $past(data_in, 3);
endproperty
```

### 规则 3: CDC 初始值

```systemverilog
// 规则 3: 上电后数据有确定的初始值
// 适用场景: 需要已知初始状态的 CDC 路径
property cdc_initial_value;
    @(posedge clk_b) disable iff (!rst_n)
    $rose rst_n |-> ##5 data_sync != 'x;  // 5 周期后数据有效
endproperty
// 注意: 如果对初始值无要求，删除此规则
```

### 规则 4: CDC 无亚稳态（无同步器 - 高风险）

```systemverilog
// 规则 4: CDC 路径必须经过同步器
// 适用场景: 检测高风险 CDC 路径（无同步器）
// 警告: 此规则标识高风险路径，需要工程师评估
property cdc_no_metastability;
    @(posedge clk_b) disable iff (!rst_n)
    $changed(data_in) |-> ##1 data_sync == $past(data_in);
endproperty
// 注意: 此断言假设无同步器保护，只有 1 周期延迟
// 警告: 高风险！建议添加同步器
```

---

## 模板代码

```systemverilog
// sva_cdc_{id}.sv
// ============================================================
// CDC 路径断言骨架
// 目标: 验证跨时钟域数据传递的正确性
// 生成日期: {date}
// 路径: {path}
// 源时钟: {src_clk}
// 目标时钟: {dst_clk}
// 同步器: {sync_type}
// 风险: {risk_level}
// 警告: CDC 断言假设已有同步器保护
// ============================================================

`timescale 1ns/1ps

module sva_cdc_{id};
    // ------------------------------------------------------------
    // CDC 信号
    // ------------------------------------------------------------
    // TODO: 替换为实际信号
    // input logic {src_clk};        // 源时钟
    // input logic {dst_clk};         // 目标时钟
    // input logic rst_n;
    // input logic [{width}-1:0] data_in;    // 源域数据
    // input logic [{width}-1:0] data_sync;  // 同步后数据

    // ------------------------------------------------------------
    // 断言规则
    // ------------------------------------------------------------
    // 规则 1: 数据稳定（{delay_cycles} 周期延迟）
    // TODO: 确认延迟周期数是否符合同步器
    property cdc_data_stable;
        @(posedge {dst_clk}) disable iff (!rst_n)
        $changed(data_in) |=> ##{delay_cycles} data_sync == $past(data_in, {delay_cycles});
    endproperty

    // 规则 2: 初始值（可选）
    // TODO: 如果对初始值无要求，删除此规则
    property cdc_initial;
        @(posedge {dst_clk}) disable iff (!rst_n)
        $rose rst_n |-> ##{init_delay} data_sync != 'x;
    endproperty

    // ------------------------------------------------------------
    // 断言实例化（默认禁用）
    // ------------------------------------------------------------
    // a_cdc_stable: assert property (cdc_data_stable);
    // a_cdc_init: assert property (cdc_initial);

endmodule
```

---

## 填充说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `{id}` | 唯一标识符 | `0`, `cdc_0` |
| `{date}` | 生成日期 | `2026-05-30` |
| `{path}` | 路径描述 | `data_a → data_sync` |
| `{src_clk}` | 源时钟 | `clk_a` |
| `{dst_clk}` | 目标时钟 | `clk_b` |
| `{sync_type}` | 同步器类型 | `2-FLOP`, `3-FLOP`, `NONE` |
| `{risk_level}` | 风险等级 | `CRITICAL`, `HIGH` |
| `{delay_cycles}` | 延迟周期数 | `2` (2-FLOP), `3` (3-FLOP) |
| `{init_delay}` | 初始值稳定延迟 | `5` |
| `{width}` | 数据位宽 | `32` |

---

## 同步器延迟对照表

| 同步器类型 | 延迟周期 | 风险等级 | 说明 |
|------------|----------|----------|------|
| NONE | 1 | 🔴 CRITICAL | 无同步器，高风险 |
| 2-FLOP | 2 | 🟡 MEDIUM | 标准同步器 |
| 3-FLOP | 3 | 🟢 LOW | 高安全性同步器 |

---

## Review 检查清单

```
工程师 Review 时检查：
1. [ ] 时钟域是否正确（src_clk, dst_clk）
2. [ ] 同步器类型是否与设计一致
3. [ ] 延迟周期数是否符合同步器延迟
4. [ ] 是否需要添加其他 CDC 规则（如 Gray 码检查）
5. [ ] 初始值断言是否需要
```

---

## 相关规则

- `pipeline.md` - 流水线规则（带 CDC 的流水线）
- `handshake.md` - 握手协议（CDC 握手场景）

---

*等待补充更多 CDC 规则（如 Gray 码、多 bit CDC）...*