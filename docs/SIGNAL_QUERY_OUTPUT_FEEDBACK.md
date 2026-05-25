# Signal Query 输出格式反馈

**版本**: v0.1  
**日期**: 2026-05-25  
**项目**: OpenTitan UART 模块测试  
**测试信号**: `uart_rx.rx_data`

---

## 背景

在 OpenTitan UART 模块上测试 signal query 功能，目标是返回信号的完整信息（定义、driver、load、条件），帮助 Agent 理解并进行 debug。

---

## 当前输出

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

---

## 评价

### ✅ 优点

| 优点 | 说明 |
|------|------|
| 结构清晰 | JSON 格式易于解析 |
| 基本属性全 | kind, name, width, module 都有 |
| 层级关系 | drivers/loads 分离，距离信息有用 |

### ❌ 缺失的关键信息

| 问题 | 说明 | 优先级 |
|------|------|--------|
| **缺少源码位置** | file, line 信息缺失 | P1 |
| **缺少驱动条件 (condition)** | 用户明确要求，但完全没有实现 | P0 |
| **缺少赋值表达式** | 需要知道具体怎么驱动的 | P0 |
| **Width 格式不直观** | [7, 0] 不如 [7:0] 直观 | P2 |
| **缺少时钟/复位域信息** | clock_domain, reset_domain 缺失 | P1 |
| **Loads 为空** | rx_data 作为 output 实际被外部使用，但未显示 | P1 |

---

## 目标格式（期望）

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
    "reset_domain": "rst_ni"
  },
  "drivers": [
    {
      "id": "uart_rx.sreg_q",
      "expression": "sreg_q[8:1]",
      "condition": "tick_baud_q",
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

## 核心改进点

### P0 (必须)

1. **Condition 提取**
   - 从 always_ff/always_comb 语句中提取使能条件
   - 如 `if (tick_baud_q)` 驱动时使能
   - 这是用户最关心的信息

2. **Driver Expression 提取**
   - 驱动信号的完整表达式
   - 部分选择时需要明确

### P1 (重要)

3. **源码位置**
   - file, line 信息
   - 便于 Agent 定位代码

4. **Clock/Reset Domain**
   - 时钟和复位信号名称
   - 用于 CDC 分析

5. **Loads 追溯**
   - PORT_OUT 的外部连接
   - 需要跨模块追溯

### P2 (优化)

6. **Width 格式**
   - 统一使用 `[msb:lsb]` 格式

---

## 结论

| 维度 | 当前评分 | 目标 |
|------|----------|------|
| **完整性** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **有用性** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **准确性** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**核心问题**：**Condition 信息完全没有实现**，这是 signal query 的核心价值所在。

---

## 后续任务

- [ ] 实现 condition 提取功能
- [ ] 实现 driver expression 提取
- [ ] 添加 file/line 信息
- [ ] 添加 clock/reset domain
- [ ] 完善 loads 追溯
- [ ] 更新架构报告
