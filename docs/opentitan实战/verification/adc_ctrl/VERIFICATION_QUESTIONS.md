# ADC_CTRL 模块验证问题清单

> 生成日期: 2026-05-14
> 模块: ADC_CTRL (hw/ip/adc_ctrl/rtl/)
> 验证角度: 设计 / 验证 / 架构 / 时序 / 面积

---

## 问题分类

- **常用 (Common)**: 5 题
- **困难 (Hard)**: 3 题
- **刁钻 (Tricky)**: 2 题

---

## Phase 1: 设计角度

### Q1-C [设计-常用] ADC采样触发路径

**问题**: `adc_o.pd` (power down) 信号如何从 FSM 控制？

**信号**: `adc_o.pd`
**模块**: `adc_ctrl_fsm.sv`

**预期考察**:
- FSM 状态机
- 低功耗模式切换

---

### Q2-C [设计-常用] 中断信号生成

**问题**: `intr_match_pending_o` 的完整生成路径？

**信号**: `intr_match_pending_o`
**模块**: `adc_ctrl_intr.sv`

**预期考察**:
- 中断使能条件
- 边沿 vs 电平触发

---

### Q3-H [设计-困难] 通道选择逻辑

**问题**: `adc_o.channel_sel` 如何决定？与 FSM 状态关系？

**信号**: `adc_o.channel_sel`
**模块**: `adc_ctrl_fsm.sv`

**预期考察**:
- 通道选择状态机
- 2-bit 控制 (00=stop, 01=ch1, 10=ch2, 11=illegal)

---

### Q4-H [设计-困难] 过滤状态更新条件

**问题**: `aon_filter_status_o` 何时更新？更新条件？

**信号**: `aon_filter_status_o`
**模块**: `adc_ctrl_core.sv`

**预期考察**:
- filter 比较逻辑
- 状态寄存器写入

---

### Q5-T [设计-刁钻] 低功耗时钟切换

**问题**: `clk_aon_i` 和 `clk_i` 切换时序？何时使用哪个？

**信号**: `clk_aon_i`, `clk_i`
**模块**: `adc_ctrl.sv`

**预期考察**:
- 两个时钟域的用途
- 切换条件

---

## Phase 2: 验证角度

### Q6-C [验证-常用] 中断清除时序

**问题**: 软件清除中断后，intr_match_pending_o 何时拉低？

**信号**: `intr_state` register field
**模块**: `adc_ctrl_reg_top.sv`

**预期考察**:
- 寄存器写入到输出延迟
- 中断确认 handshake

---

### Q7-C [验证-常用] wakeup请求生成延迟

**问题**: `wkup_req_o` 从条件满足到有效最大延迟？

**信号**: `wkup_req_o`
**模块**: `adc_ctrl_core.sv`

**预期考察**:
- 组合路径延迟
- 同步/异步

---

### Q8-H [验证-困难] 滤波器状态历史

**问题**: filter 使用多少历史样本做判决？

**模块**: `adc_ctrl_core.sv`

**预期考察**:
- filter 窗口大小
- 样本计数

---

### Q9-T [验证-刁钻] 重复采样debounce

**问题**: 同一通道连续采样间隔？debounce 机制？

**模块**: `adc_ctrl_fsm.sv`

**预期考察**:
- 采样间隔配置
- debounce 防抖

---

## Phase 3: 架构角度

### Q10-C [架构-常用] AST接口交互

**问题**: `adc_o` 和 `adc_i` 完整接口定义？与 AST 模块关系？

**信号**: `adc_ast_req_t`, `adc_ast_rsp_t`
**模块**: `adc_ctrl.sv`

**预期考察**:
- 接口定义包
- 与 AST 的 handshake

---

### Q11-C [架构-常用] pwrmgr接口

**问题**: `wkup_req_o` 连接到什么模块？预期响应？

**信号**: `wkup_req_o`
**模块**: `adc_ctrl.sv`

**预期考察**:
- pwrmgr 接口
- wakeup 序列

---

### Q12-H [架构-困难] 跨时钟域数据稳定

**问题**: slow clock (clk_aon) 数据如何同步到 fast clock (clk_i)？

**模块**: `adc_ctrl_core.sv`

**预期考察**:
- CDC 同步器
- 数据稳定化

---

### Q13-T [架构-刁钻] 复位期间的ADC控制

**问题**: rst_aon_ni 和 rst_ni 同时撤销时，ADC 初始化顺序？

**信号**: rst_ni, rst_aon_ni
**模块**: `adc_ctrl.sv`

**预期考察**:
- 两个复位域
- 初始化序列

---

## Phase 4: 时序角度

### Q14-C [时序-常用] 采样完成延迟

**问题**: ADC 采样完成后，数据有效延迟？

**信号**: `adc_i.data_valid`
**模块**: `adc_ctrl_intr.sv`

**预期考察**:
- ADC 转换时间
- 中断延迟

---

### Q15-C [时序-常用] 寄存器访问延迟

**问题**: TLUL 接口访问延迟？读 vs 写？

**模块**: `adc_ctrl_reg_top.sv`

**预期考察**:
- TLUL 协议延迟
- 读数据返回周期

---

### Q16-H [时序-困难] filter比较器延迟

**问题**: `adc_i.data` 到 `aon_filter_status` 变化的延迟？

**信号**: `adc_i.data`, `aon_filter_status_o`
**模块**: `adc_ctrl_core.sv`

**预期考察**:
- 比较器延迟
- 状态更新延迟

---

### Q17-T [时序-刁钻] 两路ADC时钟同步

**问题**: 两路ADC采样数据到达的时序差异？

**信号**: adc_i.data (ch1 vs ch2)
**模块**: `adc_ctrl_core.sv`

**预期考察**:
- 采样相位差异
- 数据对齐

---

## Phase 5: 面积角度

### Q18-C [面积-常用] FSM实现面积

**问题**: `adc_ctrl_fsm` 状态寄存器数量？

**模块**: `adc_ctrl_fsm.sv`

**预期考察**:
- 状态编码方式
- 寄存器数量

---

### Q19-H [面积-困难] 滤波器实现方式

**问题**: 2-bit filter 状态 vs 实际实现面积？

**模块**: `adc_ctrl_core.sv`

**预期考察**:
- filter 逻辑 vs 存储
- 综合结果

---

### Q20-T [面积-刁钻] 低功耗设计面积代价

**问题**: Always-on 逻辑占总面积比例？

**模块**: `adc_ctrl_core.sv`

**预期考察**:
- aon 域 vs main 域
- 面积分布

---

## 问题优先级汇总

| ID | 类别 | 难度 | 优先级 |
|----|------|------|--------|
| Q1 | 设计 | 常用 | P1 |
| Q2 | 设计 | 常用 | P1 |
| Q3 | 设计 | 困难 | P2 |
| Q4 | 设计 | 困难 | P2 |
| Q5 | 设计 | 刁钻 | P3 |
| Q6 | 验证 | 常用 | P1 |
| Q7 | 验证 | 常用 | P1 |
| Q8 | 验证 | 困难 | P2 |
| Q9 | 验证 | 刁钻 | P3 |
| Q10 | 架构 | 常用 | P1 |
| Q11 | 架构 | 常用 | P1 |
| Q12 | 架构 | 困难 | P2 |
| Q13 | 架构 | 刁钻 | P3 |
| Q14 | 时序 | 常用 | P1 |
| Q15 | 时序 | 常用 | P1 |
| Q16 | 时序 | 困难 | P2 |
| Q17 | 时序 | 刁钻 | P3 |
| Q18 | 面积 | 常用 | P1 |
| Q19 | 面积 | 困难 | P2 |
| Q20 | 面积 | 刁钻 | P3 |

---

## 文档更新记录

| 日期 | 更新内容 |
|------|---------|
| 2026-05-14 | 初版创建，20 个问题 |