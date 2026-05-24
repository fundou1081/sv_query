# Issue 讨论汇总

**讨论日期**: 2026-05-17
**Issue 总数**: 42

---

## 讨论分组

### 第1组: 节点命名问题 (6个)

| Issue | 问题 | 模块 | 优先级 |
|-------|------|------|--------|
| Issue 28 | 注释混入节点名 | mult_pipe2 | P1 |
| Issue 33 | 字面量作为节点名 | serv_top | P1 |
| Issue 34 | 循环变量出现在节点名 | gpu | P1 |
| Issue 21 | 参数表达式未展开 | dual_clock_fifo | P2 |
| Issue 27 | 参数未展开 | mult_pipe2 | P2 |
| Issue 29 | 复杂参数未展开 | cva6 | P2 |

---

### 第2组: 连接追踪问题 (6个)

| Issue | 问题 | 模块 | 优先级 |
|-------|------|------|--------|
| Issue 32 | 实例端口无连接边 | serv_top | P2 |
| Issue 38 | 实例连接数为0 | Vortex | P3 |
| Issue 18 | LOAD边统计为0 | bs_mult | P2 |
| Issue 24 | 无CONNECTION边 | pe | 设计约束 |
| Issue 30 | 无CONNECTION边 | cva6 | 设计约束 |
| Issue 40 | 总边数为0 | NV_nvdla | 设计约束 |

---

### 第3组: 位宽/类型问题 (3个)

| Issue | 问题 | 模块 | 优先级 |
|-------|------|------|--------|
| Issue 31 | 位宽(0,0) | cva6 | P2 |
| Issue 22 | 函数标记为SIGNAL | dual_clock_fifo | P2 |
| Issue 23 | mem端口方向缺失 | dual_clock_fifo | P3 |

---

### 第4组: 其他问题 (6个)

| Issue | 问题 | 模块 | 优先级 |
|-------|------|------|--------|
| Issue 36 | 参数表达式未计算 | eth_mac_10g | P2 |
| Issue 39 | `define宏无法解析 | Vortex | 已观察 |
| Issue 35 | 嵌套层次实例 | gpu | 已观察 |
| Issue 37 | 94端口复杂接口 | eth_mac_10g | 已观察 |
| Issue 41 | 子模块未解析 | NV_nvdla | 设计约束 |
| Issue 42 | 大型SoC节点管理 | NV_nvdla | 已观察 |

---

## 第1组: 节点命名问题 详细案例

---

### Issue 28: 注释混入节点名

**文件**: `~/my_dv_proj/clacc/mult_pipe2.v`

**现象**:
```
节点名: mult_pipe2.// registering input of the multiplier a_int
```

**根因**: sv_query 在解析信号名时，没有过滤注释

**当前行为**: 注释被当作信号名的一部分

**期望行为**: 注释应该被过滤，节点名应该是 `a_int`

**影响**: 节点名混乱，难以理解

**建议解决方案**:
1. 在节点名提取时过滤 `//` 和 `/*` 注释
2. 在 graph_builder 中添加注释过滤逻辑

---

### Issue 33: 字面量作为节点名

**文件**: `~/my_dv_proj/serv/rtl/serv_top.v`

**现象**:
```
边: serv_top.0 -> serv_top.iscomp (DRIVER)
边: 1'b0 -> serv_top.csr_in (DRIVER)
```

**根因**: 字面量被当作节点创建

**当前行为**: 字面量 `0`, `1'b0` 被创建为节点

**期望行为**: 字面量不应该创建为节点，只应该创建边

**影响**: 节点名不直观

**建议解决方案**:
1. 在 `_get_all_signals` 中检测字面量并跳过节点创建
2. 只创建字面量到目标的边

---

### Issue 34: 循环变量出现在节点名

**文件**: `~/my_dv_proj/tiny-gpu/src/gpu.sv`

**现象**:
```
节点名:
  gpu.lsu_read_valid[lsu_index] SIGNAL (1,0)
  gpu.core_lsu_read_valid[j] SIGNAL (1,0)
```

**根因**: for 循环变量 `lsu_index`, `j` 在节点名中未求值

**当前行为**: 循环变量保留在节点名中

**期望行为**: 应该使用具体的循环索引值，或者使用通用的表示

**影响**: 节点名不直观，难以理解

**建议解决方案**:
1. 展开循环变量为具体值 (需要知道循环范围)
2. 或者使用 `[i]` 形式保留变量名
3. 在文档中说明循环变量的处理方式

---

### Issue 21: 参数表达式未展开 (ADDR_WIDTH-1)

**文件**: `~/my_dv_proj/clacc/dual_clock_fifo.v`

**现象**:
```
节点名: dual_clock_fifo.in[ADDR_WIDTH-1]
期望:   dual_clock_fifo.in[2] (因为 ADDR_WIDTH=3)
```

**根因**: 参数 `ADDR_WIDTH=3` 被解析，但在节点名中未应用

**当前行为**: 节点名包含参数名 `ADDR_WIDTH-1`

**期望行为**: 参数应该被求值，节点名应该是 `in[2]`

**影响**: 节点名不直观

**建议解决方案**:
1. 在创建节点时使用参数值替换参数名
2. 需要在创建节点前解析参数表达式

---

### Issue 27: 参数未展开 (LVL-1)

**文件**: `~/my_dv_proj/clacc/mult_pipe2.v`

**现象**:
```
节点名: mult_pipe2.pdt_int [LVL-1]
期望:   mult_pipe2.pdt_int[1] (因为 LVL=2)
```

**根因**: 同 Issue 21

**当前行为**: 参数 LVL 在节点名中未求值

**期望行为**: 应该显示 `pdt_int[1]`

**建议解决方案**: 同 Issue 21

---

### Issue 29: 复杂参数未展开 (CVA6Cfg)

**文件**: `~/my_dv_proj/cva6/core/cva6.sv`

**现象**:
```
节点名: cva6.trans_id_ex_id[CVA6Cfg.TRANS_ID_BITS-1:0]
```

**根因**: `CVA6Cfg` 是复杂参数对象，包含嵌套参数

**当前行为**: 整个参数引用保留在节点名中

**期望行为**: 应该展开为具体的位宽

**影响**: 节点名非常长，难以理解

**建议解决方案**:
1. 识别复杂参数对象并解析其子参数
2. 或者在文档中说明复杂参数的处理限制

---

## 第2组: 连接追踪问题 详细案例

---

### Issue 32: 实例端口无连接边

**文件**: `~/my_dv_proj/serv/rtl/serv_top.v`

**现象**:
```
实例端口节点: 282 个 (如 serv_top.state.i_clk)
边数: 20 (全是 DRIVER，无 CONNECTION)

总节点数: 342
  ├── 顶层端口: 33
  ├── 实例: 13
  └── 实例端口: 282
```

**根因**: 子模块 (serv_state 等) 未解析，端口方向未知

**当前行为**: 实例端口节点被创建，但没有 CONNECTION 边

**期望行为**: 应该有 CONNECTION 边连接实例端口和信号

**分析**: 
- ConnectionExtractor 创建了 282 个实例端口节点
- 但因为 module_ports 为空 (子模块未解析)，所有方向是 'unknown'
- unknown 方向不创建边

**建议解决方案**:
1. 确认这是设计约束还是可以改进
2. 如果可以改进，需要在子模块未解析时给出更明确的警告

---

### Issue 38: 实例连接数为0

**文件**: `~/my_dv_proj/vortex/hw/rtl/Vortex.sv`

**现象**:
```
实例:
  VX_mem_bus_if: 0 连接
  VX_dcr_bus_if: 0 连接
```

**根因**: 待调查 - 可能是子模块未解析

**建议解决方案**:
1. 确认子模块是否在解析范围内
2. 检查 get_instance_connection 的返回值

---

### Issue 18: LOAD边统计为0

**文件**: `~/my_dv_proj/clacc/bs_mult.v`

**现象**:
```
边类型统计:
  DRIVER: 3
  LOAD: 0
  总边数: 3
```

**根因**: bs_mult_slice.v 未解析，端口方向未知

**已确认结论**: 设计约束，保持现状

---

## 第3组: 位宽/类型问题 详细案例

---

### Issue 31: 位宽(0,0)

**文件**: `~/my_dv_proj/cva6/core/cva6.sv`

**现象**:
```
节点: cva6.clk_i PORT_IN (0,0)
节点: cva6.rst_ni PORT_IN (0,0)
节点: cva6.irq_i PORT_IN (1,0)
```

**问题**: 
- (0,0) 是 1-bit 还是未识别？
- 大部分端口是 (0,0)，只有部分是 (1,0)

**分析**:
- (1,0) 表示 1-bit (msb=1, lsb=0)
- (0,0) 表示什么？应该是 1-bit 还是未识别？

**建议解决方案**:
1. 确定 (0,0) 的含义
2. 如果是未识别，需要改进端口位宽解析
3. 如果是 1-bit，需要修改默认值

---

### Issue 22: 函数节点被标记为SIGNAL

**文件**: `~/my_dv_proj/clacc/dual_clock_fifo.v`

**现象**:
```
节点: dual_clock_fifo.gray_conv SIGNAL
期望: dual_clock_fifo.gray_conv FUNCTION
```

**根因**: 没有 FUNCTION 类型的 NodeKind

**当前行为**: 函数被标记为 SIGNAL

**期望行为**: 应该有 FUNCTION 类型区分函数和信号

**建议解决方案**:
1. 在 NodeKind 中添加 FUNCTION 类型
2. 在解析时识别函数定义并标记为 FUNCTION

---

### Issue 23: mem存储端口方向缺失

**文件**: `~/my_dv_proj/clacc/dual_clock_fifo.v`

**现象**:
```
驱动边:
  wr_data_i -> mem[wr_addr]  (写入)
  mem[rd_addr] -> rd_data_o  (读取)
```

**问题**: mem 是双端口 RAM，但显示为单一信号

**当前行为**: mem[wr_addr] 和 mem[rd_addr] 都是 SIGNAL

**期望行为**: 应该区分读端口和写端口的方向

**建议解决方案**:
1. 添加 MEMORY 类型的 NodeKind
2. 或者在节点名中标识读/写 (如 `mem.write`, `mem.read`)

---

## 讨论要点

### 1. 节点命名问题的优先级

**P1 (建议先修)**:
- Issue 28: 注释混入 - 影响基本可读性
- Issue 33: 字面量节点 - 不应该创建
- Issue 34: 循环变量 - 影响可读性

**P2 (次优先级)**:
- Issue 21, 27, 29: 参数展开

### 2. 连接追踪问题

**结论**: 大部分是设计约束 (子模块未解析)
- Issue 18, 24, 30, 40, 41: 保持现状
- Issue 32, 38: 需要进一步调查

### 3. 位宽/类型问题

**建议**:
- Issue 31: 确定 (0,0) 的含义
- Issue 22: 添加 FUNCTION 类型
- Issue 23: 添加 MEMORY 类型

---

## 建议的行动计划

### 第一步: 修复 P1 问题 (节点命名)

| Issue | 修复方案 | 工作量 |
|-------|----------|--------|
| Issue 28 | 注释过滤逻辑 | 小 |
| Issue 33 | 字面量不创建节点 | 小 |
| Issue 34 | 循环变量处理 | 中 |

### 第二步: 改进 P2 问题 (参数展开)

| Issue | 修复方案 | 工作量 |
|-------|----------|--------|
| Issue 21, 27 | 参数表达式求值 | 中 |
| Issue 29 | 复杂参数处理 | 大 |
| Issue 31 | 位宽解析改进 | 中 |

### 第三步: 新增类型 (可选)

| Issue | 修复方案 | 工作量 |
|-------|----------|--------|
| Issue 22 | 添加 FUNCTION 类型 | 中 |
| Issue 23 | 添加 MEMORY 类型 | 中 |

---

## 待讨论问题

1. **Issue 34 (循环变量)**: 是展开循环索引还是保留变量名？
2. **Issue 29 (复杂参数)**: CVA6Cfg 这种嵌套参数是否值得支持？
3. **Issue 31 ((0,0) 含义)**: (0,0) 是 1-bit 还是未识别？
4. **Issue 32, 38**: 是否需要进一步调查根因？