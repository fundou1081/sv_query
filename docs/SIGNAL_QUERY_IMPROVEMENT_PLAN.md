# Signal Query 功能改进计划

**版本**: v0.2  
**日期**: 2026-05-25  
**状态**: P0-1, P0-2 已完成  
**项目**: OpenTitan UART 模块测试

---

## 测试环境

### 源代码
- **项目**: OpenTitan
- **路径**: `~/my_dv_proj/opentitan`
- **测试模块**: `uart_rx`
- **测试文件**: `hw/ip/uart/rtl/uart_rx.sv`
- **测试信号**: `uart_rx.rx_data`

### 代码规模
- `uart_rx.sv`: 1928 bytes
- 模块类型: UART Receive Module

### 源码内容

```systemverilog
module uart_rx (
  input           clk_i,
  input           rst_ni,
  input           rx_enable,
  input           tick_baud_x16,
  input           parity_enable,
  input           parity_odd,
  output logic    tick_baud,
  output logic    rx_valid,
  output [7:0]    rx_data,
  output logic    idle,
  output          frame_err,
  output          rx_parity_err,
  input           rx
);

  logic            rx_valid_q;
  logic   [10:0]   sreg_q, sreg_d;
  logic    [3:0]   bit_cnt_q, bit_cnt_d;
  logic    [3:0]   baud_div_q, baud_div_d;
  logic            tick_baud_d, tick_baud_q;
  logic            idle_d, idle_q;

  assign tick_baud = tick_baud_q;
  assign idle      = idle_q;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      sreg_q      <= 11'h0;
      bit_cnt_q   <= 4'h0;
      baud_div_q  <= 4'h0;
      tick_baud_q <= 1'b0;
      idle_q      <= 1'h1;
    end else begin
      sreg_q      <= sreg_d;
      bit_cnt_q   <= bit_cnt_d;
      baud_div_q  <= baud_div_d;
      tick_baud_q <= tick_baud_d;
      idle_q      <= idle_d;
    end
  end

  always_comb begin
    if (!rx_enable) begin
      sreg_d      = 11'h0;
      bit_cnt_d   = 4'h0;
      baud_div_d  = 4'h0;
      tick_baud_d = 1'b0;
      idle_d      = 1'b1;
    end else begin
      tick_baud_d = 1'b0;
      sreg_d      = sreg_q;
      bit_cnt_d   = bit_cnt_q;
      baud_div_d  = baud_div_q;
      idle_d      = idle_q;
      if (tick_baud_x16) begin
        {tick_baud_d, baud_div_d} = {1'b0,baud_div_q} + 5'h1;
      end
      // ... 更多逻辑
    end
  end
endmodule
```

---

## 现状分析

### 当前输出

```json
{
  "signal": "uart_rx.rx_data",
  "module": "uart_rx",
  "definition": {
    "type": "output logic [7:0]",
    "kind": "PORT_OUT",
    "name": "rx_data",
    "width": [7, 0],
    "is_clock": false,
    "is_reset": false,
    "is_enable": false
  },
  "drivers": [
    {
      "kind": "PORT_IN",
      "name": "parity_enable",
      "module": "uart_rx",
      "width": [1, 0],
      "distance": 1
    },
    {
      "kind": "SIGNAL",
      "name": "sreg_q[8:1]",
      "module": "uart_rx",
      "bit_range": "[8:1]",
      "width": [8, 1],
      "distance": 1
    },
    {
      "kind": "SIGNAL",
      "name": "sreg_q[9:2]",
      "module": "uart_rx",
      "bit_range": "[9:2]",
      "width": [9, 2],
      "distance": 1
    }
  ],
  "loads": []
}
```

### 当前评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **完整性** | ⭐⭐ | 缺少 file/line/condition/expression |
| **有用性** | ⭐⭐⭐ | 基本结构有用，但关键调试信息缺失 |
| **准确性** | ⭐⭐⭐⭐ | kind/width/module 准确 |

---

## 改进计划

### P0 - 必须修复 (Core Features)

| # | 任务 | 当前状态 | 目标 | 复杂度 |
|---|------|---------|------|--------|
| P0-1 | **Condition 提取** | 完全缺失 | 从 always_ff/always_comb 提取使能条件 | 🔴 高 |
| P0-2 | **Driver Expression 提取** | 缺失 | 获取完整的驱动表达式 | 🔴 高 |

#### P0-1: Condition 提取

**问题**: 用户需要知道信号在什么条件下被驱动，但当前完全缺失

**代码示例**:
```systemverilog
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) begin
    sreg_q <= '0;           // reset condition: !rst_ni
  end else if (tick_baud_q) begin  // ← 需要提取这个条件
    sreg_q <= sreg_d;
  end
end
```

**期望输出**:
```json
{
  "drivers": [{
    "id": "uart_rx.sreg_q",
    "condition": "tick_baud_q",
    "reset_condition": "!rst_ni",
    "assignment_type": "always_ff"
  }]
}
```

**实现思路**:
1. 在 `signal_expression_visitor.py` 中扩展 visit 方法
2. 提取 `if` 语句的条件作为 condition
3. 关联 always_ff/always_comb 的时钟/复位信息

---

#### P0-2: Driver Expression 提取

**问题**: 需要知道具体的驱动表达式，而非仅信号名

**期望输出**:
```json
{
  "drivers": [{
    "id": "uart_rx.sreg_q",
    "expression": "sreg_d",      // ← 具体表达式
    "bit_slice": "[8:1]",        // ← 位选择
    "condition": "tick_baud_q"
  }]
}
```

---

### P1 - 重要功能 (Important Features)

| # | 任务 | 当前状态 | 目标 | 复杂度 |
|---|------|---------|------|--------|
| P1-3 | **源码位置** | 缺失 | 添加 file/line 信息 | 🟡 中 |
| P1-4 | **Clock/Reset Domain** | 缺失 | 标注时钟和复位域 | 🟡 中 |
| P1-5 | **Loads 追溯** | 空 | PORT_OUT 的外部连接 | 🔴 高 |

#### P1-3: 源码位置

**期望输出**:
```json
{
  "signal": "uart_rx.rx_data",
  "file": "hw/ip/uart/rtl/uart_rx.sv",
  "line": 15,
  "definition": {
    "file": "hw/ip/uart/rtl/uart_rx.sv",
    "line": 15
  },
  "drivers": [{
    "id": "uart_rx.sreg_q",
    "file": "hw/ip/uart/rtl/uart_rx.sv",
    "line": 65
  }]
}
```

---

#### P1-4: Clock/Reset Domain

**期望输出**:
```json
{
  "definition": {
    "kind": "PORT_OUT",
    "clock_domain": "clk_i",
    "reset_domain": "rst_ni"
  }
}
```

---

#### P1-5: Loads 追溯

**问题**: rx_data 作为 output port，loads 为空，应该追溯到外部连接

**期望**: 应该显示连接到 rx_data 的外部信号

---

### P2 - 优化 (Polish)

| # | 任务 | 当前状态 | 目标 | 复杂度 |
|---|------|---------|------|--------|
| P2-6 | **Width 格式** | `[7, 0]` | `[7:0]` | 🟢 低 |

---

## P0-1 实现总结 (v0.2 - 2026-05-25)

### 实现内容

1. **新增 DriverInfo 数据类** (`graph/models.py`)
   ```python
   @dataclass
   class DriverInfo:
       node: TraceNode           # 驱动节点
       condition: str = ""       # 驱动条件
       reset_condition: str = "" # 复位条件
       clock_domain: str = ""    # 时钟域
       assign_type: str = ""     # always_ff/always_comb/continuous
       distance: int = 1         # 驱动距离
       expression: str = ""      # 驱动表达式
   ```

2. **新增 trace_fanin_detailed() 方法** (`query/signal.py`)
   - 返回 `List[DriverInfo]` 替代 `List[TraceNode]`
   - 从边的 condition 字段提取条件信息

3. **新增 trace_detailed() 方法** (`query/signal.py`)
   - 返回 `DriverChain` 替代 `SignalChain`
   - 包含详细驱动信息

4. **在 UnifiedTracer 暴露新 API** (`unified_tracer.py`)
   - `trace_detailed()` - 带详细信息的追溯
   - `trace_fanin_detailed()` - 带详细信息的 fanin

### 验证结果

```bash
$ pytest sim/tests -q
996 passed, 1 skipped, 1 warning in 18.03s
```

### 输出示例

```json
{
  "signal": "uart_rx.sreg_q",
  "module": "uart_rx",
  "confidence": "high",
  "drivers": [
    {
      "id": "uart_rx.sreg_d",
      "kind": "SIGNAL",
      "condition": "!!rst_ni",
      "clock_domain": "clk_i",
      "assign_type": "nonblocking"
    },
    {
      "id": "uart_rx.rx",
      "kind": "PORT_IN",
      "condition": "",
      "clock_domain": "",
      "assign_type": ""
    }
  ]
}
```

---

## P0-2 实现总结 (v0.2 - 2026-05-25)

### 实现内容

1. **TraceEdge 新增字段** (`graph/models.py`)
   - `expression`: 驱动表达式 (如 "sreg_d")
   - `bit_slice`: 位选择 (如 "[8:1]")

2. **DriverInfo 新增字段** (`graph/models.py`)
   - `expression`: 驱动表达式
   - `bit_slice`: 位选择

3. **graph_builder.py 填充 expression**
   - 使用 `SignalExpressionVisitor.visit()` 获取可读的表达式字符串

### 验证结果

```bash
$ pytest sim/tests -q
996 passed, 1 skipped, 1 warning in 18.35s
```

### 输出示例

```json
{
  "signal": "uart_rx.sreg_q",
  "drivers": [
    {
      "id": "uart_rx.sreg_d",
      "expression": "sreg_d",
      "condition": "!!rst_ni",
      "clock_domain": "clk_i"
    }
  ]
}
```

---

### 根因分析

| 组件 | 状态 |
|------|------|
| Condition 提取 | ✅ 早已实现 (statement_collector_visitor.py) |
| Condition 存储 | ✅ TraceEdge.condition |
| **Condition 返回** | ✅ **现已实现** (DriverInfo) |

---

## 实现顺序

```
P0-1: Condition 提取 ← 从这里开始
    ↓
P0-2: Driver Expression 提取
    ↓
P1-3: 源码位置
    ↓
P1-4: Clock/Reset Domain
    ↓
P1-5: Loads 追溯
    ↓
P2-6: Width 格式优化
```

---

## 目标格式

```json
{
  "signal": "uart_rx.rx_data",
  "module": "uart_rx",
  "file": "hw/ip/uart/rtl/uart_rx.sv",
  "line": 15,
  "definition": {
    "type": "output logic [7:0]",
    "kind": "PORT_OUT",
    "width": "[7:0]",
    "clock_domain": "clk_i",
    "reset_domain": "rst_ni",
    "file": "hw/ip/uart/rtl/uart_rx.sv",
    "line": 15
  },
  "drivers": [
    {
      "id": "uart_rx.sreg_q",
      "expression": "sreg_d",
      "bit_slice": "[8:1]",
      "condition": "tick_baud_q",
      "reset_condition": "!rst_ni",
      "assignment_type": "always_ff",
      "file": "hw/ip/uart/rtl/uart_rx.sv",
      "line": 65,
      "distance": 1
    }
  ],
  "loads": [
    {
      "id": "uart_rx.rx_valid",
      "condition": "rx_valid_q",
      "distance": 1
    }
  ]
}
```

---

## 目标评分

| 维度 | 当前 | 目标 |
|------|------|------|
| **完整性** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **有用性** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **准确性** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 后续任务清单

- [x] P0-1: 实现 condition 提取功能 ✅ (v0.2)
- [x] P0-2: 实现 driver expression 提取 ✅ (v0.2)
- [ ] P1-3: 添加 file/line 信息
- [ ] P1-4: 添加 clock/reset domain
- [ ] P1-5: 完善 loads 追溯
- [ ] P2-6: 统一 width 格式
- [ ] 更新架构报告
- [ ] 添加单元测试
