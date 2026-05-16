# OpenChip QA 测试问题记录

> 测试时间: 2026-05-16
> 测试工具: sv_query
> 测试项目: clacc/bs_mult (首个测试)

---

## 发现的问题

### Issue 7: 非ANSI端口声明未支持

**问题描述**:
sv_query 的 `get_port_declarations()` 无法识别非ANSI端口声明

**示例**:
```verilog
module bs_mult(clk, x, y, p, firstbit, lastbit);  // 非ANSI格式
    input clk;
    input x, y, firstbit, lastbit;
    output p;
```

**预期端口**: clk(输入), x(输入), y(输入), p(输出), firstbit(输入), lastbit(输入)
**实际结果**: 端口数为 0

**根因分析**:
- 非ANSI端口声明在 `module (...);` 括号内
- sv_query 的 `get_port_declarations()` 使用 `header.ports` (ANSI格式)
- 非ANSI格式使用 `NonAnsiPortList` 而非 `AnsiPortList`

**相关代码**:
- `base.py: get_port_declarations()`
- `base.py: get_port_name_and_direction()`

**优先级**: P0 (影响基本功能)

**状态**: 待修复

---

### Issue 8: 端口位宽提取 ✅ 已支持

**问题描述**:
sv_query 的 `extract_port_width()` 已经支持端口位宽提取

**测试结果**:
```
wr_data_i: [DATA_WIDTH-1] -> [15:0] (input) ✅
rd_data_o: [DATA_WIDTH-1] -> [15:0] (output) ✅
clk: (1-bit) ✅
```

**功能**:
- `extract_port_width(port, module)` 返回 dict
- `msb_raw`: 原始表达式
- `msb_eval`: 求值结果
- `msb_is_param`: 是否参数化

**优先级**: N/A - 功能已存在且正常

**状态**: ✅ 已验证

---

## 功能覆盖度分析 (clacc/bs_mult)

| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 bs_mult |
| 实例解析 | ✅ | 正确找到 31 个 bs_mult_slice |
| 参数提取 | ✅ | 无参数时正确返回空列表 |
| 端口解析 | ❌ | 非ANSI端口声明未支持 |
| 位宽解析 | - | 未测试 |
| 连接追踪 | - | 未测试 |

---

## clacc/dual_clock_fifo 测试结果

**测试结果**:
- 模块数: 1 (dual_clock_fifo) ✅
- 参数数: 2 (ADDR_WIDTH=3, DATA_WIDTH=16) ✅
- 端口数: 10 ✅
- 实例数: 0 (无子模块实例)

**端口列表**:
```
wr_rst_i: input
wr_clk_i: input
wr_en_i: input
wr_data_i: input (16-bit)
rd_rst_i: input
rd_clk_i: input
rd_en_i: input
rd_data_o: output (16-bit)
full_o: output
empty_o: output
```

**问题回答**:
- Q1: gray_conv 函数 → sv_query 无法直接提取函数定义，需阅读源码
- Q2-Q14: 需分析源码回答

**功能覆盖度**:
| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | |
| 参数提取 | ✅ | ADDR_WIDTH, DATA_WIDTH |
| 端口解析 | ✅ | ANSI格式端口 |
| 实例解析 | N/A | 无子模块 |
| 位宽解析 | ⚠️ | DATA_WIDTH=16 参数未展开 |

**观察**:
- 参数引用求值正常 (DATA_WIDTH-1 → 15) ✅

---

## 待测试项目

1. [ ] clacc/bs_mult - 继续测试剩余问题
2. [ ] clacc/dual_clock_fifo
3. [ ] clacc/mult_pipe2
4. [ ] clacc/pe
5. [ ] serv
6. [ ] cva6
7. [ ] nvdla
8. [ ] opentitan
9. [ ] picorv32
10. [ ] tiny-gpu
11. [ ] verilog-axi
12. [ ] verilog-ethernet
13. [ ] vortex
14. [ ] zipcpu
15. [ ] darkriscv

---

## 后续行动

1. 修复 Issue 7: 非ANSI端口声明支持
2. 测试 Issue 8: 端口位宽提取
3. 继续下一个项目测试
4. 定期汇总发现的问题

---

## 备注

- 非ANSI端口声明是 Verilog-1995 风格，现在更多使用 SystemVerilog ANSI 格式
- 但 clacc 项目中大量使用非ANSI格式，需要兼容
---

## clacc/mult_pipe2 测试结果

**测试结果**:
- 模块数: 1 (mult_pipe2) ✅
- 参数数: 2 (SIZE=16, LVL=2) ✅
- 端口数: 0 ❌ (非ANSI端口声明)
- 实例数: 0 (无子模块)

**端口列表格式**: `( a, b, clk, pdt) ;` - 非ANSI声明

**问题回答**:
- Q1: SIZE/LVL 参数 → sv_query 正确提取参数 ✅
- Q2: 输出延迟 → 需分析源码 (延迟 = LVL cycles)
- Q3-Q12: 需分析源码回答

**功能覆盖度**:
| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | |
| 参数提取 | ✅ | SIZE=16, LVL=2 |
| 端口解析 | ❌ | 非ANSI端口声明 |
| 位宽解析 | - | 未测试 |
| 实例解析 | N/A | 无子模块 |

**备注**: 与 bs_mult 相同问题，非ANSI端口声明不支持


---

## clacc/pe 测试结果

**测试结果**:
- 模块数: 1 (pe) ✅
- 参数数: 0 ✅
- 端口数: 0 ❌ (非ANSI端口声明)
- 实例数: 6 ✅

**实例列表**:
```
I0: dual_clock_fifo
I1: ifmap_spad
I2: dual_clock_fifo (/* psum */)
I3: psum_spad
I4: dual_clock_fifo (/* filter kernel IO */)
I5: filt_spad
```

**发现**:
- clacc 反格式实例声明: `I0 dual_clock_fifo` (instance_name module_type)
- sv_query 能识别实例类型，但名称解析有混淆

**功能覆盖度**:
| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | pe |
| 参数提取 | ✅ | 无参数 |
| 端口解析 | ❌ | 非ANSI端口声明 |
| 实例解析 | ⚠️ | 识别6个实例，但type/name混淆 |
| 位宽解析 | - | 未测试 |


---

## serv/serv_decode 测试结果

**测试结果**:
- 模块数: 1 (serv_decode) ✅
- 参数数: 2 (PRE_REGISTER=1, MDU=0) ✅
- 端口数: 47 ✅ (ANSI格式!)
- 实例数: 0 (无子模块)

**端口列表 (前20个)**:
```
clk: input
i_wb_rdt: input
i_wb_en: input
o_sh_right: output
o_bne_or_bge: output
o_cond_branch: output
o_e_op: output
o_ebreak: output
o_branch_op: output
o_shift_op: output
o_rd_op: output
o_two_stage_op: output
o_dbus_en: output
o_mdu_op: output
o_ext_funct3: output
...
还有 27 个端口
```

**问题回答**:
- Q1: 指令分解 → sv_query 无法直接提取，但可分析端口推断
- Q2-QN: 需分析源码回答

**功能覆盖度**:
| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | serv_decode |
| 参数提取 | ✅ | PRE_REGISTER, MDU |
| 端口解析 | ✅ | ANSI格式，47个端口 |
| 实例解析 | N/A | 无子模块 |
| 位宽解析 | ⚠️ | i_wb_rdt[31:2] 位宽未展开 |

**观察**:
- serv 使用 ANSI 端口声明，比 clacc 更标准
- 47 个端口说明这是复杂的译码器


---

## serv/serv_alu 测试结果

**测试结果**:
- 模块数: 1 (serv_alu) ✅
- 参数数: 2 (W=1, B=W-1) ✅ - 注意 B 引用 W!
- 端口数: 13 ✅ (ANSI格式)
- 实例数: 0 (无子模块)

**参数分析**:
```
W = 1
B = W-1 = 0 (参数引用!)
```

**问题回答**:
- Q1: ALU 参数化 → W=1 表示位宽，B=W-1 是参数引用
- Q2-QN: 需分析源码

**功能覆盖度**:
| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | serv_alu |
| 参数提取 | ✅ | W=1, B=W-1 |
| 参数引用 | ⚠️ | B=W-1 需要递归解析 |
| 端口解析 | ✅ | ANSI格式 |
| 位宽解析 | - | 未测试 |

**观察**:
- 这是第一个测试到参数引用参数的模块
- sv_query 的 get_module_parameters 返回 {'name': 'B', 'value': 'W-1'} 字符串
- 需要 Issue 9 修复后参数引用才能正确求值


---

## serv/serv_top 测试结果

**测试结果**:
- 模块数: 1 (serv_top) ✅
- 参数数: 10 ✅ - 复杂参数化
- 端口数: 33 ✅ (ANSI格式)
- 实例数: 9 ✅

**参数列表**:
```
WITH_CSR=1, W=1, B=W-1, PRE_REGISTER=1, RESET_STRATEGY=MINI,
RESET_PC=0, DEBUG=0, MDU=0, COMPRESSED=0, ALIGN=COMPRESSED
```

**实例列表**:
```
state, decode, immdec, bufreg, bufreg2, ctrl, alu, rf_if, mem_if
```

**功能覆盖度**:
| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | serv_top |
| 参数提取 | ✅ | 10个参数，包含引用 |
| 端口解析 | ✅ | 33个端口 |
| 实例解析 | ✅ | 9个子模块 |
| 位宽解析 | - | 未测试 |

**观察**:
- serv_top 是 serv 的顶层模块，包含完整的 RISC-V 处理器
- 9 个子模块实例：state, decode, immdec, bufreg, bufreg2, ctrl, alu, rf_if, mem_if
- 参数包含复杂引用：W=1, B=W-1, ALIGN=COMPRESSED


---

## cva6 测试结果

**已测试模块**:

### decoder.sv
- 模块数: 1 (decoder) ✅
- 参数数: 2 (CVA6Cfg, INTERRUPTS) ✅
- 端口数: 37 ✅
- 实例数: 0

### cva6.sv (顶层)
- 模块数: 1 (cva6) ✅
- 参数数: 2 (CVA6Cfg, AccCfg) ✅
- 端口数: 13 ✅
- 实例数: 10 ✅

**实例列表 (部分)**:
```
i_frontend, id_stage_i, issue_stage_i, ex_stage_i, ...
```

**功能覆盖度**:
| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | cva6, decoder |
| 参数提取 | ✅ | 复杂参数 (build_config) |
| 端口解析 | ✅ | 37端口 decoder |
| 实例解析 | ⚠️ | 10实例，注释干扰 |

**观察**:
- cva6 是大模块，参数使用复杂的嵌套配置 (build_config_pkg)
- 注释干扰实例名称解析 (Issue 2 相关)
- SystemVerilog 使用率高 (`.sv` 文件)


---

## nvdla 测试结果

**已测试模块**:

### NV_nvdla.v (顶层)
- 模块数: 1 (NV_nvdla) ✅
- 参数数: 0
- 端口数: 0 ❌ (非ANSI格式)
- 实例数: 6 ✅

### NV_NVDLA_bdma.v
- 模块数: 1 (NV_NVDLA_bdma) ✅
- 参数数: 0
- 端口数: 0 ❌ (非ANSI格式)
- 实例数: 5 ✅

**端口格式分析**:
```verilog
module NV_NVDLA_bdma (
   bdma2cvif_rd_req_ready        //|< i
  ,bdma2cvif_wr_req_ready        //|< i
  ...
  ,bdma2csb_resp_pd              //|> o
```

NVDLA 使用非ANSI端口声明，且方向用注释表示 (`//|< i` = input, `//|> o` = output)

**功能覆盖度**:
| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | |
| 参数提取 | ✅ | 无参数 |
| 端口解析 | ❌ | 非ANSI+注释格式 |
| 实例解析 | ✅ | |


---



---

## Issue 11: 逗号分隔的多个端口方向缺失

**问题描述**:
当多个端口用逗号分隔且共用一个方向关键字时 (`input clk, resetn`)，只有第一个端口有方向，后续端口方向为 unknown

**示例**:
```verilog
input clk, resetn  // clk 有方向，resetn 没有
```

**原因分析**:
- pyslang 将 `input clk, resetn` 解析为两个 ImplicitAnsiPort
- 第一个有 direction header，第二个没有
- 第二个应该继承第一个的方向，但当前代码未处理

**影响**:
- picorv32 的 resetn 端口方向显示为 unknown

**优先级**: P2 (低优先级边缘情况)

**状态**: 已知限制

## picorv32 测试结果

**文件**: picorv32.v (包含 8 个模块!)

### 模块列表

| 模块 | 参数 | 端口 | 实例 |
|------|------|------|------|
| picorv32 | 26 | 27 | 3 |
| picorv32_regs | 0 | 8 | 3 |
| picorv32_pcpi_mul | 2 | 10 | 3 |
| picorv32_pcpi_fast_mul | 3 | 10 | 3 |
| picorv32_pcpi_div | 0 | 10 | 3 |
| picorv32_axi | 25 | 32 | 3 |
| picorv32_axi_adapter | 0 | 26 | 3 |
| picorv32_wb | 25 | 24 | 3 |

**picorv32 (主模块) 参数**:
```
ENABLE_COUNTERS=1, ENABLE_COUNTERS64=1, ENABLE_REGS_16_31=1,
ENABLE_REGS_DUALPORT=1, LATCHED_MEM_RDATA=0, TWO_STAGE_SHIFT=1,
BARREL_SHIFTER=0, TWO_CYCLE_COMPARE=0, TWO_CYCLE_ALU=0,
COMPRESSED_ISA=0, ...
```

**picorv32 (主模块) 端口 (前15个)**:
```
clk: input, resetn: unknown, trap: output, mem_valid: output,
mem_instr: output, mem_ready: input, mem_addr: output,
mem_wdata: output, mem_wstrb: output, ...
```

**发现问题**:
- 端口方向有 `unknown` (resetn 应该是什么方向?)

**功能覆盖度**:
| 功能 | 支持 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 8个模块全部识别 |
| 参数提取 | ✅ | 26个参数 |
| 端口解析 | ⚠️ | 27端口，但有unknown |
| 实例解析 | ✅ | 3个实例 |

