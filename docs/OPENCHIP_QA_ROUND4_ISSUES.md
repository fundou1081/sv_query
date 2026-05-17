# OpenChip QA Round 4 - 问题汇总

**测试时间**: 2026-05-17
**测试项目**: clacc/bs_mult

---

## 问题状态总结

| Issue | 问题 | 状态 | 说明 |
|-------|------|------|------|
| Issue 17 | 非ANSI端口位宽丢失 | ✅ 已记录 | 源代码问题，非 sv_query bug |
| Issue 18 | LOAD 边统计为 0 | ✅ 已确认 | 设计约束，保持现状 |
| Issue 19 | 实例节点前缀 "top" | ✅ 已修复 | 动态获取根模块名 |
| Issue 20 | 边数只有 3 | ✅ 已修复 | 添加缺少文件警告 |

---

## Issue 17: 非ANSI端口位宽丢失

### 案例: bs_mult.v 的 output p

**问题**: `p: output` 位宽丢失，应为 `output [29:0]`

**根因**: bs_mult.v 源代码不符合 SV 标准

```verilog
// 实际代码 (有问题)
output p;         // ❌ 缺少位宽声明

// 标准写法
output [29:0] p;   // ✅ 有位宽声明
```

**结论**: 这是源代码问题，非 sv_query bug。sv_query 正确识别了 `p` 是 output 端口，但无法提取位宽因为源代码没有声明。

**文档**: `docs/ISSUE_17_CASE_BS_MULT.md`

---

## Issue 18: LOAD 边统计为 0

### 问题

```
实际: DRIVER: 3, LOAD: 0, 总边数: 3
期望: 应该有实例端口连接边
```

### 根因

| 项目 | 说明 |
|------|------|
| **为什么 unknown** | bs_mult_slice.v 未解析，端口方向无从得知 |
| **为什么不创建边** | 代码逻辑：unknown 方向跳过边创建 |
| **影响** | 31 个实例 × 10 个端口 = 310 个连接跳过 |

### 解决方案

**保持现状** - 设计约束，正确性优先。

当模块未解析时：
- 端口方向 → 'unknown'
- 跳过边创建
- 输出警告 (Issue 20)

**文档**: `docs/ISSUE_18_CONCLUSION.md`

---

## Issue 19: 实例节点前缀错误 "top" ✅

### 问题

```
实际: top.I0.clk, top.I0.pout, ...
期望: bs_mult.I0.clk, bs_mult.I0.pout, ...
```

### 修复内容

1. 在 `ConnectionExtractor.__init__` 添加 `self.root_module_name = None`
2. 在 `extract()` 开始时动态获取第一个模块名
3. 将所有硬编码的 `"top."` 替换为 `f"{self.root_module_name}."`

### 验证结果

```
修复前: top.I0.clk (371 个), bs_mult.* (8 个)
修复后: bs_mult.I0.clk (379 个), top.* (0 个)
```

### Commit

`94ad7fa fix: Issue 19 - 动态获取根模块名而非硬编码 top`

---

## Issue 20: 边数只有 3

### 问题

当只解析 bs_mult.v 时：
- 总边数: 3 (只有 assign 语句的 DRIVER 边)
- 缺少实例端口连接边

### 修复内容

添加 `_missing_module_warning` 方法，当检测到实例但无端口定义时输出警告：

```
[sv_query] 可能缺少文件: 实例 'I0' 的模块 'bs_mult_slice' 没有找到端口定义。
  → 可能原因: 解析的文件范围不完整，缺少 'bs_mult_slice' 的定义文件
  → 建议: 确保传入所有相关的 Verilog 文件
```

### Commit

`f2b1647 fix: Issue 20 - 添加可能缺少文件的警告提示`

---

## Round 4 最终结论

### 问题分类

| 类型 | 数量 | 说明 |
|------|------|------|
| ✅ 已修复 | 2 | Issue 19, Issue 20 |
| ✅ 已记录为非bug | 2 | Issue 17 (源代码问题), Issue 18 (设计约束) |

### 学到的东西

1. **解析范围很重要**: sv_query 需要解析所有相关文件才能获取完整信息
2. **正确性优先**: 不创建错误边比创建边更重要
3. **警告友好**: 明确提示可能的问题比静默失败更好
4. **源代码质量**: 不符合标准的代码会导致工具无法正确解析

---

## Commits

| Commit | 说明 |
|--------|------|
| `94ad7fa` | fix: Issue 19 - 动态获取根模块名 |
| `f2b1647` | fix: Issue 20 - 添加缺少文件警告 |
| `858d9cb` | docs: Issue 17 - 记录源代码问题 |
| `dd8cc0f` | docs: Issue 18 - 根因分析 |
| `502ed76` | docs: Issue 18 - 结论: 保持现状 |
---

## dual_clock_fifo 模块测试结果

**测试时间**: 2026-05-17
**文件**: `/Users/fundou/my_dv_proj/clacc/dual_clock_fifo.v`

---

### 模块信息

| 项目 | 值 |
|------|-----|
| 模块名 | dual_clock_fifo |
| 参数 | ADDR_WIDTH=3, DATA_WIDTH=16 |
| 端口 | 10 个 (4 input, 2 output, 4 bidirectional input) |
| 实例数 | 0 (无子模块实例) |

### 端口详情

| 端口 | 方向 | 位宽 | 说明 |
|------|------|------|------|
| wr_rst_i | input | - | 写复位 |
| wr_clk_i | input | - | 写时钟 |
| wr_en_i | input | - | 写使能 |
| wr_data_i | input | [15:0] | 写数据 |
| rd_rst_i | input | - | 读复位 |
| rd_clk_i | input | - | 读时钟 |
| rd_en_i | input | - | 读使能 |
| rd_data_o | output | [15:0] | 读数据 |
| full_o | output | - | 满标志 |
| empty_o | output | - | 空标志 |

---

### 边类型统计

| 边类型 | 数量 | 说明 |
|--------|------|------|
| DRIVER | 23 | 数据驱动边 |
| BIT_SELECT | 5 | 位选择边 |
| **总计** | **28** | |

---

### 发现的问题

#### Issue 21: 参数表达式未展开

**现象**:
```
节点名包含: dual_clock_fifo.in[ADDR_WIDTH-1]
期望: dual_clock_fifo.in[2] (因为 ADDR_WIDTH=3)
```

**根因**: 参数在节点名中使用但未被求值

**影响**: 节点名显示不直观，难以理解

**状态**: 待讨论解决方案

---

#### Issue 22: 函数节点被标记为 SIGNAL

**现象**:
```
gray_conv 函数被标记为 SIGNAL
应该被标记为 FUNCTION 或类似
```

**根因**: 函数定义没有特殊处理

**影响**: 函数和信号无法区分

**状态**: 待讨论解决方案

---

#### Issue 23: mem 存储访问缺少端口方向

**现象**:
```
驱动边:
  wr_data_i -> mem[wr_addr]  (写入)
  mem[rd_addr] -> rd_data_o  (读取)
```

**问题**: mem 是双端口 RAM，但只显示为单一的"mem[addr]"形式

**影响**: 无法区分读端口和写端口的方向

**状态**: 已观察，待讨论

---

### 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 dual_clock_fifo |
| 参数解析 | ✅ | ADDR_WIDTH=3, DATA_WIDTH=16 |
| 参数应用 | ⚠️ | 节点名中参数未展开 |
| 端口解析 | ✅ | 10 个端口正确识别 |
| 位宽解析 | ✅ | wr_data_i[15:0], rd_data_o[15:0] |
| 时钟域 | ✅ | wr_clk_i, rd_clk_i 识别 |
| 复位信号 | ✅ | wr_rst_i, rd_rst_i 识别 |
| 存储阵列 | ⚠️ | mem 存在但端口方向不清晰 |
| 函数 | ⚠️ | gray_conv 被标记为 SIGNAL |

---

### sv_query 能力评估

| 能力 | 评分 | 说明 |
|------|------|------|
| 模块解析 | ★★★★★ | 正确识别 |
| 参数解析 | ★★★★☆ | 解析但未应用 |
| 端口解析 | ★★★★★ | 全部正确 |
| CDC 分析 | ★☆☆☆☆ | 不支持 Gray 码识别 |
| 存储分析 | ★★★☆☆ | 能识别 mem 但不完整 |
| 函数分析 | ★★☆☆☆ | 函数被当作信号处理 |

---

### 下一步

1. **Issue 21**: 讨论参数展开方案
2. **Issue 22**: 讨论函数节点处理
3. **Issue 23**: 讨论存储阵列表示


---

## pe 模块测试结果

**测试时间**: 2026-05-17
**文件**: `/Users/fundou/my_dv_proj/clacc/pe.v`

---

### 模块信息

| 项目 | 值 |
|------|-----|
| 模块名 | pe |
| 参数 | 0 |
| 端口 | 6 个 |
| 实例数 | 6 个 (3 dual_clock_fifo, 3 SPAD) |

### 端口详情

| 端口 | 方向 | 说明 |
|------|------|------|
| clk_noc | input | NoC 时钟 |
| clk_pe | input | PE 时钟 |
| ifmap | input | 输入特征图 |
| filt | input | 卷积核 |
| input_psum | input | 输入部分和 |
| out_psum | output | 输出部分和 |

---

### 实例详情

| 实例名 | 模块类型 | 连接数 | 说明 |
|--------|----------|--------|------|
| I0 | dual_clock_fifo | 4 | ifmap FIFO |
| I1 | ifmap_spad | 1 | ifmap 存储 |
| I2 | dual_clock_fifo | 4 | psum FIFO |
| I3 | psum_spad | 1 | psum 存储 |
| I4 | dual_clock_fifo | 3 | filter FIFO (部分连接) |
| I5 | filt_spad | 1 | filter 存储 |

---

### 发现的问题

#### Issue 24: pe 模块无连接边

**现象**:
```
节点数: 18
边数: 0      ← 应该有连接边
```

**根因**: pe.v 只解析了自身，SPAD 模块 (ifmap_spad, psum_spad, filt_spad) 未解析

**影响**: 无法追踪 SPAD 存储的读写关系

**状态**: 设计约束 (解析范围问题)

---

#### Issue 25: clacc 反格式实例名

**现象**:
```python
# 原始 instance.type.value
type_val = 'I0'  # 这是实例名，不是模块类型

# adapter 正确处理后
module_type = 'dual_clock_fifo'  # 正确的模块类型
```

**问题**: pe.v 使用 clacc 反格式 `I0 dual_clock_fifo`，instance.type 存储实例名，decl.name 存储模块类型

**解决方案**: adapter 已正确处理，使用 `get_instance_module_type()` 获取模块类型

**状态**: ✅ 已解决 (adapter 正确处理)

---

#### Issue 26: SPAD 连接信息不完整

**现象**:
```
SPAD 连接:
  ifmap_spad: 1 连接 (只有 clk)
  psum_spad: 1 连接 (只有 clk)
  filt_spad: 1 连接 (只有 clk)
```

**问题**: SPAD 的 addr, we, data_port 连接未解析

**根因**: SPAD 模块未解析，无法获取端口定义

**状态**: 设计约束

---

### 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 pe |
| 端口解析 | ✅ | 6 个端口正确 |
| 实例识别 | ✅ | 6 个实例正确 (adapter 正确处理) |
| 实例名称 | ✅ | 使用 get_instance_name() |
| 模块类型 | ✅ | 使用 get_instance_module_type() |
| 连接追踪 | ⚠️ | 无边，因 SPAD 未解析 |

---

### sv_query 能力评估

| 能力 | 评分 | 说明 |
|------|------|------|
| 实例解析 | ★★★★☆ | adapter 正确处理反格式 |
| 连接追踪 | ★★☆☆☆ | 需要解析所有子模块 |
| 层次分析 | ★★★☆☆ | 能识别 I0-I5 但无法建立连接 |

---

### 后续观察

1. clacc 格式实例名是 I0, I1, I2... 而不是标准格式
2. clacc 使用反格式: `instance_name module_type`
3. adapter 已正确处理，但用户需要使用正确的方法


---

## mult_pipe2 模块测试结果

**测试时间**: 2026-05-17
**文件**: `/Users/fundou/my_dv_proj/clacc/mult_pipe2.v`

---

### 模块信息

| 项目 | 值 |
|------|-----|
| 模块名 | mult_pipe2 |
| 参数 | SIZE=16, LVL=2 |
| 端口 | 4 个 |
| 实例数 | 0 |

### 端口详情

| 端口 | 方向 | 位宽 | 说明 |
|------|------|------|------|
| a | input | [15:0] | 被乘数 |
| b | input | [15:0] | 乘数 |
| clk | input | - | 时钟 |
| pdt | output | [31:0] | 乘积 |

---

### 边类型统计

| 边类型 | 数量 |
|--------|------|
| DRIVER | 5 |
| BIT_SELECT | 4 |
| **总计** | **9** |

---

### 发现的问题

#### Issue 27: 参数在节点名中未展开

**现象**:
```
节点名: mult_pipe2.pdt_int [LVL-1]
期望:   mult_pipe2.pdt_int[1] (因为 LVL=2)
```

**根因**: 参数 LVL 在节点名中未求值

**影响**: 节点名不直观，需要用户自己计算

**状态**: 待讨论解决方案

---

#### Issue 28: 注释混入节点名

**现象**:
```
节点名: mult_pipe2.// registering input of the multiplier a_int
```

**问题**: 注释被当作节点名的一部分

**影响**: 节点名混乱，难以理解

**状态**: 待讨论

---

### 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 mult_pipe2 |
| 参数解析 | ✅ | SIZE=16, LVL=2 |
| 参数应用 | ⚠️ | 节点名中参数未展开 |
| 端口解析 | ✅ | 位宽正确 [15:0], [31:0] |
| 连接追踪 | ✅ | 9 条边正确追踪 |

---

### sv_query 能力评估

| 能力 | 评分 | 说明 |
|------|------|------|
| 参数解析 | ★★★★☆ | 正确解析但未应用 |
| 位宽处理 | ★★★★★ | 正确识别 [15:0], [31:0] |
| 连接追踪 | ★★★★☆ | 基本功能正常 |
| 注释处理 | ★☆☆☆☆ | 注释混入节点名 |

---

### 后续观察

1. mult_pipe2 使用参数化位宽，输出 `pdt = [2*SIZE-1:0] = [31:0]`
2. 流水线寄存器 `pdt_int[LVL-1:0]` 数组
3. 参数在节点名中未展开，需要求值


---

## cva6 模块测试结果

**测试时间**: 2026-05-17
**文件**: `/Users/fundou/my_dv_proj/cva6/core/cva6.sv`

---

### 模块信息

| 项目 | 值 |
|------|-----|
| 模块名 | cva6 |
| 参数 | 2 (CVA6Cfg, ASID_WIDTH) |
| 端口 | 13 个 |
| 实例数 | 10 个 |
| 总节点数 | 781 |
| 总边数 | 191 |

### 端口详情

| 端口 | 方向 | 说明 |
|------|------|------|
| clk_i | input | 时钟 |
| rst_ni | input | 复位 (低有效) |
| boot_addr_i | input | 启动地址 |
| hart_id_i | input | Hart ID |
| irq_i | input [1:0] | 中断请求 |
| ipi_i | input | 间处理器中断 |
| time_irq_i | input | 定时器中断 |
| debug_req_i | input | 调试请求 |
| rvfi_probes_o | output | RVFI 探针 |
| cvxif_req_o | output | CV-XIF 请求 |
| cvxif_resp_i | input | CV-XIF 响应 |
| noc_req_o | output | NoC 请求 |
| noc_resp_i | input | NoC 响应 |

---

### 实例详情

| 实例 | 模块类型 | 说明 |
|------|----------|------|
| i_frontend | frontend | 取指单元 |
| i_id_stage | id_stage | 译码级 |
| i_issue_stage | issue_stage | 发射级 |
| i_ex_stage | ex_stage | 执行级 |
| i_commit_stage | commit_stage | 提交级 |
| i_csr_regfile | csr_regfile | CSR 寄存器文件 |
| i_controller | controller | 控制器 |
| i_std_cache_subsystem | std_cache_subsystem | 缓存子系统 |
| i_instr_tracer | instr_tracer | 指令追踪器 |
| i_cva6_rvfi_probes | cva6_rvfi_probes | RVFI 探针 |

---

### 边类型统计

| 边类型 | 数量 | 说明 |
|--------|------|------|
| DRIVER | 131 | 数据驱动边 |
| BIT_SELECT | 60 | 位选择边 |
| **总计** | **191** | |

**注意**: 没有 CONNECTION 边，说明子模块 (frontend, id_stage 等) 未解析

---

### 发现的问题

#### Issue 29: 参数表达式未展开 (CVA6Cfg)

**现象**:
```
节点名: cva6.trans_id_ex_id[CVA6Cfg.TRANS_ID_BITS-1:0]
期望:   cva6.trans_id_ex_id[6:0] (如果 TRANS_ID_BITS=7)
```

**问题**: CVA6Cfg 是复杂参数对象，节点名中完全保留

**影响**: 节点名不直观，难以理解

**状态**: 待讨论

---

#### Issue 30: 子模块未解析导致无 CONNECTION 边

**现象**:
```
边类型统计:
  DRIVER: 131
  BIT_SELECT: 60
  CONNECTION: 0    ← 期望有连接边
```

**根因**: cva6.sv 只解析了自身，子模块 (frontend, id_stage 等) 在其他文件

**影响**: 无法追踪实例端口连接

**状态**: 设计约束

---

#### Issue 31: 位宽 (0,0) 问题

**现象**:
```
节点: cva6.clk_i PORT_IN (0,0)
节点: cva6.rst_ni PORT_IN (0,0)
节点: cva6.irq_i PORT_IN (1,0)
```

**问题**: 大部分端口位宽为 (0,0)，部分为 (1,0)

**分析**: 
- (0,0) 表示未识别位宽
- (1,0) 表示 1-bit
- 应该有 [N:0] 格式的位宽

**状态**: 待讨论

---

### 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 cva6 |
| 参数解析 | ⚠️ | 2 个参数但未应用 |
| 端口解析 | ⚠️ | 13 个端口，位宽不完整 |
| 实例识别 | ✅ | 10 个实例正确识别 |
| 实例命名 | ✅ | 使用 i_ 前缀格式 |
| 连接追踪 | ⚠️ | 无 CONNECTION 边 |

---

### sv_query 能力评估

| 能力 | 评分 | 说明 |
|------|------|------|
| 大型 SoC 解析 | ★★★★☆ | 781 节点，191 边 |
| 层次结构 | ★★★☆☆ | 识别子模块但无法追踪连接 |
| 参数处理 | ★★☆☆☆ | CVA6Cfg 过于复杂 |
| 时钟域识别 | ★★★☆☆ | 能识别 clk_i, rst_ni |

---

### 后续观察

1. CVA6 是复杂的多模块 SoC
2. 实例命名使用 `i_` 前缀 (i_frontend, i_id_stage 等)
3. 参数 CVA6Cfg 是配置对象，包含多个子参数
4. 子模块分布在其他文件中


---

## serv_top 模块测试结果

**测试时间**: 2026-05-17
**文件**: `/Users/fundou/my_dv_proj/serv/rtl/serv_top.v`

---

### 模块信息

| 项目 | 值 |
|------|-----|
| 模块名 | serv_top |
| 参数 | 10 个 (WITH_CSR, W, B, PRE_REGISTER 等) |
| 端口 | 33 个 |
| 实例数 | 9 个 |
| 总节点数 | 342 |
| 总边数 | 20 |

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| WITH_CSR | 1 | 是否包含 CSR |
| W | 1 | 位宽参数 |
| B | W-1 | 位宽计算 |
| PRE_REGISTER | 1 | 预寄存器 |
| RESET_STRATEGY | MINI | 复位策略 |
| RESET_PC | 0 | 复位地址 |

---

### 实例详情

| 实例名 | 模块类型 | 连接数 | 说明 |
|--------|----------|--------|------|
| state | serv_state | 46 | 状态机 |
| decode | serv_decode | 47 | 译码器 |
| immdec | serv_immdec | 13 | 立即数译码 |
| bufreg | serv_bufreg | 20 | 缓冲寄存器 |
| bufreg2 | serv_bufreg2 | 18 | 缓冲寄存器2 |
| ctrl | serv_ctrl | 18 | 控制器 |
| alu | serv_alu | 13 | ALU |
| rf_if | serv_rf_if | 35 | 寄存器文件接口 |
| mem_if | serv_mem_if | 11 | 存储器接口 |

---

### 边类型统计

| 边类型 | 数量 | 说明 |
|--------|------|------|
| DRIVER | 20 | 数据驱动边 |
| CONNECTION | 0 | 无实例连接边 |
| **总计** | **20** | |

---

### 发现的问题

#### Issue 32: 实例端口节点存在但无连接边

**现象**:
```
实例端口节点: 282 个 (如 serv_top.state.i_clk)
但边数: 20 (全是 DRIVER，无 CONNECTION)

总节点数: 342
  ├── 顶层端口: 33
  ├── 实例: 13 (top-level instances)
  └── 实例端口: 282 (子模块端口)
```

**问题**: 实例端口节点被创建了，但连接到这些端口的边是 DRIVER 而不是 CONNECTION

**分析**: 可能是子模块 (serv_state 等) 未解析，端口方向未知

**状态**: 待调查

---

#### Issue 33: 字面量作为节点名

**现象**:
```
边: serv_top.0 -> serv_top.iscomp (DRIVER)
边: 1'b0 -> serv_top.csr_in (DRIVER)
```

**问题**: 字面量 `0` 和 `1'b0` 被当作节点名

**影响**: 节点名不直观

**状态**: 待讨论

---

### 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 serv_top |
| 参数解析 | ✅ | 10 个参数正确 |
| 参数应用 | ⚠️ | B=W-1 未展开为 0 |
| 端口解析 | ✅ | 33 个端口正确 |
| 实例识别 | ✅ | 9 个实例正确 |
| 连接追踪 | ⚠️ | 无 CONNECTION 边 |

---

### sv_query 能力评估

| 能力 | 评分 | 说明 |
|------|------|------|
| 处理器核解析 | ★★★★☆ | 342 节点，完整层次 |
| 参数解析 | ★★★★☆ | 10 个参数 |
| 实例识别 | ★★★★★ | 9 个子模块 |
| 连接追踪 | ★★☆☆☆ | 无 CONNECTION 边 |

---

### 后续观察

1. SERV 使用标准格式 `module instance_name (connections)`
2. 实例命名: state, decode, immdec, ctrl, alu 等
3. 子模块在 `serv/` 目录的其他文件中
4. 子模块未解析导致无 CONNECTION 边


---

## gpu (Tiny GPU) 模块测试结果

**测试时间**: 2026-05-17
**文件**: `/Users/fundou/my_dv_proj/tiny-gpu/src/gpu.sv`

---

### 模块信息

| 项目 | 值 |
|------|-----|
| 模块名 | gpu |
| 参数 | 8 个 |
| 端口 | 18 个 |
| 实例数 | 5 个 (dcr, controller × 2, dispatch, cores) |
| 总节点数 | 126 |
| 总边数 | 24 |

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| DATA_MEM_ADDR_BITS | 8 | 数据内存地址位宽 |
| DATA_MEM_DATA_BITS | 8 | 数据内存数据位宽 |
| DATA_MEM_NUM_CHANNELS | 4 | 数据内存通道数 |
| PROGRAM_MEM_ADDR_BITS | 8 | 程序内存地址位宽 |
| PROGRAM_MEM_DATA_BITS | 16 | 程序内存数据位宽 |
| PROGRAM_MEM_NUM_CHANNELS | 1 | 程序内存通道数 |
| NUM_CORES | 2 | 核心数量 |
| THREADS_PER_BLOCK | 4 | 每核心线程数 |

---

### 端口详情

| 端口 | 方向 | 位宽 | 说明 |
|------|------|------|------|
| clk | input | - | 时钟 |
| reset | input | - | 复位 |
| start | input | - | 启动信号 |
| done | output | - | 完成信号 |
| program_mem_* | - | [7:0], [15:0], [0:0] | 程序内存接口 |
| data_mem_* | - | [7:0], [3:0] | 数据内存接口 |

---

### 实例详情

| 实例名 | 模块类型 | 连接数 | 说明 |
|--------|----------|--------|------|
| dcr_instance | dcr | 5 | 设备控制寄存器 |
| data_memory_controller | controller | 18 | 数据内存控制器 |
| program_memory_controller | controller | 10 | 程序内存控制器 |
| dispatch_instance | dispatch | 10 | 分发单元 |
| cores.core_instance | (嵌套) | - | GPU 核心 |

---

### 边类型统计

| 边类型 | 数量 | 说明 |
|--------|------|------|
| BIT_SELECT | 16 | 位选择边 |
| DRIVER | 8 | 数据驱动边 |
| **总计** | **24** | |

---

### 发现的问题

#### Issue 34: 数组索引变量出现在节点名中

**现象**:
```
节点名:
  gpu.lsu_read_valid[lsu_index] SIGNAL (1,0)
  gpu.core_lsu_read_valid[j] SIGNAL (1,0)
```

**问题**: `lsu_index` 和 `j` 是 for 循环变量，在节点名中未求值

**分析**: 这不是参数问题，而是运行时循环变量的处理问题

**影响**: 节点名不直观，难以理解

**状态**: 待讨论

---

#### Issue 35: 嵌套层次实例 nodes

**现象**:
```
实例节点: gpu.cores.core_instance
          ↑ 嵌套层次
```

**问题**: `cores` 是一个层次模块，`core_instance` 在其内部

**影响**: 节点名包含嵌套层次

**状态**: 已观察

---

### 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 gpu |
| 参数解析 | ✅ | 8 个参数正确 |
| 参数应用 | ⚠️ | 参数在节点名中正确展开 |
| 端口解析 | ✅ | 18 个端口，位宽正确 [3:0], [7:0], [15:0] |
| 实例识别 | ✅ | 5 个实例，正确处理嵌套层次 |
| 连接追踪 | ⚠️ | 无 CONNECTION 边 (子模块未解析) |

---

### sv_query 能力评估

| 能力 | 评分 | 说明 |
|------|------|------|
| GPU 解析 | ★★★★☆ | 126 节点，正确识别多核结构 |
| 参数处理 | ★★★★★ | 8 个参数全部展开 |
| 位宽解析 | ★★★★★ | [3:0], [7:0], [15:0] 全部正确 |
| 嵌套层次 | ★★★★☆ | 识别 cores.core_instance |

---

### 后续观察

1. gpu 使用参数化配置，NUM_CORES=2, THREADS_PER_BLOCK=4
2. 端口位宽正确展开为 [3:0] (4通道), [7:0] (8位), [15:0] (16位)
3. 实例包含嵌套层次 (cores.core_instance)
4. 循环变量 (lsu_index, j) 出现在节点名中


---

## eth_mac_10g 模块测试结果

**测试时间**: 2026-05-17
**文件**: `/Users/fundou/my_dv_proj/verilog-ethernet/rtl/eth_mac_10g.v`

---

### 模块信息

| 项目 | 值 |
|------|-----|
| 模块名 | eth_mac_10g |
| 参数 | 16 个 |
| 端口 | 94 个 |
| 实例数 | 2 个 |
| 总节点数 | 282 |
| 总边数 | 91 |

---

### 关键参数 (有表达式)

| 参数 | 原始值 | 说明 |
|------|--------|------|
| DATA_WIDTH | 64 | XGMII 数据位宽 |
| KEEP_WIDTH | (DATA_WIDTH/8) | 表达式未计算 |
| CTRL_WIDTH | (DATA_WIDTH/8) | 表达式未计算 |
| PTP_TS_WIDTH | PTP_TS_FMT_TOD ? 96 : 64 | 三元表达式未计算 |
| TX_USER_WIDTH | 复杂表达式 | 未计算 |
| RX_USER_WIDTH | 复杂表达式 | 未计算 |

---

### 端口详情 (部分)

| 端口方向 | 数量 | 示例 |
|----------|------|------|
| input | ~60 | tx_axis_tdata[63:0], xgmii_rxd[63:0] |
| output | ~34 | rx_axis_tdata[63:0], xgmii_txd[63:0] |

---

### 实例详情

| 实例名 | 模块类型 | 连接数 | 说明 |
|--------|----------|--------|------|
| axis_xgmii_rx_inst | axis_xgmii_rx_32 | 14 | XGMII 接收 |
| axis_xgmii_tx_inst | axis_xgmii_tx_32 | 18 | XGMII 发送 |

---

### 边类型统计

| 边类型 | 数量 | 说明 |
|--------|------|------|
| DRIVER | 86 | 数据驱动边 |
| BIT_SELECT | 5 | 位选择边 |
| **总计** | **91** | |

---

### 发现的问题

#### Issue 36: 参数表达式未计算

**现象**:
```
参数值:
  KEEP_WIDTH = (DATA_WIDTH/8)    ← 应为 8
  CTRL_WIDTH = (DATA_WIDTH/8)    ← 应为 8
  PTP_TS_WIDTH = PTP_TS_FMT_TOD ? 96 : 64  ← 应为 64 或 96
```

**问题**: 复杂参数表达式未求值，直接保留为字符串

**影响**: 用户需要手动计算参数值

**状态**: 待讨论

---

#### Issue 37: 94 个端口 - 复杂接口

**现象**: 94 个端口，包括：
- AXI Stream 接口 (tx/rx axis)
- XGMII 物理接口
- PTP 时间戳接口
- LFC/PFC 流量控制
- 配置寄存器

**分析**: 这是一个高度集成的 MAC 模块

**状态**: 已观察

---

### 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 eth_mac_10g |
| 参数解析 | ⚠️ | 16 个参数，但表达式未计算 |
| 参数应用 | ⚠️ | 端口位宽部分使用参数 |
| 端口解析 | ✅ | 94 个端口，位宽正确 |
| 实例识别 | ✅ | 2 个实例正确 |
| 连接追踪 | ⚠️ | 无 CONNECTION 边 |

---

### sv_query 能力评估

| 能力 | 评分 | 说明 |
|------|------|------|
| 复杂 MAC 解析 | ★★★★☆ | 282 节点，94 端口 |
| 参数表达式 | ★★☆☆☆ | 表达式未计算 |
| AXI Stream | ★★★★☆ | 正确识别 |
| XGMII 接口 | ★★★★☆ | 正确识别 |

---

### 后续观察

1. eth_mac_10g 是复杂的网络 MAC 模块
2. 参数使用复杂表达式：`KEEP_WIDTH = (DATA_WIDTH/8)`
3. 端口位宽使用参数引用：`tx_axis_tdata[(DATA_WIDTH-1):0]` 解析为 [63:0]
4. 子模块 axis_xgmii_rx_32, axis_xgmii_tx_32 在其他文件


---

## Vortex 模块测试结果

**测试时间**: 2026-05-17
**文件**: `/Users/fundou/my_dv_proj/vortex/hw/rtl/Vortex.sv`

---

### 模块信息

| 项目 | 值 |
|------|-----|
| 模块名 | Vortex |
| 参数 | 0 (使用 `define 宏) |
| 端口 | 17 个 |
| 实例数 | 6 个 |
| 总节点数 | 94 |
| 总边数 | 58 |

---

### 端口详情

| 端口 | 方向 | 说明 |
|------|------|------|
| clk | input | 时钟 |
| reset | input | 复位 |
| mem_req_* | output | 内存请求信号 |
| mem_rsp_* | input | 内存响应信号 |
| dcr_wr_* | input | DCR (Device Control Register) 写信号 |
| busy | output | 忙标志 |

---

### 实例详情

| 实例名 | 模块类型 | 连接数 | 说明 |
|--------|----------|--------|------|
| per_cluster_mem_bus_if | VX_mem_bus_if | 0 | 每集群内存总线接口 |
| mem_bus_if | VX_mem_bus_if | 0 | 内存总线接口 |
| __l3_reset | VX_reset_relay | 3 | L3 复位继电器 |
| l3cache | VX_cache_wrap | 4 | 三级缓存 |
| dcr_bus_if | VX_dcr_bus_if | 0 | DCR 总线接口 |
| __buffer_ex161 | VX_pipe_register | 3 | 流水线寄存器 |

---

### 边类型统计

| 边类型 | 数量 | 说明 |
|--------|------|------|
| DRIVER | 29 | 数据驱动边 |
| BIT_SELECT | 29 | 位选择边 |
| **总计** | **58** | |

---

### 发现的问题

#### Issue 38: 实例连接数为 0

**现象**:
```
实例:
  VX_mem_bus_if: 0 连接
  VX_dcr_bus_if: 0 连接
```

**问题**: 内存接口实例没有连接

**分析**: 
1. 子模块未解析，无法获取端口定义
2. 或者连接真的是空的

**状态**: 待调查

---

#### Issue 39: 使用 `define 宏而非参数

**现象**:
```
参数数: 0
```

**问题**: Vortex 使用 `define 宏而不是 module parameter

**影响**: sv_query 无法解析 `define 宏的值

**状态**: 已观察

---

### 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 Vortex |
| 参数解析 | ⚠️ | 无 (使用 `define) |
| 端口解析 | ✅ | 17 个端口正确 |
| 实例识别 | ✅ | 6 个实例正确 |
| 连接追踪 | ⚠️ | 部分实例连接为 0 |

---

### sv_query 能力评估

| 能力 | 评分 | 说明 |
|------|------|------|
| GPU 解析 | ★★★★☆ | 94 节点，正确识别缓存结构 |
| 宏处理 | ★☆☆☆☆ | 无法解析 `define) |
| 实例接口 | ★★★☆☆ | 6 个实例，部分连接为 0 |

---

### 后续观察

1. Vortex 使用 `define 宏定义配置参数
2. 实例命名包含下划线前缀: `__l3_reset`, `__buffer_ex161`
3. 内存接口使用请求/响应模式
4. 三级缓存 (L3) 是重要组件


---

## NV_nvdla (NVDLA Top) 模块测试结果

**测试时间**: 2026-05-17
**文件**: `/Users/fundou/my_dv_proj/hw/vmod/nvdla/top/NV_nvdla.v`

---

### 模块信息

| 项目 | 值 |
|------|-----|
| 模块名 | NV_nvdla |
| 参数 | 0 (使用 `define) |
| 端口 | 69 个 |
| 实例数 | 6 个 |
| 总节点数 | 2115 |
| 总边数 | 0 |

---

### 端口详情

| 端口 | 方向 | 位宽 | 说明 |
|------|------|------|------|
| dla_core_clk | input | - | 核心时钟 |
| dla_csb_clk | input | - | CSB 配置时钟 |
| csb2nvdla_* | input | [15:0], [31:0] | CSB 配置接口 |
| nvdla2csb_* | output | [31:0] | CSB 响应 |
| nvdla_core2dbb_* | output | [63:0], [511:0] | AXI 主接口 |

---

### 实例详情

| 实例名 | 模块类型 | 连接数 | 说明 |
|--------|----------|--------|------|
| u_partition_o | NV_NVDLA_partition_o | 720 | 输出分区 |
| u_partition_c | NV_NVDLA_partition_c | 592 |  配置分区 |
| u_partition_ma | NV_NVDLA_partition_m | 286 | MAC 分区 A |
| u_partition_mb | NV_NVDLA_partition_m | 286 | MAC 分区 B |
| u_partition_a | NV_NVDLA_partition_a | 43 | 激活分区 |
| u_partition_p | NV_NVDLA_partition_p | 113 | PDP 分区 |

---

### 节点类型统计

| 节点类型 | 数量 | 说明 |
|----------|------|------|
| PORT_IN | 2076 | 输入端口 |
| PORT_OUT | 33 | 输出端口 |
| INSTANTIATED_MODULE | 6 | 实例模块 |
| **总计** | **2115** | |

---

### 发现的问题

#### Issue 40: 总边数为 0

**现象**:
```
边数: 0
节点数: 2115
```

**根因**: NV_nvdla.v 中所有 assign 语句都被注释掉了
```verilog
//assign nvdla_host1x_clk = dla_host1x_clk;
//assign nvdla_falcon_clk = dla_falcon_clk;
//assign nvdla_core_clk = dla_core_clk;
```

**分析**: 
1. NV_nvdla 是纯实例化模块，没有自己的逻辑
2. 所有信号连接通过子模块实例的端口连接完成
3. DriverExtractor 无法创建边 (无 assign 语句)
4. ConnectionExtractor 创建端口节点但不创建边 (子模块未解析)

**影响**: 无法追踪信号驱动关系

**状态**: 设计约束 (模块结构问题)

---

#### Issue 41: 子模块未解析导致无连接

**现象**:
```
实例连接:
  u_partition_o: 720 连接 (但无 CONNECTION 边)

子模块未解析:
  NV_NVDLA_partition_o: False
```

**问题**: 子模块 (partition_o, partition_c 等) 未解析

**影响**: 无法建立实例端口连接边

**状态**: 设计约束

---

#### Issue 42: 大型 SoC 节点管理

**现象**:
```
节点数: 2115
  ├── 2076 个 PORT_IN
  └── 33 个 PORT_OUT
```

**问题**: 2115 个节点，2076 个是输入端口

**分析**: 每个实例端口创建了一个 PORT_IN 节点

**影响**: 节点数量大但边数为 0

**状态**: 已观察

---

### 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| 模块识别 | ✅ | 正确识别 NV_nvdla |
| 参数解析 | ⚠️ | 无 (使用 `define) |
| 端口解析 | ✅ | 69 个端口正确 |
| 实例识别 | ✅ | 6 个分区实例正确 |
| 连接追踪 | ⚠️ | 0 边 (无 assign, 子模块未解析) |

---

### sv_query 能力评估

| 能力 | 评分 | 说明 |
|------|------|------|
| 大型 SoC 解析 | ★★★☆☆ | 2115 节点，但无边 |
| 实例接口 | ★★★★☆ | 6 个分区，1800+ 连接 |
| 信号追踪 | ★☆☆☆☆ | 无法追踪 (无 assign) |
| 层次结构 | ★★★☆☆ | 识别分区但无法连接 |

---

### 后续观察

1. NV_nvdla 是纯结构化顶层模块
2. 所有逻辑在子模块 (partition_*) 中
3. 子模块在 `hw/vmod/nvdla/` 目录的其他文件中
4. 需要解析所有 partition 文件才能建立连接

