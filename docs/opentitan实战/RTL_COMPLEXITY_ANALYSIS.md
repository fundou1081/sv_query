# OpenTitan RTL 复杂度分级与 sv_query 验证计划

> 探索日期: 2026-05-14
> 目的: 为 sv_query 项目建立真实场景的质量验证基准

---

## 探索方法

在 OpenTitan RTL 代码库 (`~/my_dv_proj/opentitan/`) 中按代码行数排序，找出不同复杂度的设计模块：

```bash
# 统计各 IP 的 RTL 代码行数
for ip in hw/ip/*/rtl; do
  total=$(find $ip -name '*.sv' -exec wc -l {} \; 2>/dev/null | awk '{sum+=$1} END {print sum}')
  echo "$total $(basename $(dirname $ip))"
done | sort -n
```

**结果排名（RTL 代码行数）**：

| IP | RTL 行数 | 复杂度评估 |
|----|----------|-----------|
| adc_ctrl | ~5,600 | 简单 |
| lc_ctrl | ~5,600 | 简单 |
| keymgr_dpe | ~5,900 | 简单 |
| i2c | ~8,900 | 中等偏小 |
| kmac | ~12,100 | 中等 |
| aes | ~17,200 | 中等偏大 |
| otbn | ~14,700 | 复杂 |
| prim | ~25,100 | 基础库 |
| spi_device | ~32,100 | 复杂 |

---

## 复杂度分级

### 简单设计：adc_ctrl

**路径**: `hw/ip/adc_ctrl/rtl/`

**文件列表** (7 文件):
- `adc_ctrl.sv` - 主模块入口
- `adc_ctrl_core.sv` - DCD 核心逻辑
- `adc_ctrl_fsm.sv` - 状态机
- `adc_ctrl_intr.sv` - 中断处理
- `adc_ctrl_pkg.sv` - 包定义
- `adc_ctrl_reg_pkg.sv` - 寄存器包
- `adc_ctrl_reg_top.sv` - 寄存器顶层

**特点**:
- FSM 驱动 ADC 采样序列
- 单一时钟域 (clk_aon_i)
- 模块职责清晰，接口简单

**适合场景**: 快速功能验证，但不适合展现 sv_query 追踪能力

---

### 中等复杂度：AES

**路径**: `hw/ip/aes/rtl/`

**文件列表** (40+ 文件):
- `aes_core.sv` - 核心主体 (~600 行)
- `aes_cipher_core.sv` - 加密核心
- `aes_control.sv` / `aes_control_fsm.sv` - 控制 FSM
- `aes_key_expand.sv` - 密钥扩展
- `aes_sbox.sv` - S-Box 实现 (多版本)
- `aes_ctr.sv` / `aes_ctr_fsm.sv` - CTR 模式
- `aes_ghash.sv` - GCM 模式
- `aes_prng_*.sv` - 随机数生成
- ...等

**特点**:
- 多路选择器控制数据流：`state_in_sel`、`key_init_sel`、`iv_sel`
- 多时钟/复位域
- 共享复用逻辑 (MixColumns, ShiftRows, SubBytes)
- 密钥扩展多阶段

**信号示例**:
```systemverilog
logic [3:0][3:0][7:0] state_in;
logic [3:0][3:0][7:0] state_out;
logic [NumRegsKey-1:0][31:0] key_init [NumSharesKey];
```

**适合场景**:
- 跨模块 driver 追踪（key -> state -> output）
- 条件驱动分析（cipher_op 控制数据路径）
- 多驱动源场景

---

### 复杂设计：OTBN

**路径**: `hw/ip/otbn/rtl/`

**文件列表** (30+ 文件):
- `otbn.sv` - 主模块入口
- `otbn_core.sv` - 处理器核主体
- `otbn_controller.sv` - 控制器
- `otbn_decoder.sv` - 指令译码器
- `otbn_alu_base.sv` / `otbn_alu_bignum.sv` - ALU
- `otbn_lsu.sv` - Load/Store 单元
- `otbn_rf_base.sv` / `otbn_rf_bignum.sv` - 寄存器文件
- `otbn_mac_bignum.sv` - 乘法累加器
- `otbn_vec_*.sv` - 向量操作单元
- ...等

**特点**:
- 完整处理器核架构
- 多单元数据交互
- 复杂的状态控制
- 向量执行单元

**适合场景**:
- 多驱动源分析（同一寄存器被不同单元驱动）
- 深层次模块间信号追踪
- 复杂数据依赖图

---

## sv_query 验证计划

### 验证目标

使用 OpenTitan RTL 作为真实场景，验证 sv_query 的以下能力：

1. **Driver 追踪准确性**: 给定信号，找到所有驱动它的源
2. **跨模块边界追踪**: 信号穿过实例端口时的追踪
3. **条件驱动识别**: case/mux 选择逻辑下的实际驱动源
4. **多驱动源分析**: 同一信号被多个源驱动的情况

### 推荐验证顺序

| 顺序 | 模块 | 理由 |
|------|------|------|
| **1** | AES | 规模适中、数据流清晰、多路选择 |
| **2** | OTBN | 复杂但架构清晰、深度测试 |
| **3** | kmac | 中等复杂度、Keccak 轮函数 |
| **4** | adc_ctrl | 简单场景、快速回归 |

### AES 验证具体场景

**场景 1**: 追踪 `state_out` 的 driver
```
预期: state_out 由 state_done 多路选择得到
路径: key_init -> state_init -> state_done -> state_out
```

**场景 2**: 分析 `cipher_op` 控制的数据路径
```
预期: cipher_op = AES_ENC/AES_DEC 控制 SubBytes/MixColumns 选择
```

**场景 3**: 密钥扩展状态追踪
```
预期: key_init_q[KeyLen] -> key_init_cipher[NumShares] -> state_init
```

### OTBN 验证具体场景

**场景 1**: 追踪 `otbn.ALU` 结果写回寄存器文件
```
预期: otbn_core -> otbn_alu_base -> otbn_rf_base
```

**场景 2**: LSU 数据加载追踪
```
预期: otbn_controller -> otbn_lsu -> otbn_rf_base
```

---

## 验收标准

### 简单设计 (adc_ctrl)

- [ ] 能追踪到 `adc_ctrl_fsm` 对 `adc_o` 的驱动
- [ ] 能识别 `intr_match_pending_o` 的所有驱动源

### 中等设计 (AES)

- [ ] 追踪 `state_out` 能显示完整的 key -> state -> output 路径
- [ ] 识别 `cipher_op` 控制的多路选择器
- [ ] 能追踪密钥扩展多阶段数据流

### 复杂设计 (OTBN)

- [ ] 追踪 `rf_base.wr_data` 能显示所有写入源
- [ ] 能处理多单元同时驱动的场景
- [ ] 能追踪向量单元与标量单元的数据交换

---

## 文档更新记录

| 日期 | 更新内容 |
|------|---------|
| 2026-05-14 | 初版创建 |