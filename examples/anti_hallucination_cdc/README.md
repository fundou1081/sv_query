# 反幻觉 walkthrough：单级 CDC 被说成“两级同步”

**目标**: 5 分钟内看到一个“看似合理但错误”的根因，如何被 sv_query 的结构证据反驳。

## 0. 场景

[cdc_bug.sv](cdc_bug.sv) 中，`src_valid` 在 `dst_clk` 域只被打了一拍：

```systemverilog
always_ff @(posedge dst_clk or negedge resetn) begin
  if (!resetn) dst_valid <= 1'b0;
  else         dst_valid <= src_valid;   // line 15
end
```

Agent 的错误结论（很常见）：

> “`dst_valid` 在 `dst_clk` 域内寄存，说明已经有两级同步器，CDC 安全。”

**错误点**: “寄存了一拍” ≠ “两级同步器”。这里没有 `meta` 中间级。

## 1. 查 profile：确认它确实在 dst_clk 域

```bash
cd /Users/fundou/my_dv_proj/sv_query
sv_query trace profile cdc_bug.dst_valid \
  -f examples/anti_hallucination_cdc/cdc_bug.sv --json
```

关键输出：

```json
{
  "signal": "cdc_bug.dst_valid",
  "kind": "REG",
  "clock_domains": ["dst_clk"],
  "source": {
    "file": "examples/anti_hallucination_cdc/cdc_bug.sv",
    "line": 15
  }
}
```

这支持“它在 dst_clk 域”，但**不证明**有同步链。

## 2. 查 fanin：反驳“两级同步器”

```bash
sv_query trace fanin cdc_bug.dst_valid \
  -f examples/anti_hallucination_cdc/cdc_bug.sv --json
```

关键输出（截取）：

```json
{
  "signal": "cdc_bug.dst_valid",
  "drivers": [
    {
      "id": "cdc_bug.src_valid",
      "kind": "PORT_IN",
      "distance": 1,
      "condition": "!(!resetn)"
    },
    {
      "id": "1'b0",
      "kind": "CONST",
      "distance": 1
    }
  ]
}
```

`dst_valid` 的直接驱动只有 `src_valid` 和复位常量；**没有 meta 寄存器**，距离是 1。

## 3. 反向确认：src_valid 只被 dst_valid 采一次

```bash
sv_query trace fanout cdc_bug.src_valid \
  -f examples/anti_hallucination_cdc/cdc_bug.sv --json
```

关键输出：

```json
{
  "signal": "cdc_bug.src_valid",
  "loads": [
    {
      "id": "cdc_bug.dst_valid",
      "kind": "REG",
      "distance": 1
    }
  ]
}
```

## 4. Ground truth

- 故障行：[cdc_bug.sv:15](cdc_bug.sv)，`dst_valid <= src_valid`；
- 结构事实：`src_valid → dst_valid` 只有一拍，缺少 `meta` 中间级；
- 正确修复（不是本工具的自动修改）：

```systemverilog
logic meta;
always_ff @(posedge dst_clk or negedge resetn) begin
  if (!resetn) begin
    meta     <= 1'b0;
    dst_valid <= 1'b0;
  end else begin
    meta     <= src_valid;
    dst_valid <= meta;
  end
end
```

## 5. 这个例子的边界

- 证明的是**图中不存在两级链路**，不是“CDC 一定失败”；
- 不替代 CDC 规则检查/时序约束/仿真；
- 不修改用户 RTL；修复片段仅作 ground truth 说明。
