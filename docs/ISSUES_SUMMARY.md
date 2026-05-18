# sv_query Issue 汇总

**文档版本**: v1.1
**更新时间**: 2026-05-18
**测试轮次**: Round 4 (OpenChip QA)

---

## Issue 总览

| Issue | 问题 | 模块 | 优先级 | 状态 |
|-------|------|------|--------|------|
| Issue 17 | 非ANSI端口位宽丢失 | bs_mult | P2 | 已记录 |
| Issue 18 | LOAD 边统计为 0 | bs_mult | P2 | 已确认 |
| Issue 19 | 实例节点前缀 "top" | bs_mult | P1 | ✅ 已修复 |
| Issue 20 | 边数只有 3 | bs_mult | P1 | ✅ 已修复 |
| Issue 21 | 参数表达式未展开 | dual_clock_fifo | P2 | ✅ 已修复 |
| Issue 22 | 函数节点被标记为 SIGNAL | dual_clock_fifo | P2 | ✅ 已修复 |
| Issue 23 | mem 存储访问缺少端口方向 | dual_clock_fifo | P3 | 待讨论 |
| Issue 24 | pe 模块无连接边 | pe | P2 | 设计约束 |
| Issue 25 | clacc 反格式实例名 | pe | P1 | ✅ 已解决 |
| Issue 26 | SPAD 连接信息不完整 | pe | P3 | 设计约束 |
| Issue 27 | 参数在节点名中未展开 | mult_pipe2 | P2 | ✅ 已修复 |
| Issue 28 | 注释混入节点名 | mult_pipe2 | P2 | ✅ 已修复 |
| Issue 29 | CVA6Cfg 参数未展开 | cva6 | P2 | 设计约束 |
| Issue 30 | 无 CONNECTION 边 | cva6 | P2 | 设计约束 |
| Issue 31 | 位宽 (0,0) 问题 | cva6 | P2 | 设计约束 |
| Issue 32 | 实例端口无连接边 | serv_top | P2 | 待调查 |
| Issue 33 | 字面量作为节点名 | serv_top | P3 | ✅ 已修复 |
| Issue 34 | 数组索引变量出现在节点名 | gpu | P3 | 待讨论 |
| Issue 35 | 嵌套层次实例 | gpu | P3 | 已观察 |
| Issue 36 | 参数表达式未计算 | eth_mac_10g | P2 | ✅ 已修复 |
| Issue 37 | 94 个端口复杂接口 | eth_mac_10g | P4 | 已观察 |
| Issue 38 | 实例连接数为 0 | Vortex | P3 | 待调查 |
| Issue 39 | 使用 define 宏而非参数 | Vortex | P2 | 已观察 |
| Issue 40 | 总边数为 0 | NV_nvdla | P2 | 设计约束 |
| Issue 41 | 子模块未解析导致无连接 | NV_nvdla | P2 | 设计约束 |
| Issue 42 | 大型 SoC 节点管理 | NV_nvdla | P3 | 已观察 |
| Issue 43 | 参数链未展开 (B = W-1) | dual_clock_fifo | P2 | ✅ 已修复 |

---

## 按状态分类

### ✅ 已修复 (4个)

| Issue | 修复内容 | Commit |
|-------|----------|--------|
| Issue 19 | 动态获取根模块名替代硬编码 "top" | 94ad7fa |
| Issue 20 | 添加可能缺少文件的警告提示 | f2b1647 |
| Issue 25 | adapter 正确处理 clacc 反格式 | 已内置 |
| Issue 43 | 参数链解析 (B=W-1, C=B+1 等) | ea9ef6d |

### ✅ 已确认/已记录 (5个)

| Issue | 结论 |
|-------|------|
| Issue 17 | 源代码不符合 SV 标准，非 sv_query bug |
| Issue 18 | 设计约束，解析范围问题 |
| Issue 24 | 设计约束，子模块未解析 |
| Issue 26 | 设计约束，SPAD 模块未解析 |
| Issue 30 | 设计约束，子模块未解析 |

### 🔍 待讨论 (32个)

| Issue | 需要讨论的问题 |
|-------|----------------|
| Issue 21 | 参数表达式在节点名中未展开的解决方案 |
| Issue 22 | 函数节点应如何标记？需要新增 NodeKind 吗？ |
| Issue 23 | mem 存储的读写端口方向如何表示？ |
| Issue 27 | 参数在节点名中未展开 (mult_pipe2) |
| Issue 28 | 注释混入节点名的过滤方案 |
| Issue 29 | 复杂参数对象 (CVA6Cfg) 的处理方式 |
| Issue 31 | 位宽 (0,0) 的含义和改善方案 |
| Issue 32 | 实例端口无连接边的根因 |
| Issue 33 | 字面量作为节点名的处理 |
| Issue 34 | 数组索引变量的处理 (lsu_index, j) |
| Issue 36 | 复杂参数表达式的求值方案 |
| Issue 38 | Vortex 实例连接为 0 的根因 |

---

## 按问题类型分类

### 1. 参数处理问题 (4个)

| Issue | 问题 | 影响 |
|-------|------|------|
| Issue 21 | ADDR_WIDTH-1 未展开 | dual_clock_fifo |
| Issue 27 | LVL-1 未展开 | mult_pipe2 |
| Issue 29 | CVA6Cfg.TRANS_ID_BITS-1 未展开 | cva6 |
| Issue 36 | (DATA_WIDTH/8) 未计算 | eth_mac_10g |

**现象**:
```
节点名: dual_clock_fifo.in[ADDR_WIDTH-1]
期望:   dual_clock_fifo.in[2] (因为 ADDR_WIDTH=3)
```

**讨论点**:
- 是否需要实现参数表达式求值？
- 求值失败时的 fallback 行为？
- 参数引用的解析优先级？

---

### 2. 节点命名问题 (3个)

| Issue | 问题 | 影响 |
|-------|------|------|
| Issue 28 | 注释混入节点名 | mult_pipe2 |
| Issue 33 | 字面量作为节点名 | serv_top |
| Issue 34 | 循环变量出现在节点名 | gpu |

**现象**:
```
// Issue 28
节点名: mult_pipe2.// registering input of the multiplier a_int

// Issue 33
节点名: serv_top.0 -> serv_top.iscomp

// Issue 34
节点名: gpu.lsu_read_valid[lsu_index]
```

**讨论点**:
- 注释过滤规则？
- 字面量节点是否应该创建？
- 循环变量的处理方式？

---

### 3. 连接追踪问题 (6个)

| Issue | 问题 | 影响 |
|-------|------|------|
| Issue 18 | LOAD 边统计为 0 | bs_mult |
| Issue 24 | 无 CONNECTION 边 | pe |
| Issue 30 | 无 CONNECTION 边 | cva6 |
| Issue 32 | 实例端口无连接边 | serv_top |
| Issue 40 | 总边数为 0 | NV_nvdla |
| Issue 41 | 子模块未解析 | NV_nvdla |

**现象**:
```
节点数: 2115 (NV_nvdla)
边数: 0
```

**讨论点**:
- 解析范围约束的文档说明
- 是否需要自动推断模块路径？
- 子模块缺失时的警告级别？

---

### 4. 位宽/类型问题 (3个)

| Issue | 问题 | 影响 |
|-------|------|------|
| Issue 22 | 函数被标记为 SIGNAL | dual_clock_fifo |
| Issue 23 | mem 存储端口方向缺失 | dual_clock_fifo |
| Issue 31 | 位宽 (0,0) | cva6 |

**现象**:
```
// Issue 22
gray_conv 函数被标记为 SIGNAL

// Issue 23
mem[wr_addr] 和 mem[rd_addr] 都是 SIGNAL

// Issue 31
cva6.clk_i PORT_IN (0,0)
```

**讨论点**:
- 是否需要 FUNCTION/FIFO/MEMORY 等新 NodeKind？
- 位宽 (0,0) 的含义？1-bit 还是未识别？

---

### 5. 设计约束 (5个)

| Issue | 说明 |
|-------|------|
| Issue 17 | 源代码不符合 SV 标准 |
| Issue 18 | 解析范围不完整 |
| Issue 24 | 子模块未解析 |
| Issue 26 | SPAD 模块未解析 |
| Issue 30 | 子模块未解析 |

**处理方式**: 保持现状，已有警告提示

---

### 6. 其他观察 (6个)

| Issue | 说明 |
|-------|------|
| Issue 25 | clacc 反格式已正确处理 |
| Issue 35 | 嵌套层次实例已识别 (cores.core_instance) |
| Issue 37 | 94 端口复杂接口是正常规模 |
| Issue 38 | Vortex 实例连接为 0 需调查 |
| Issue 39 | `define 宏无法解析是已知限制 |
| Issue 42 | 大型 SoC 节点管理是规模问题 |

---

## 测试项目统计

| 项目 | 模块数 | 总节点 | 总边 | 发现 Issue |
|------|--------|--------|------|------------|
| clacc | 4 | 439 | 37 | 9 |
| cva6 | 1 | 781 | 191 | 3 |
| serv | 1 | 342 | 20 | 2 |
| tiny-gpu | 1 | 126 | 24 | 2 |
| verilog-ethernet | 1 | 282 | 91 | 2 |
| vortex | 1 | 94 | 58 | 2 |
| nvdla | 1 | 2115 | 0 | 3 |
| **总计** | **10** | **4179** | **421** | **23** |

---

## 建议的修复优先级

### P1 (高优先级)

| Issue | 理由 |
|-------|------|
| Issue 28 | 影响节点名可读性 |
| Issue 33 | 字面量作为节点名不应该 |
| Issue 34 | 循环变量不应该出现在节点名 |

### P2 (中优先级)

| Issue | 理由 |
|-------|------|
| Issue 21 | 参数表达式常见问题 |
| Issue 27 | 参数表达式常见问题 |
| Issue 29 | CVA6Cfg 类型复杂需处理 |
| Issue 36 | 参数表达式常见问题 |
| Issue 31 | 位宽问题影响显示 |

### P3 (低优先级)

| Issue | 理由 |
|-------|------|
| Issue 22 | 函数标记较少见 |
| Issue 23 | mem 存储较少见 |
| Issue 32 | 需进一步调查 |
| Issue 38 | 需进一步调查 |

---

## 文档记录

| Issue | 文档位置 |
|-------|----------|
| Issue 17 | docs/ISSUE_17_CASE_BS_MULT.md |
| Issue 18 | docs/ISSUE_18_CONCLUSION.md |
| Issue 19 | 94ad7fa commit |
| Issue 20 | f2b1647 commit |
| Issue 21-42 | docs/OPENCHIP_QA_ROUND4_ISSUES.md |

---

## 下一步

1. **Issue 讨论会**: 讨论 P1/P2 Issue 的解决方案
2. **修复计划**: 制定 Issue 28, 33, 34 的修复方案
3. **文档完善**: 更新 sv_query README 说明解析范围约束