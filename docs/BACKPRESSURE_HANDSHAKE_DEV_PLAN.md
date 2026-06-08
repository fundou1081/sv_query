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
| 1.13 | 真实项目验证 (verilog-axi 全套) | 验证 | ⏳ 待做 | — |
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
