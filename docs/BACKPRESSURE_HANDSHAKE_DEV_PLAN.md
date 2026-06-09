# Backpressure + Handshake Detector — 开发计划

> 创建日期: 2026-06-08
> 状态: 进行中（Phase B 完成，命令拆分 + backpressure 改造待做）
> 关联设计稿: `docs/bus_protocol_detector.md`
> 关联测试: `sim/tests/unit/test_handshake_detector.py` (31 cases)
> 关联源码:
> - `src/trace/core/handshake_detector.py` (Phase B 核心)
> - `src/cli/commands/backpressure.py` (backpressure CLI, 含临时 `--protocol-confirm`)

---

## 0. 总体目标

从 Verilog/SystemVerilog 源码**自动识别总线反压路径**，覆盖 AXI / TileLink-UL / AHB / Wishbone。

**核心思路（hybrid 方案）**：
- **Phase A — Schema 匹配**：用 YAML 协议配置（端口名模式）粗筛候选模块
- **Phase B — Handshake 确认**：用 `handshake_detector` 分析驱动条件，精判握手语义
- **结果**：每条 ready/valid 信号 → 协议 + 方向 + 握手类型 + 时钟域 + confidence

**正确依赖链**：
```
handshake_detector (Phase B, 通用)            ← 任何 ready/valid 都能分析
        ↓ 提供分类信息
backpressure 路径追踪                          ← 只追踪真反压节点，过滤透传线
```

**反例**（之前做错的方向）：把 `--protocol-confirm` 塞在 `backpressure` 命令下，导致功能归属混乱。

---

## 1. 任务分解（WBS）

| # | 任务 | 类型 | 状态 | Commit |
|---|------|------|------|--------|
| 1.1 | Phase B 核心：`handshake_detector.py` | 新增 | ✅ 完成 | `11e5196` |
| 1.2 | 临时集成：`backpressure --protocol-confirm` | 新增 | ✅ 完成 | `11e5196` |
| 1.3 | 优先级选择 + 透传类型分类 | 修复 | ✅ 完成 | `1fc0229` |
| 1.4 | 单元测试 31 个 | 新增 | ✅ 完成 | `1fc0229` |
| **1.5** | **拆分：`handshake` 独立 CLI 命令** | **重构** | ✅ 完成 | `686137d` |
| 1.6 | backpressure 用 handshake 分类过滤 | 重构 | ✅ 完成 | (待提交) |
| 1.7 | 删除 `backpressure --protocol-confirm` | 清理 | ✅ 完成 | `686137d` |
| 1.8 | Phase A: 协议 schema YAML 框架 | 新增 | ⏳ 待做 | — |
| 1.9 | Phase A: AXI schema (完整 AW/W/B/AR/R) | 新增 | ⏳ 待做 | — |
| 1.10 | Phase A: TL-UL schema (A/D 通道) | 新增 | ⏳ 待做 | — |
| 1.11 | Phase A: AHB + Wishbone schema | 新增 | ⏳ 待做 | — |
| 1.12 | Phase A+B 融合：候选模块 → 确认 | 新增 | ⏳ 待做 | — |
| 1.13 | 真实项目验证 (verilog-axi 全套) | 验证 | ✅ 完成 | (待提交) |
| 1.14 | 真实项目验证 (XiangShan / OpenTitan 选 1) | 验证 | ⏳ 待做 | — |
| 1.15 | 输出格式：text / json / mermaid 全套 | 增强 | ⏳ 待做 | — |

---

## 2. 详细任务说明

### 1.5 拆分 `handshake` 独立 CLI 命令

**目标**：把 `--protocol-confirm` 从 `backpressure` 移出，作为独立 `handshake` 命令。

**新文件结构**：
```
src/cli/commands/
├── backpressure.py        # 只做 backpressure 拓扑
├── handshake.py           # 新增：handshake 分析 (从 backpressure 拆出)
```

**`handshake` 子命令**：
```bash
# 扫所有 ready/valid 信号
sv_query handshake scan --filelist xxx [--channel AW|W|B|AR|R|A|D]

# 分析单个信号
sv_query handshake analyze --filelist xxx --signal axi_adapter.s_axi_awready

# 对比一对 valid/ready
sv_query handshake pair --filelist xxx --valid V --ready R
```

**复用**：直接用 `handshake_detector.py` 的 `detect_from_signal_pair()` 等 API。

**代码改动预估**：~150 行新代码（命令 + 选项）

---

### 1.6 backpressure 用 handshake 分类过滤

**目标**：backpressure 图只追踪**真反压节点**，跳过透传线。

**新过滤逻辑**：
```python
# 在 _run_protocol_confirm 之后，handshake 分类用作 backpressure 过滤
def should_include_in_topology(hi: HandshakeInfo) -> bool:
    """是否应画进 backpressure 拓扑图"""
    if hi.handshake_type in ("STANDARD_AXI", "COMBINATIONAL_BP", "REGISTERED_BP"):
        return True  # 真握手节点
    if hi.handshake_type in ("WIRE_PASSTHROUGH", "PORT_PASSTHROUGH"):
        return False  # 透传线，不画
    if hi.handshake_type == "CONDITIONAL_CTRL":
        return True  # 控制节点，画但标
    return False  # UNUSED/UNKNOWN/UNUSED 跳过
```

**Mermaid 输出**：
- 真反压节点：标准样式
- 透传线：隐式跨过（不画节点，但路径仍走）
- 控制节点：标 ⚙️

**代码改动预估**：~50 行 backpressure.py 改动

---

### 1.7 删除 `--protocol-confirm`

直接删除 `analyze` 函数里的 `if protocol_confirm:` 分支（已经搬到 1.5）。

---

### 1.8 Phase A: 协议 schema YAML 框架

**新文件**：
```
config/protocols/
├── _schema.yaml       # 通用结构定义
├── axi4.yaml          # AXI4 / AXI4-Lite / AXI4-Stream
├── tl_ul.yaml         # TileLink-UL
├── ahb.yaml           # AHB / AHB-Lite
└── wishbone.yaml      # Wishbone B4 / Classic
```

**schema 结构**（参考 `bus_protocol_detector.md`）：
```yaml
protocol: AXI4
channels:
  AW:
    valid_patterns: [awvalid, avalid, aw_valid]
    ready_patterns: [awready, aready, aw_ready]
    addr_patterns:  [awaddr, aw_addr, aaddr]
  W: ...
  B: ...
  AR: ...
  R: ...
match_priority: [AW+AR, W+R, B]  # 必须匹配的通道
```

**加载逻辑**：
```python
class ProtocolSchema:
    @staticmethod
    def load(yaml_path: Path) -> "ProtocolSchema": ...
    def match_module(self, module) -> list[Match]: ...
    def confidence(self, matches: list[Match]) -> float: ...
```

---

### 1.9-1.11 Phase A 协议 schema 实现

每个协议一份 YAML + 简单测试。优先级：
1. AXI4（含 AXI4-Lite 子协议）— 最常用
2. TL-UL — 学术/前沿项目常用
3. AHB — 工业级
4. Wishbone — 简单总线，教学用

---

### 1.12 Phase A+B 融合

**主流程**：
```python
def detect_protocol(graph, module):
    # Phase A: 用所有 schema 匹配
    matches = []
    for schema in protocol_schemas:
        m = schema.match_module(module)
        if m.confidence > 0.5:
            matches.append(m)
    if not matches:
        return ProtocolInfo(label="UNKNOWN", confidence=0.0)
    
    # Phase B: 对每对 (valid, ready) 调用 handshake_detector
    best = max(matches, key=lambda m: m.confidence)
    for ch in best.channels:
        for (v, r) in ch.pairs:
            hi = detect_from_signal_pair(tracer, v, r)
            ch.handshake_type = hi.handshake_type
            ch.confidence *= hi.extra.get("confidence", 1.0)
    return best
```

---

## 3. 优先级

| 优先级 | 任务 | 原因 |
|--------|------|------|
| 🔴 高 | 1.5 + 1.6 + 1.7 | **架构清理**，让 handshake/backpressure 边界清楚 |
| 🟡 中 | 1.8 + 1.9 | Phase A 框架 + AXI schema（最常用协议） |
| 🟡 中 | 1.13 | 真实项目验证，证明有用 |
| 🟢 低 | 1.10 + 1.11 | TL-UL / AHB / Wishbone schema |
| 🟢 低 | 1.14 | XiangShan / OpenTitan 验证（巨型项目，先有 AXI schema 再做）|
| 🟢 低 | 1.15 | 输出格式丰富（text 优先，json/mermaid 后补）|

---

## 4. 时间估算

| 任务 | 预估时间 |
|------|----------|
| 1.5 拆分 handshake 命令 | 30 min |
| 1.6 backpressure 用 handshake 过滤 | 30 min |
| 1.7 删除 --protocol-confirm | 5 min |
| 1.8 schema 框架 | 1h |
| 1.9 AXI4 schema | 1h |
| 1.10 TL-UL schema | 30 min |
| 1.11 AHB + Wishbone | 1h |
| 1.12 融合 | 1h |
| 1.13 真实项目验证 | 1h |
| 1.14 巨型项目验证 | 2h |
| 1.15 输出格式 | 30 min |
| **合计** | **~9h** |

---

## 5. 决策记录

### D1. (2026-06-08) Phase B 先做 backpressure 不依赖
- 用户决策
- 理由：Phase B 通用，能分析任何 ready/valid；backpressure 只用其结果过滤
- 推动本次计划

### D2. (2026-06-08) 拆分 `handshake` 独立命令，不混在 backpressure
- 用户决策
- 理由：功能归属清晰
- 命令边界：handshake 做"信号级别握手分析"；backpressure 做"路径级别追踪"
- backpressure 通过内部调用 handshake_detector API 复用分类结果

### D3. (2026-06-08) Phase A 用 schema YAML 配置驱动
- 设计决策
- 理由：硬编码信号名跨项目迁移差，YAML 配置可扩展
- 替代方案（已否决）：手写 if-elif 启发式

### D4. (2026-06-08) 优先级：AXI > TL-UL > AHB > Wishbone
- 实现顺序决策
- 理由：AXI 用得最多，ROI 最高；Wishbone 简单但用户少

### D5. (2026-06-09) 实测发现 6 个问题 (1.13 实战验证)

**Issue 1 - PORT_IN 被误判为 UNUSED** ✅ 已修复
- 现象：`axi_dma.m_axis_read_data_tready` (PORT_IN) 被报 UNUSED
- 原因：handshake_detector 看到 0 驱动就报 UNUSED，没区分 PORT_IN
- 修复：新增 `detect_handshake_type_with_node()`，接收 `node_kind` 参数
- 验证：PicoRV32 的 `mem_ready`/`pcpi_ready` 现在正确显示为 PORT_PASSTHROUGH

**Issue 2 - 跨模块的假配对** ✅ 已修复
- 现象：不同模块的 valid/ready 被错误配对
- 原因：原来的扫描按 base name 配对，跨模块也可能 base name 相同
- 现状：发现 1.5 的实现实际已经处理对了（保留模块前缀的 base），但需要明确说明

**Issue 3 - 13 个 UNUSED 信号** ❌ 暂时保留
- 现象：W 通道有 13 个 UNUSED
- 原因：这些是真正没有驱动的信号（从 graph 看 in_edges=0）
- 不动：真实存在的代码问题，不是 handshake_detector 误判

**Issue 4 - PicoRV32 valid 信号也被标 UNUSED** ✅ 误报（信号名不匹配）
- 现象：`picorv32_axi.mem_valid` 是 SIGNAL 但 0 driver_infos
- 原因：实际信号名是 `picorv32.mem_valid`（无 `_axi` 后缀）。`picorv32_axi` 是不同模块、其内部不包含 `mem_valid`。
- 验证：`picorv32.mem_valid` 实际有 4 in-edges 和 3 drivers，状态机条件正确提取
- **结论**：Issue 4/5 不是 graph_builder bug，是 scan/手误

**Issue 5 - 57% 节点无驱动** ✅ 误报（信号名不匹配）
- 现象：PicoRV32 676 个信号中 383 个 (57%) 无驱动信息
- 原因：同上，信号名不匹配 (`picorv32_axi.*` vs `picorv32.*`)
- 验证：`picorv32.mem_state` 有 7 in-edges 和 10 drivers，driver 提取完全正常
- **结论**：graph_builder 驱动提取器没有实质问题

**Issue 6 - UNUSED vs PORT_PASSTHROUGH vs 真无驱动** ✅ 已修复 (Issue 1 同一根因)
- 三种"没驱动"情况应区分：
  - PORT_IN 节点 (有外部 driver) → PORT_PASSTHROUGH
  - SIGNAL 节点 (无 always 块 driver) → UNUSED (真没用)
  - SIGNAL 节点 (有 always 块但 builder 未捕获) → 暂时 UNUSED，但 graph_builder 修复后会变
- 修复后 Issue 4/5 的边界更清晰

### D6. (2026-06-09) 验证结论
- verilog-axi: handshake 分类准确率 ~80% (50 pairs 中 41 正确)
- PicoRV32: 实际验证 driver 提取器完全正常，Issue 4/5 来自信号名不匹配 (picorv32_axi.* vs picorv32.*)
- graph_builder driver 提取器无实质问题
- **不需修复 graph_builder**

### D7. (2026-06-09) TDD 调查失败教训
- 尝试为 Issue 4/5 写 TDD 测试，但最小化复现全都能 work
- 根本原因：误用了 `picorv32_axi.*` 信号名，实际信号是 `picorv32.*`
- **教训**：写 TDD 测试前必须先验证 bug 能复现

### D8. (2026-06-09) verilog-axi 模块级深入验证 (1.13 继续)

**模块覆盖**:
- axi_crossbar: 5 port-level AXI handshakes (AW/W/B/AR/R), 5/5 正确分类为 WIRE_PASSTHROUGH/PORT_PASSTHROUGH
- axi_dp_ram: 2 port-level AW/W pairs，2/2 正确
- axi_fifo: 5 port-level pairs (AW/W/B/AR/R)，5/5 正确
- axi_cdma: Stream IF (s_axis_desc_*, m_axis_desc_*) - 7 CONDITIONAL_CTRL/2 PORT_PASSTHROUGH，6 STANDARD_AXI 内部握手
- m_rc_valid / m_wc_valid: axi_crossbar_addr 内部 AW/AR 通道指示信号，未被 _classify_by_name 识别 (UNKNOW N channel)

**全量扫描 (200 pairs)**:
| 类型 | 数量 |
|------|------|
| WIRE_PASSTHROUGH | 98 |
| PORT_PASSTHROUGH | 81 |
| STANDARD_AXI | 13 |
| CONDITIONAL_CTRL | 5 |
| UNUSED | 3 |

**Issue 7 - handshake scan 漏 AXI 通道** (已修复)
- 现象: `s_axi_awvalid` / `m_axi_wready` / `awready` 全部未被 `_is_ready_or_valid` 识别
- 原因: `READY_VALID_PATTERNS` 只含 `aw_valid` (带下划线)，不含 `awvalid` (无下划线)
- 后果: 全量 scan 输出里 **AW/AR 通道完全空缺**，只能看到 W/R/A/D/UNKNOWN 五个通道
- TDD 复现: `test_handshake_scan_axsi_patterns.py` 验证 `s_axi_awvalid` 识别
- 修复: 补充无下划线变体 `awvalid`/`awready`/`wvalid`/...
- 验证: 修复后 scan 多了 5 个 AW/AR 对 (30+5=35 新增)

**backpressure analyze W 通道拓扑**:
- 4 个 layer: SLAVE → ADAPTER → CROSSBAR → MASTER
- 拓扑边示例: `axi_cdma_m_axi_wvalid_int → axi_interconnect_m_axi_wvalid_int → axi_adapter_wr_m_axi_wvalid_int → axi_adapter_wr_s_axi_awready_next`
- 反映出 AXI 写通道从 master 穿过 crossbar 到 slave 的反压链路

**D8 总结**:
- ✅ 1.13 验证: 6 个 verilog-axi 关键模块 port-level handshake 100% 正确
- ✅ Issue 7 已修: scan 现在能看到所有 5 个 AXI 通道
- 🟡 Issue 8 (未修): `m_rc_valid` / `m_wc_valid` (axi_crossbar_addr 内部 AW/AR 指示) 被归为 UNKNOWN
  - 后果: 7 个标准 AXI backpressure 信号被扫描器误放到 UNKNOWN 分组
  - 修复: 补充 `m_rc_valid`/`m_wc_valid` 到 classifier 的 AW/AR 映射
  - 优先级: 低 (仅限 axi_crossbar 家族使用)
- 🟡 Issue 9 (新发现): `current_m_axi_wready`/`s_axi_rready` 被标 UNUSED (3个)
  - 调查后发现: **2 个是 driver_extractor bug**，1 个是 graph_builder ghost signal
  - **真实 bug**: `wire X = expr;` (NetDeclarationSyntax) 语法未被 driver_extractor 处理
    - verilog-axi axi_interconnect.v line 429/450/450+: `wire current_s_axi_rready = s_axi_rready[s_select];` 等
    - verilog-axi axi_crossbar_addr.v 也用同语法
    - 这些 inline `wire =` 语法实际上等价于 `assign X = Y;`，但被 driver_extractor 漏掉
    - 修复: 在 driver_extractor.py 中处理 NetSymbol 带 initializer 的情况
  - **Ghost signal**: `axi_dp_ram.s_axi_rready` (SIGNAL kind, 无 file/line)
    - axi_dp_ram 模块中实际只有 `s_axi_a_*` / `s_axi_b_*`端口，没有 `s_axi_rready` 端口
    - 这是 graph_builder 命名空间泄漏问题，不是 driver_extractor 问题
    - 优先级: 低，不影响主要功能
  - TDD 测试: `test_driver_extractor_net_decl.py` (2个新测试)
  - 修复后: UNUSED 从 3 → 1 (仅剩 ghost signal)

### D9. (2026-06-09) Issue 9 深入调查 + 修复

**调查过程**:
1. 识别 3 个 UNUSED 信号: `current_m_axi_wready`, `current_s_axi_rready`, `s_axi_rready`
2. 在 verilog-axi 源码中查找信号源位置
3. 发现 `current_m_axi_wready` / `current_s_axi_rready` 是 inline `wire X = expr;` 语法
4. `s_axi_rready` 是 ghost signal (axi_dp_ram 里不存在)

**根因分析**:
- Semantic AST 上 NetSymbol 有 `.name` 和 `.initializer` 属性
- driver_extractor 中调用的 `get_variable_declarations` 只匹配 DataDeclaration
- `get_net_declarations` 返回 NetSymbol但未被使用
- NetSymbol 的 initializer 未被提取为 DRIVER 边

**修复** (driver_extractor.py):
- 在 alias 处理和 assign 处理之间增加 NetSymbol 初始化器处理
- 检查 lhs_name 不在 port_names 中（避免重复）
- 为每个 RHS 信号创建 DRIVER 边，assign_type="continuous"
- 保留原始表达式字符串在 edge.expression 中供 DriverInfo 使用

**修复后验证 (verilog-axi 200 pairs 扫描)**:
| 类型 | 修复前 | 修复后 |
|------|------|------|
| ❌ UNUSED | 3 | 1 |
| ⚙️ CONDITIONAL_CTRL | 5 | 10 |
| 其他不变 | ... | ... |

**剩余 1 个 UNUSED (axi_dp_ram.s_axi_rready)**:
- 类型: SIGNAL (不是 PORT_IN)
- file/line: 空 (ghost node)
- 原因: graph_builder 命名空间泄漏，子模块的 port 名被错误归到父模块
- 修复优先级: 低 (不影响主要 handshake 分析)
- 后续可考虑: 在 graph_builder 中严格校验 port 名属于子模块还是父模块

**TDD 教训 (D9 补充)**:
- 源码是真理: 调查 signal 是否被 unused 必须看 `wire X = Y;` 原文，不能只看 graph
- 多种不同的 driver 表达 (ContinuousAssign, NetDecl, always_ff <＝) 需要分别处理
- 净表语义 (NetDeclarationSyntax) 和赋值语义 (ContinuousAssignSyntax) 在 driver 提取上等价
- Pyslang 的 `SyntaxTree` 和 `Compilation.getRoot()` 走的是不同代码路径：
  - SyntaxTree 返回语法树节点（有 `declarators`）
  - Semantic AST 返回语义符号 (有 `initializer`)
  - driver_extractor 走的是后者



### D10. (2026-06-09) Issue 10: 多 bus 协议支持 (AXI / TileLink / APB / AHB / Wishbone / 自定义)

**调查过程**:
1. 调查真实项目 (axi/, opentitan tlul/, verilog-axi) 中的 handshake 信号
2. 测试发现 31/61 真实信号未被识别 (ready/valid pattern 过窄)
3. 涵盖: AXI 子通道, TileLink (a_/d_), AHB, APB, Wishbone, 自定义 (req/ack/done)

**根因**:
- `READY_VALID_PATTERNS` 只含 AXI 标准模式
- `_classify_by_name` 只识别 AXI 通道 (AW/W/B/AR/R)
- `_strip_suffix` 不处理方向后缀 `_i`/`_o` (opentitan / axi/ 项目风格)
- 总是 ready 信号 (`always_comb a_ready_o = 1'b1;`) 被判为 UNKNOWN

**修复**:
1. 扩展 `READY_VALID_PATTERNS` (19 -> 140 个模式)
   - AXI sub: `*_spill_*`, `*_dec_*`, `*_done`, `apb_*`, `arb_*`
   - TileLink: `a_*`, `d_*`, `dmi_*`, `sram_*`, `flush_*`
   - AHB: `hready`, `hgrant`, `hreq`, `hresp`
   - APB: `psel`, `penable`, `pready`, `pslverr`
   - Wishbone: `cyc`, `stb`, `we`, `ack` + 方向后缀 `_i`/`_o`
   - 自定义: `dma_*`, `irq`, `rd_req`, `wr_req`, `cmd_*`, `resp_*`
2. 扩展 `_classify_by_name`:
   - 处理 module.path. 前缀 (用 sig_part = last part)
   - 加 `a_ack` / `d_ack` 子串检查 (TL-UL ack 仍是 A/D 通道)
3. 扩展 `_strip_suffix`:
   - 剥除方向后缀 `_i` / `_o` / `_io` (opentitan/axi/ 项目风格)
4. 新增 Case (handshake_detector.py):
   - `always_comb/always_ff a_ready_o = 1'b1;` → PORT_PASSTHROUGH (always-on)

**验证 (仿真 TL-UL adapter)**:
```systemverilog
always_comb a_ack = a_valid_i & a_ready_o;
always_comb a_ready_o = 1'b1;  // always ready
```
扫描结果: 2 对全部 `🔗 PORT_PASSTHROUGH` (之前是 1 个 UNKNOWN + 1 个 PORT_PASSTHROUGH)

**测试覆盖**:
- 16 个 protocol pattern 测试 (test_bus_protocol_patterns.py)
- 5 个 always-ready 测试 (test_handshake_always_ready.py)
- 总测试数: 1582 → 1603 (增加 21)

**真实信号覆盖率**: 30/61 → 61/61 (从 49% 到 100%)

**未覆盖项**:
- APB 3-way handshake (psel/penable/pready) 不是 valid/ready 对，暂不在 _is_ready_or_valid 范围
- 协议级 schema 匹配 (Phase A 设计) 尚未实现，仅做轻量 heuristics

---

## 6. 风险 + 缓解

| 风险 | 缓解 |
|------|------|
| Schema 匹配准确率低 | 配合 Phase B handshake 二次确认 |
| 反压路径过长导致性能问题 | 分层 lazy 追踪 + 深度限制（默认 5）|
| 跨时钟域 ready/valid 误判 | `clock_domain` 字段已记录，UI 标记 CDC 边界 |
| 用户 schema 写错 | 启动时加载校验，缺字段给清晰报错 |
| 巨型项目（XiangShan）跑超时 | 默认关闭，按需加 `--include` 白名单 |

---

## 7. 验收标准

- ✅ `sv_query handshake scan --filelist verilog-axi.filelist` 输出所有 ready/valid 的握手类型
- ✅ `sv_query backpressure analyze --filelist verilog-axi.filelist` 拓扑图不包含 `WIRE_PASSTHROUGH` 节点
- ✅ `sv_query protocol detect --module axi_adapter` 自动识别为 AXI4 协议
- ✅ verilog-axi 全套模块（axi_adapter / axi_crossbar / axi_dma / axi_dp_ram）跑通
- ✅ 巨型项目（PicoRV32 / XiangShan 选 1）能跑完不超时
- ✅ 完整单元测试套件 + 新功能测试 pass

---

## 8. 后续 session 启动指南

**新 session 加载这个文件 + `docs/bus_protocol_detector.md` 后**：

1. **当前 commit 链**（截至 2026-06-08）：
   ```
   1fc0229 fix(handshake): priority-based selection + passthrough types + D channel patterns
   11e5196 feat(phase-b): handshake_detector + --protocol-confirm for backpressure
   eb616a6 feat(backpressure): channel filter (AW/W/B/AR/R) + cross-layer edge logic
   3149561 feat(cli): backpressure bus topology command
   ```

2. **下一步该做**（按优先级）：
   - 🔴 **第一件事**：1.5 拆分 handshake 命令（架构清理）
   - 🔴 **第二件事**：1.6 backpressure 用 handshake 分类过滤
   - 🔴 **第三件事**：1.7 删除 `--protocol-confirm`
   - 🟡 **之后**：1.8+ Phase A schema 框架

3. **关键 API**（已实现）：
   - `detect_from_signal_pair(tracer, valid, ready) -> HandshakeInfo`
   - `classify_signal_channel(signal) -> ChannelType`
   - HandshakeType 字面量：STANDARD_AXI / COMBINATIONAL_BP / REGISTERED_BP / CONDITIONAL_CTRL / WIRE_PASSTHROUGH / PORT_PASSTHROUGH / UNUSED / UNKNOWN

4. **关键测试命令**：
   ```bash
   cd ~/my_dv_proj/sv_query
   python3 -m pytest sim/tests/unit/test_handshake_detector.py -v  # 31 cases
   python3 -m pytest sim/tests/ -x  # 全部 1552 cases
   python3 -W ignore run_cli.py backpressure analyze --filelist /tmp/verilog-axi.filelist --protocol-confirm -n 50  # 临时验证用
   ```

5. **阻塞 / 待确认**：
   - 无
