# OTBN 模块验证问题清单

> 生成日期: 2026-05-14
> 模块: OTBN (hw/ip/otbn/rtl/)
> 验证角度: 设计 / 验证 / 架构 / 时序 / 面积

---

## 问题分类

- **常用 (Common)**: 5 题
- **困难 (Hard)**: 3 题
- **刁钻 (Tricky)**: 2 题

---

## Phase 1: 设计角度

### Q1-C [设计-常用] ALU 结果写回寄存器文件

**问题**: 追踪 `rf_base.wr_data_o` 的完整 driver 路径

**信号**: `rf_base.wr_data`
**模块**: `otbn_core.sv`

**预期考察**:
- ALU, LSU, MAC 等多个写入源
- 多路选择逻辑
- 优先级处理

---

### Q2-C [设计-常用] 指令译码到执行

**问题**: `jal` 指令从译码到 PC 更新的完整路径？

**模块**: `otbn_decoder.sv` → `otbn_controller.sv` → `otbn_rf_base.sv`

**预期考察**:
- 立即数生成
- 目标 PC 计算
- 写回使能

---

### Q3-H [设计-困难] CSR 操作与alu交互

**问题**: CSR 读写操作如何影响后续 ALU 操作？

**模块**: `otbn_alu_base.sv`, CSR registers

**预期考察**:
- CSR 写后立即读
- CSR 指令的握手信号

---

### Q4-H [设计-困难] Loop 指令的嵌套处理

**问题**: `loop` / `loopi` 嵌套时的行为？最多支持几层？

**模块**: `otbn_loop_controller.sv`

**预期考察**:
- stack 实现
- 嵌套深度限制
- 提前退出机制

---

### Q5-T [设计-刁钻] 非法指令的检测点

**问题**: 非法指令在哪个模块被检测？后续如何传播？

**模块**: `otbn_decoder.sv` → `otbn_controller.sv`

**预期考察**:
- 非法指令编码
- error 信号的传播路径

---

## Phase 2: 验证角度

### Q6-C [验证-常用] 寄存器文件写冲突

**问题**: 同一周期对同一寄存器既从 ALU 写又从 LSU 写，结果？

**模块**: `otbn_rf_base.sv`

**预期考察**:
- 写优先级
- RAW (Read After Write) 处理

---

### Q7-C [验证-常用] LSU 访问延迟

**问题**: `ld` 指令结果何时写入寄存器文件？最大延迟？

**模块**: `otbn_lsu.sv`

**预期考察**:
- memory 响应延迟
- stall 机制

---

### Q8-H [验证-困难] 流水线 stall 传播

**问题**: LSU 产生 stall 时，哪些模块收到通知并暂停？

**模块**: `otbn_core.sv` (controller)

**预期考察**:
- stall 信号树
- 各单元响应

---

### Q9-T [验证-刁钻] 中断入口的完整状态保存

**问题**: 中断发生时，哪些状态被保存？保存顺序？

**模块**: `otbn_controller.sv`

**预期考察**:
- PC 保存
- 寄存器文件快照
- CSR 状态

---

## Phase 3: 架构角度

### Q10-C [架构-常用] 向量单元与标量单元数据交换

**问题**: 标量寄存器如何向向量寄存器写入？反向呢？

**模块**: `otbn_vec_*.sv`, `otbn_rf_base.sv`

**预期考察**:
- 矢量转换指令
- 数据格式差异

---

### Q11-C [架构-常用] 与 keymgr 的密钥交互

**问题**: OTBN 如何从 keymgr 获取私钥？接口时序？

**模块**: `otbn.sv` (top level)

**预期考察**:
- sideload 接口
- 密钥加载时机

---

### Q12-H [架构-困难] 多个引擎同时请求 EDN

**问题**: ENTROPY 请求冲突时如何处理？

**模块**: `otbn_rnd.sv`

**预期考察**:
- RND, RNDCSR 请求优先级

---

### Q13-T [架构-刁钻] 跨时钟域的 life cycle

**问题**: otbn_top 多个时钟域的切换顺序？复位时序？

**模块**: `otbn.sv`

**预期考察**:
- 时钟门控顺序
- 复位解除顺序

---

## Phase 4: 时序角度

### Q14-C [时序-常用] MAC 乘累加延迟

**问题**: MAC 结果何时可用？关键路径？

**模块**: `otbn_mac_bignum.sv`

**预期考察**:
- 乘法延迟
- 累加器链

---

### Q15-C [时序-常用] 寄存器读延迟

**问题**: `rf_base` 读操作的数据延迟？back-to-back 读？

**模块**: `otbn_rf_base.sv`

**预期考察**:
- 读端口延迟
- forwarding 逻辑

---

### Q16-H [时序-困难] BN.MULQ 执行周期

**问题**: BN.MULQ (向量乘法) 需要多少周期？是否流水线？

**模块**: `otbn_vec_multiplier.sv`

**预期考察**:
- 乘法器资源
- 调度算法

---

### Q17-T [时序-刁钻] bignum 寄存器 vs w 寄存器 timing

**问题**: bignum 寄存器 (512b) vs w 寄存器 (32b) 的时序差异？

**模块**: `otbn_rf_bignum.sv` vs `otbn_rf_base.sv`

**预期考察**:
- 面积 vs 速度 trade-off

---

## Phase 5: 面积角度

### Q18-C [面积-常用] Register file 面积分布

**问题**: RF (w 寄存器) 占 OTBN 总面积比例？

**模块**: `otbn_rf_base.sv`

**预期考察**:
- 32 x 32b 寄存器
- 读写端口数

---

### Q19-H [面积-困难] BigNum ALU vs Base ALU 面积

**问题**: BN ALU 面积是 Base ALU 的多少倍？

**模块**: `otbn_alu_bignum.sv` vs `otbn_alu_base.sv`

**预期考察**:
- 位宽差异
- 功能复杂度

---

### Q20-T [面积-刁钻] Scramble ctrl 额外面积

**问题**: OTBN 的 `scramble_ctrl` 模块面积代价？是否必需？

**模块**: `otbn_scramble_ctrl.sv`

**预期考察**:
- SRAM 扰码功能
- area overhead

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