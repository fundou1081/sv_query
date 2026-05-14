# AES 模块验证问题清单

> 生成日期: 2026-05-14
> 模块: AES (hw/ip/aes/rtl/)
> 验证角度: 设计 / 验证 / 架构 / 时序 / 面积

---

## 问题分类比例

- **常用 (Common)**: 5 题 - 基础功能验证
- **困难 (Hard)**: 3 题 - 复杂场景追踪
- **刁钻 (Tricky)**: 2 题 - 边界/Corner Case

**总计**: 20+ 题

---

## Phase 1: 设计角度（设计正确性）

### Q1-C [设计-常用] state_out 数据路径

**问题**: 追踪 `state_out[0][0][7:0]` 的完整 driver 路径

**信号**: `state_out[3:0][3:0][7:0]`
**模块**: `aes_core.sv`

**预期考察**:
- 多路选择器 `state_out_sel` 的作用
- `state_done` vs `state_init` vs `1'b0` 的选择条件
- SubBytes + MixColumns 的数据变换

---

### Q2-C [设计-常用] 密钥扩展启动条件

**问题**: `key_init_q` 在什么条件下从 `key_init_d` 加载新值？

**信号**: `key_init_q[NumRegsKey-1:0][31:0]`
**模块**: `aes_core.sv`

**预期考察**:
- 握手信号 `key_init_qe`
- 控制状态机 `ctrl.init` vs `ctrl.update`
- 多阶段 key expand 状态

---

### Q3-H [设计-困难] 多路选择器sel信号生成

**问题**: `state_in_sel_ctrl` 信号如何生成？它与 `cipher_op` 的关系？

**信号**: `state_in_sel`, `si_sel_e`
**模块**: `aes_core.sv`

**预期考察**:
- `si_sel_e` 枚举类型所有选项
- 各选择条件下的 source：
  - `SI_IV`: 来自 IV/计数器
  - `SI_ZERO`: 清除
  - `SI_ONE`: 固定值
  - `SI_KEY`: 密钥扩展结果

---

### Q4-H [设计-困难] GCM 模式的特殊数据路径

**问题**: GCM 模式下 `ghash_data_o` 的 driver 是什么？何时有效？

**信号**: `ghash_data_o`
**模块**: `aes_core.sv`

**预期考察**:
- `gcm_phase_q` 控制的有效范围
- `GHASH` vs `GHASH_INIT` vs `GHASH_CT` 阶段区分
- 与 `cipher_op` 的交互

---

### Q5-T [设计-刁钻] Shadow register 更新延迟

**问题**: `ctrl_shadowed` 更新时会产生哪些信号变化？时序关系？

**信号**: `ctrl_reg_err_update`, `ctrl_reg_err_storage`
**模块**: `aes_control.sv`

**预期考察**:
- Shadow register 的双拍机制
- `update_err` vs `storage_err` 区别
- 对 FSM 状态的影响

---

## Phase 2: 验证角度（验证覆盖）

### Q6-C [验证-常用] entropy 请求-应答握手

**问题**: `entropy_clearing_req_o` 和 `entropy_clearing_ack_i` 的完整握手时序？

**信号**: `entropy_clearing_req_o`, `entropy_clearing_ack_i`
**模块**: `aes_core.sv`

**预期考察**:
- req 置高条件
- ack 回来后 req 何时清除
- 超时/死锁场景

---

### Q7-C [验证-常用] 计数器进位链延迟

**问题**: `ctr[0]` 从 8'hFF 进位到 8'h00 时，`ctr[1]` 何时变化？

**信号**: `ctr[NumSlicesCtr-1:0][SliceSizeCtr-1:0]`
**模块**: `aes_ctr.sv`

**预期考察**:
- 进位链 ripple vs synchronous
- `ctr_inc` 控制下的行为
- 边界：max 值 wrap

---

### Q8-H [验证-困难] 多信号同时变化的时钟域

**问题**: `shadowed_update_err_i` 和 `shadowed_storage_err_i` 在哪个时钟域有效？

**信号**: `shadowed_update_err_i`, `shadowed_storage_err_i`
**模块**: `aes_core.sv`

**预期考察**:
- 同步 vs 异步信号
- 对 `ctrl_reg_err_update` 的组合逻辑影响
- 是否需要 CDC 处理

---

### Q9-T [验证-刁钻] 强制清除场景的优先级

**问题**: `clear_on_fatal` 为 1 时，哪些信号被强制清除？优先级？

**信号**: `clear_on_fatal`, 内部 state/key registers
**模块**: `aes_core.sv`

**预期考察**:
- fatal error 的来源
- 清除是同步还是异步
- 与 normal clear 的区别

---

## Phase 3: 架构角度（模块交互）

### Q10-C [架构-常用] keymgr sideload 接口

**问题**: `keymgr_key_i` 如何传递到内部密钥信号？哪一步使用？

**信号**: `keymgr_key_i`, `key_sideload`
**模块**: `aes_core.sv`

**预期考察**:
- `sideload_q` 控制选择
- key sideload vs key_init 的多路选择
- keymgr 接口时序要求

---

### Q11-C [架构-常用] LC escalation 控制路径

**问题**: `lc_escalate_en_i` 如何影响 AES 操作？什么情况下生效？

**信号**: `lc_ctrl_pkg::lc_tx_t lc_escalate_en_i`
**模块**: `aes_core.sv`

**预期考察**:
- `lc_tx_t` 类型（On/Off/Warning）
- escalation 对 PRNG/entropy 的影响
- 是否影响数据路径

---

### Q12-H [架构-困难] 跨模块的 alert 信号传播

**问题**: `alerts[0]` 的完整生成和传播路径？

**信号**: `alerts[0]`, `alert_tx_o[0]`
**模块**: `aes_core.sv`

**预期考察**:
- 多源 alert：`ctrl_alert`, `mux_sel_err`, `sp_enc_err`
- `intg_err_alert_i` 的来源
- prim_alert_sender 实例化

---

### Q13-T [架构-刁钻] 多 slice CTR 的跨 slice 进位

**问题**: 4 slice CTR 计数器，当 slice[0] 从 255→0 时，slice[1] 是否立即进位？

**信号**: `ctr[3:0][7:0]`
**模块**: `aes_ctr.sv`

**预期考察**:
- slice 之间的进位逻辑
- 进位延迟（ripple chain）
- 对 AES-CTR 吞吐量的影响

---

## Phase 4: 时序角度（Timing Critical）

### Q14-C [时序-常用] S-Box 关键路径延迟

**问题**: SubBytes 的 critical path 经过哪些组件？延迟来源？

**信号**: `state_out` (combinational path)
**模块**: `aes_sbox*.sv`

**预期考察**:
- S-Box 实现选择（canright/dom/lut）
- `SecSBoxImpl` 参数影响
- 关键路径：input → S-Box → output

---

### Q15-C [时序-常用] PRNG reseed 时序

**问题**: `entropy_masking_req_o` 置高后，最长等待多少周期才有 `entropy_masking_ack_i`？

**信号**: `entropy_masking_req_o`
**模块**: `aes_entropy.sv`

**预期考察**:
- 请求到 ack 的最大延迟
- 超时处理机制
- 对加密吞吐量的影响

---

### Q16-H [时序-困难] 密钥扩展多周期时序

**问题**: 密钥扩展完成需要多少周期？与 key_len 关系？

**信号**: `key_init_we`, `key_init_cipher`
**模块**: `aes_key_expand.sv`

**预期考察**:
- 128/192/256 位密钥的扩展周期差异
- 扩展是否可流水线
- 对 throughput 的影响

---

### Q17-T [时序-刁钻] masking 两 shares 同步

**问题**: `SecMasking=1` 时，两份 shares 的计算是否完全同步？延迟差异？

**信号**: `state_init [NumShares]`, `state_mask`
**模块**: `aes_core.sv`

**预期考察**:
- 两份 share 的独立计算
- 何时需要重新对齐（reshare）
- 对 critical path 的影响

---

## Phase 5: 面积角度（Area/Power）

### Q18-C [面积-常用] S-Box 面积 vs 速度 trade-off

**问题**: 不同 `SecSBoxImpl` 参数对应的面积差异？

**信号**: `sbox_impl_e` (SBoxImplDom/CanRight/Lut)
**模块**: `aes_sbox*.sv`

**预期考察**:
- DOM (掩码) vs CanRight vs LUT 面积对比
- 是否可配置
- 对综合结果的影响

---

### Q19-H [面积-困难] 复用逻辑的面积优化

**问题**: MixColumns 在加密和解密时是否共享？实现方式？

**信号**: `mix_columns_sel`
**模块**: `aes_mix_columns.sv`

**预期考察**:
- 加密/解密 MixColumns 差异
- 是否通过 Invsbox+Same 复用
- 对面积的影响

---

### Q20-T [面积-刁钻] 清除逻辑的额外面积

**问题**: `clear_on_fatal` 功能是否需要额外寄存器？面积代价？

**信号**: `clear_on_fatal`, internal clearing muxes
**模块**: `aes_control.sv`

**预期考察**:
- 是否是纯粹的控制逻辑
- 还是需要额外的 state retention
- 综合工具是否能优化

---

## 问题优先级汇总

| ID | 类别 | 难度 | 角度 | 优先级 |
|----|------|------|------|--------|
| Q1 | 设计 | 常用 | 数据路径 | P1 |
| Q2 | 设计 | 常用 | 密钥扩展 | P1 |
| Q3 | 设计 | 困难 | 多路选择 | P1 |
| Q4 | 设计 | 困难 | GCM 模式 | P2 |
| Q5 | 设计 | 刁钻 | Shadow reg | P2 |
| Q6 | 验证 | 常用 | 握手时序 | P1 |
| Q7 | 验证 | 常用 | 计数器进位 | P1 |
| Q8 | 验证 | 困难 | 时钟域 | P2 |
| Q9 | 验证 | 刁钻 | 强制清除 | P3 |
| Q10 | 架构 | 常用 | keymgr 接口 | P1 |
| Q11 | 架构 | 常用 | LC 控制 | P1 |
| Q12 | 架构 | 困难 | alert 传播 | P2 |
| Q13 | 架构 | 刁钻 | 多 slice 进位 | P3 |
| Q14 | 时序 | 常用 | S-Box 延迟 | P1 |
| Q15 | 时序 | 常用 | PRNG 时序 | P1 |
| Q16 | 时序 | 困难 | 密钥扩展周期 | P2 |
| Q17 | 时序 | 刁钻 | masking 同步 | P3 |
| Q18 | 面积 | 常用 | S-Box 面积 | P1 |
| Q19 | 面积 | 困难 | 复用优化 | P2 |
| Q20 | 面积 | 刁钻 | 清除逻辑面积 | P3 |

---

## 下一步

1. 对每个问题，编写 `golden_<question_id>.md`
2. 手动推导答案（不看工具输出）
3. 使用 sv_query 验证
4. 记录一致/不一致

---

## 文档更新记录

| 日期 | 更新内容 |
|------|---------|
| 2026-05-14 | 初版创建，20 个问题 |