# OpenTitan 实战 - 跨模块 Driver/Load 追踪验证

**验证日期**: 2026-05-13  
**验证目标**: 使用 OpenTitan RTL 验证 sv_query 的跨模块 driver/load 追踪能力  
**铁律**: 遵循项目开发纪律（金标准测试 + RTL 来源真实场景）

---

## 场景选择

| 模块 | 路径 | 选择理由 |
|------|------|----------|
| `uart_tx` | `opentitan/hw/ip/uart/rtl/uart_tx.sv` | 简单模块，输出端口，driver 链清晰 |
| `uart_rx` | `opentitan/hw/ip/uart/rtl/uart_rx.sv` | 类似简单模块，验证一致性 |
| `uart_core` | `opentitan/hw/ip/uart/rtl/uart_core.sv` | 组合 uart_tx/rx，包含跨模块连接 |

---

## 验证方法

1. **Verilator 语法验证**: 所有 RTL 必须通过 lint
2. **手动推导金标准**: 脱离被测代码，从 RTL 人工推导预期结果
3. **对比验证**: 运行 sv_query，与金标准逐项对比
4. **完整记录**: 记录每个信号的 driver/load 追踪结果

---

## 目录结构

```
docs/opentitan实战/
├── README.md              # 本文件
├── uart_tx_driver追踪.md   # uart_tx 模块 driver 链验证
├── uart_rx_driver追踪.md   # uart_rx 模块 driver 链验证
├── uart_core跨模块追踪.md   # uart_core 跨模块连接验证
└── 验证结果汇总.md          # 所有验证结果汇总
```

---

## 验证流程

### 1. 选择 RTL 模块
- 选择具有代表性的 IP 模块
- 验证跨模块边界连接

### 2. 手动推导金标准
```
RTL 源码分析 → 预期 driver/load 关系 → 记录为金标准
```

### 3. 运行 sv_query
```
sv_query(graph.find_drivers) → 实际结果
```

### 4. 对比验证
```
金标准 vs 实际结果 → 一致性判断
```

---

## 预期输出

每个验证文档应包含：
1. **RTL 源码** (关键片段)
2. **手动推导的金标准** (表格形式)
3. **sv_query 实际输出**
4. **对比结果** (一致/不一致)
5. **如有差异，根因分析**
---

## 复杂度分级参考

| 复杂度 | 模块 | RTL 行数 | 适合场景 |
|--------|------|----------|----------|
| 简单 | adc_ctrl | ~5.6K | 快速功能验证 |
| 中等 | aes | ~17K | 多路选择、条件驱动追踪 |
| 复杂 | otbn | ~15K | 多驱动源、深层次模块追踪 |

详细分析见 [RTL_COMPLEXITY_ANALYSIS.md](RTL_COMPLEXITY_ANALYSIS.md)

---

## 独立验证流程

**重要**: 验证独立于项目测试框架，暂不参与回归测试。

详细流程见 [verification/README.md](verification/README.md)

### 核心原则

1. **问题驱动** - 先提出具体验证问题
2. **人工推导** - 不查看工具代码，仅阅读 RTL 源码
3. **多次确认** - 复杂设计需要反复确认
4. **独立记录** - Golden 结果与工具输出分开记录

### 验证目录

```
docs/opentitan实战/verification/
├── README.md           # 验证流程
├── aes/
│   ├── VERIFICATION_PLAN.md
│   └── golden_*.md
├── otbn/
└── adc_ctrl/
```

### 当前进度

| 模块 | 状态 | 验证问题数 |
|------|------|-----------|
| aes | 规划中 | 5 |
| otbn | 待开始 | - |
| adc_ctrl | 待开始 | - |
