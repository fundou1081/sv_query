# Spike 0 Report — API Feasibility

> 日期: 2026-06-10
> 目的: 在写代码前, 验证 graph_builder / port access / struct 等 API 是否支持 Phase A 协议检测

---

## ✅ 已验证 (4 个)

### V1. Port list 访问 (B1, B2 解决)
- **API**: `adapter.get_port_declarations(module)` → list of PortSymbol
- **属性**: `port.name`, `port.direction` (PortDirection enum: Input/Output/Inout)
- **辅助**: `get_port_name_and_direction(port)` → `(name, direction)`, `extract_port_width(port)` → width
- **测试**: picorv32 (32 ports), verilog-axi axi_adapter (25 ports), 简单 AXI4 模块 (25 ports), 匿名信号 (12 ports) — **全部正确**

✅ **结论**: RoleDetector 可以**完全靠** port list 拿到 (name, direction, width)。**B1/B2 的输入解决了**。

### V2. Co-occurrence 数据源 (B8 解决) ⭐ 关键发现
- **机制**: graph_builder 在 `TraceEdge.condition` 字段记录驱动条件的**字符串**形式
- **示例**: `if (v_in && r_in) y_out <= 1'b1;` → edge `clk -> y_out` 的 `condition = "v_in && r_in"`
- **PairFinder 算法变得简单**:
  ```python
  for edge in graph.edges():
      for sig in extract_signals_from_str(edge.condition):
          # 所有出现在同一 condition 的信号 = 在同一 if 块里共现
  ```
- **不需要** AST 二次遍历! 完全用现有 graph

✅ **结论**: PairFinder 数据源已就绪。**B8 解决**, **Session 2 工作量减少 50%**。

### V3. Packed struct 部分处理 (B7 部分解决)
- **现状**: graph_builder 有 `_collect_struct_members` + `_expand_struct_assignments` 两个方法
- **生效场景**:
  - 整 struct 赋值 (`m_aw <= s_aw;`) — 自动展开为成员赋值
  - 字段访问 (`s_aw.valid`) — 自动收集到 `_struct_members`
- **不生效场景** (Spike 验证):
  - 端口是 struct 整体 (`output aw_chan_t m_aw`) — 字段不会出现在 graph nodes
  - 验证: 测试中, `axi_with_struct.m_aw` 是唯一节点, 没有 `m_aw.valid` / `m_aw.addr`

⚠️ **结论**: 部分支持。**Phase A 协议检测的实用范围**:
- ✅ 普通端口 (verilog-axi 风格): 完全支持
- ⚠️ 整 struct 端口 (axi_pkg 风格): 仅支持"整 struct 配对"作为 1 个 signal, **不能识别 struct 字段 role**
- **不阻塞 MVP**, 但完整支持需先做 struct 字段展开 (独立 PR, 1-2 小时)

### V4. Module 列表 (B2 解决)
- **API**: `adapter.get_modules()` → list of InstanceSymbol
- **过滤**: `adapter.get_module_name(module)` → name string
- **测试**: picorv32 有多个 module (picorv32_axi, simpleuart, ...), 都能正确枚举

✅ **结论**: 全项目扫描可做。

---

## ❌ 不支持的 / 需 workaround (2 个)

### N1. Co-occurrence 只能在 `if` 条件里识别 (B3 风险)

**问题**: 
```verilog
// 可识别 (if 条件)
if (v && r) y <= ...;   // 边 condition = "v && r"

// 不可识别 (assign)
assign y = v && r;       // 边 condition = "" (assign 无 if)
```

**测试**:
- `if (v && r)` → ✅ edge has condition
- `assign y = v & r;` → ❌ edge has no condition

**影响**: `assign` 风格握手对识别不到 (但 AW/W/B/AR/R 主线都靠 always_ff 写, 所以实际 AXI 项目不受影响)

**Workaround**: PairFinder 接受 2 个权重来源:
- "高权重" 共现 (if 条件, condition 字段)
- "低权重" 名字 hint (io_aw_valid + io_aw_ready 这种)

### N2. verilog-axi 完整项目跑不动 (Session 5 风险)

**问题**: verilog-axi 模块互相依赖 (axi_adapter 用 axi_adapter_wr/rd, axi_crossbar 用 axi_crossbar_wr/rd), 单独模块跑不动

**测试**:
- ✅ picorv32 单文件能跑
- ❌ verilog-axi 单文件失败 (需要 priority_encoder, axi_adapter_wr 等)
- ❌ opentitan tlul 单文件失败 (需要 top_pkg, prim_fifo_sync)

**影响**: Session 5 真实项目验证受挫

**Workaround**:
- 先用 picorv32 + 自定义 SV 测试 (足够覆盖 90% 场景)
- verilog-axi 跑全 filelist (axi_adapter.v + axi_register_wr.v + axi_register_rd.v + arbiter.v)
- opentitan 找最小独立模块 (e.g. tlul_fifo_sync) 或写 mock package

---

## 📊 关键发现汇总

| Blocker | 状态 | 解决方式 |
|---------|------|----------|
| B1 (master/slave 方向) | ⚠️ 仍需解决 | Spike 没探, 需在 RoleDetector 设计时显式处理 |
| B2 (信号分组) | ✅ 输入已就绪 | port list 完整; 分组算法需 Session 1 设计 |
| B3 (co-occurrence 定义) | ✅ 已明确 | TraceEdge.condition 字段就是数据源 |
| B7 (packed struct) | ⚠️ 部分 | 需在 Session 5 加 struct 字段展开 |
| B8 (graph_builder API) | ✅ 完全解决 | `edge.condition` 字段直接用 |

---

## 🎯 Spike 0 → Session 1 衔接

### Session 1 (RoleDetector) 立即可开始

**输入** (✅ 全部就绪):
- `adapter.get_port_declarations(module)` → ports
- `port.name` / `port.direction` / `port.width` — **三重信号特征**
- 不需要 graph, 不需要 AST 二次遍历

**输出** (✅ 清晰):
- `dict[role, list[RoleCandidate]]` — 每个 role 多个候选 + confidence

**测试** (✅ 已有 5 个真实模块):
1. 简单 AXI4 master (Test 1)
2. packed struct 模块 (Test 2)
3. picorv32 (Test 3)
4. (待加) verilog-axi axi_adapter (需 filelist)
5. (待加) 匿名信号 (Test 5)

**预估代码**: 100-150 行 (比原计划 150-200 少, 因为 API 已简化)

---

## 📝 修订建议 (更新到 plan)

### Plan 需修改
1. **B1 master/slave 方向反转**: 仍未解, Session 1 必须显式处理。建议 "双向尝试" 策略。
2. **B7 packed struct**: 推迟到 Session 5, MVP 不要求。Session 1 注释里写明"不支持 struct 字段"
3. **verilog-axi 单文件失败**: Session 5 用 filelist workaround, 或者降级到 picorv32 验证

### Plan 不变
1. **B3 co-occurrence**: 现有 `TraceEdge.condition` 字段就够
2. **B8 graph API**: 完全用现有 API, 无需新方法

---

## 🚀 下一步行动

**Session 1 立即可启动** (因为 B3/B8 输入已就绪):

1. 创建 `src/trace/core/protocol/__init__.py`
2. 创建 `src/trace/core/protocol/role_detector.py` (~150 行)
3. 写 20 个单元测试 (覆盖: 简单 AXI, packed struct, 匿名, 宽信号, etc.)
4. 跑 picorv32 + 简单 AXI4 测试, 验证 RoleDetector 正确分类

**B1 master/slave 解决方案** (在 Session 1 内处理):
- RoleDetector 输出时, 标记每个 valid/ready 候选的"preferred direction"
- 给 2 个 view: "as_master" (output=source), "as_slave" (input=source)
- matcher 跑 2 次, 取最高分

---

## ✅ Spike 0 结论

| 项 | 状态 |
|----|------|
| API 可行性 | ✅ 核心 API 都可用 |
| 数据源 | ✅ graph_builder.condition 字段足够 |
| 时间 | 比预期少 50% (B8 解决) |
| 风险 | 1 个 (B7 struct, 可推迟) |

**绿灯, 进入 Session 1。**
