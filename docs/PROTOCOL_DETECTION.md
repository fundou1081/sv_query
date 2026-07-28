# Protocol Detection (Phase A) — Implementation Plan

## 1. 目标 (Goal)

**核心**: 不依赖变量名, 通过**关键信号 (key signals) + 语义匹配 (semantic matching)** 自动识别模块的 bus 协议 (AXI4 / TL-UL / AHB / APB / Wishbone / 自定义)。

**反命题**: 不是"匹配字符串 `awvalid`", 而是"找到 1bit output + 1bit input 在 if 里共现的握手对"。

**Success Criteria**:
- 90% 准确率 (真实项目: verilog-axi / opentitan / picorv32)
- 0 误报 (宁可 UNKNOWN, 不乱猜)
- < 50ms/模块 (不需要 LLM)
- **零配置可用** (无 YAML 也能识别"有 5 个握手对"是 AXI)
- YAML 只用于**变体判定** (AXI4_FULL vs AXI4_LITE) 和**名字 hint 加分**

---

## 2. 架构 (Architecture)

```
                                    ┌──────────────────┐
                                    │  Module (AST)    │
                                    └────────┬─────────┘
                                             ↓
                          ┌─────────────────────────────────┐
                          │   RoleDetector (Session 1)      │
                          │   - 找 valid/ready/payload 候选  │
                          │   - 基于 width + direction      │
                          └────────────────┬────────────────┘
                                           ↓
                          ┌─────────────────────────────────┐
                          │   PairFinder (Session 2)         │
                          │   - 找 valid+ready 配对          │
                          │   - 基于 co-occurrence in if     │
                          └────────────────┬────────────────┘
                                           ↓
                          ┌─────────────────────────────────┐
                          │   ProtocolMatcher (Session 3)    │
                          │   - 用协议模板匹配 (role 模板)  │
                          │   - YAML 提供 变体判定 + hint    │
                          └────────────────┬────────────────┘
                                           ↓
                                    ProtocolMatch
                          (protocol, variant, confidence, signals)
```

**关键设计原则**:
1. **下层不依赖上层** — RoleDetector 完全靠 port 特征, 无 YAML 无 graph
2. **每层独立可测** — 每层都有清晰的输入输出和单测
3. **失败优雅降级** — 任何一层失败, 上一层的 best-effort 结果仍然有用

---

## 3. 关键设计 (Key Design Decisions)

### 3.1 角色定义 (Role)

| Role | Width | Direction | 用途 |
|------|-------|-----------|------|
| `valid` | 1 | output (master) / input (slave) | 源主动信号 (valid/req/ack) |
| `ready` | 1 | input (master) / output (slave) | 宿响应信号 (ready/ack/stall) |
| `addr` | ≥ 8 | output | 地址/请求 payload |
| `data` | ≥ 8 | output (W) / input (R) | 数据 payload |
| `ctrl` | 2-8 | output | 控制信号 (len/size/burst/id) |
| `strb` | =data/8 | output | strobe (W 通道) |
| `resp` | 1-4 | input/output | 响应码 (bresp/rresp) |
| `last` | 1 | output | 突发结束标志 (W/R 通道) |

### 3.2 三层判定 (3-Layer Decision)

```
Layer 1 (硬性):  width + direction
    - 1bit output  → 候选 valid
    - 1bit input   → 候选 ready
    - wide output  → 候选 addr/data

Layer 2 (软性):  名字 hint (YAML 可选)
    - 命中 "valid/awvalid/wvalid" → +0.3
    - 命中 "ready/awready/wready" → +0.3
    - 命中 "addr/awaddr/araddr"   → +0.2

Layer 3 (关系):  co-occurrence
    - 与配对信号在 if/always 共现 → +0.4
    - 多个信号同时翻转           → +0.2
```

### 3.3 协议模板 (Protocol Template)

```yaml
# config/protocols/axi4.yaml
protocol: AXI4

# 关键信号模板 (用 ROLE 定义, 不靠名字)
template:
  - channel: AW
    roles_required: [valid, ready, addr]
    roles_valid:    { dir_out: [valid, addr], dir_in: [ready] }
  - channel: W
    roles_required: [valid, ready, data]
  - channel: B
    roles_valid:    { dir_in: [valid], dir_out: [ready] }  # 方向反转
  - channel: AR
    roles_required: [valid, ready, addr]
  - channel: R
    roles_valid:    { dir_in: [valid, data], dir_out: [ready] }

# 名字 hint (辅助, 命中加分)
hints:
  AW:
    valid: [awvalid, aw_valid, avalid]
    ready: [awready, aw_ready, aready]
    addr:  [awaddr, aw_addr, aaddr]

# 变体判定 (靠"缺什么信号"判定)
variants:
  AXI4_FULL:    { needs: { AW: [len, size, burst] } }
  AXI4_LITE:    { needs_absent: { AW: [len, size, burst] } }
```

### 3.4 评分公式 (Scoring)

```
protocol_score = (
    0.40 * pair_coverage      # 找到多少对必需握手
  + 0.25 * role_classification # 候选 role 分类准确度
  + 0.20 * name_hint_match    # 名字 hint 命中
  + 0.15 * structural_purity   # 配对结构清晰度
)
```

**Pair coverage**: `找到的有效配对数 / 协议要求的最小配对数`
**Role classification**: 候选 role 分类的 confidence 平均值
**Name hint match**: 候选信号的"标准名"匹配率 (用于 AXI4_FULL/Lite 变体)
**Structural purity**: 配对是否能组成"对称结构" (例如 valid+addr+id 都来自 master)

---

## 4. Session 分解 (Session Breakdown)

### Session 1: Role Detection (基础: 角色候选)

**目标**: 给一个模块, 找出所有可能的 `valid`/`ready`/`addr`/`data` 候选

**新增文件**:
- `src/trace/core/protocol/__init__.py`
- `src/trace/core/protocol/role_detector.py` (~150 行)
- `sim/tests/unit/test_role_detector.py` (~20 测试)

**核心 API**:
```python
class RoleCandidate:
    signal: str
    role: str              # 'valid' / 'ready' / 'addr' / 'data' / 'ctrl' / 'strb' / 'last' / 'resp' / 'unknown'
    confidence: float      # 0.0-1.0
    reasons: list[str]     # 为什么判定这个 role

def find_role_candidates(module) -> dict[str, list[RoleCandidate]]:
    """返回 {role: [candidates]}"""
    # 基于 port width + direction + (可选) 名字 hint
    # 不需要 AST 解析, 只看 port list
```

**输入**: Module with port list
**输出**: 候选信号分组

**测试**:
- 简单模块: 只有 valid/ready 配对
- AXI 风格: 5 个通道, 每个有 valid+ready+addr/data
- 反向: B/R 通道 valid 是 input, ready 是 output
- 边界: 0 个候选、1 个候选、几十个候选
- 反例: clock/reset 不被误判为 ready

**预计**: 150-200 行 Python + 100 行测试

---

### Session 2: Pair Discovery (配对发现)

**目标**: 在 role 候选的基础上, 找出真正配对的 valid+ready

**新增文件**:
- `src/trace/core/protocol/pair_finder.py` (~200 行)
- `sim/tests/unit/test_pair_finder.py` (~15 测试)

**核心 API**:
```python
@dataclass
class HandshakePair:
    valid_sig: RoleCandidate
    ready_sig: RoleCandidate
    confidence: float      # 配对置信度
    co_occurrence_count: int  # 在 if/always 里一起出现的次数
    same_clock: bool
    reasons: list[str]

def find_handshake_pairs(module, role_candidates) -> list[HandshakePair]:
    """
    找所有可能的 (valid, ready) 配对
    算法:
      1. 对每个 valid 候选 × ready 候选, 计算 co-occurrence
      2. 同 cycle 翻转 +0.3
      3. 同 if 条件 +0.4
      4. 同 always 块 +0.2
      5. 名字成对 (前后缀一致) +0.1
    """
```

**关键创新**: 用 graph_builder 现有图找 co-occurrence!
```python
# 已有 graph_builder 提供:
# - sig_a --> sig_b 表示 sig_b 依赖 sig_a
# - sig_a --> sig_b 在同一个 if 里出现过
```

**测试**:
- 简单配对: 1 个 valid + 1 个 ready
- 多配对: AXI 5 个通道
- 不配对: clock + reset (必须不配)
- 部分配对: 只有 W 通道, 缺其他
- 假配对: 名字像但实际不相关

**预计**: 200-250 行 Python + 150 行测试

---

### Session 3: Protocol Template Matching (协议模板匹配)

**目标**: 把找到的配对映射到协议 (AXI4 / TL-UL / AHB / APB / Wishbone / 自定义)

**新增文件**:
- `config/protocols/axi4.yaml`
- `config/protocols/axi4_lite.yaml`
- `config/protocols/tlul.yaml`
- `config/protocols/ahb.yaml`
- `config/protocols/apb.yaml`
- `src/trace/core/protocol/schema.py` (~100 行, YAML 加载)
- `src/trace/core/protocol/matcher.py` (~250 行, 模板匹配)
- `sim/tests/unit/test_protocol_matcher.py` (~15 测试)

**核心 API**:
```python
@dataclass
class ProtocolMatch:
    protocol: str            # "AXI4" / "TLUL" / "AHB" / "APB" / "WISHBONE" / "CUSTOM"
    variant: str | None      # "AXI4_FULL" / "AXI4_LITE" / None
    confidence: float        # 0.0-1.0
    channels: dict[str, ChannelMatch]
    matched_pairs: list[HandshakePair]
    unmatched_signals: list[str]
    warnings: list[str]

def match_protocol(module, pairs) -> list[ProtocolMatch]:
    """
    返回所有候选协议 (按 confidence 降序)
    """
    matches = []
    for schema in load_all_schemas():
        m = score_module_against_schema(module, pairs, schema)
        if m.confidence > 0.3:
            matches.append(m)
    return sorted(matches, key=lambda m: -m.confidence)
```

**YAML 加载**:
```python
@dataclass
class ProtocolTemplate:
    name: str
    required_channels: list[ChannelSpec]
    hints: dict[str, dict[str, list[str]]]
    variants: dict[str, VariantSpec]
    
    @classmethod
    def load_from_yaml(cls, path: str) -> 'ProtocolTemplate': ...
```

**测试**:
- 单个 AXI4 master: 5 通道, 全配对
- AXI4 slave: 方向相反
- AXI4-Lite: 缺 len/size/burst
- APB master: psel/penable/pready 3-way
- TL-UL: a_valid/a_ready/a_opcode
- 不匹配的模块: 自定义协议
- 多协议候选: 同时像 AXI 又像 TL-UL

**预计**: 100 行 YAML × 5 + 350 行 Python + 200 行测试

---

### Session 4: CLI Integration (CLI 集成)

**目标**: `sv_query protocol detect` 命令可用

**新增文件**:
- `src/cli/commands/protocol.py` (~150 行)
- `sim/tests/unit/test_protocol_cli.py` (~10 测试)

**CLI 接口**:
```bash
# 单模块检测
sv_query protocol detect --module axi_adapter
sv_query protocol detect -f top.sv --module axi_adapter

# 全项目扫描
sv_query protocol scan --filelist verilog-axi.filelist
sv_query protocol scan -f top.sv

# 输出格式
sv_query protocol detect --module axi_adapter --format json
sv_query protocol detect --module axi_adapter --format mermaid
```

**输出**:
```
✓ Protocol Detection Results
  Module: axi_adapter
  Protocol: AXI4
  Variant: AXI4_FULL
  Confidence: 0.92

  Channels:
    ✅ AW  valid=awvalid  ready=awready  addr=awaddr  ctrl=[awid,awlen,awsize,awburst]
    ✅ W   valid=wvalid   ready=wready   data=wdata   ctrl=[wstrb,wlast]
    ✅ B   valid=bvalid   ready=bready   resp=bresp
    ✅ AR  valid=arvalid  ready=arready  addr=araddr  ctrl=[arid,arlen,arsize,arburst]
    ✅ R   valid=rvalid   ready=rready   data=rdata   resp=rresp   ctrl=[rlast]

  Warnings: none
```

**预计**: 200 行 Python + 100 行测试

---

### Session 5: 真实项目验证 (Real Project Validation)

**目标**: 跑通 verilog-axi / picorv32 / opentitan, 调参

**测试项目**:
1. `verilog-axi/axi_adapter.v` — 简单 AXI 适配器
2. `verilog-axi/axi_crossbar.v` — 复杂 crossbar
3. `picorv32/picorv32.v` — Wishbone 风格 (内嵌)
4. `opentitan/hw/ip/tlul/rtl/tlul_*.sv` — TileLink UL

**调参维度**:
- 配对 co-occurrence 阈值
- 名字 hint 命中权重
- 置信度 cutoff (低于此报 UNKNOWN)
- 误报过滤 (例如 clk/reset 永远不是 ready)

**成功标准**:
- 4 个项目都跑通
- 0 误报 (clock/reset/data 不被错认为 ready)
- 真实 AXI 模块置信度 ≥ 0.85

**预计**: 主要是测试和调参, 约 100-200 行新代码

---

### Session 6: LLM 增强 (Optional, 视需要)

**触发条件**: 置信度 < 0.5
**用途**: LLM 给"建议 + 解释", 不参与判定
**实现**: 缓存 + 节流, 每个模块最多 1 次 LLM 调用

```python
if match.confidence < 0.5:
    llm_suggestion = ask_llm(f"Module {name} has these ports: ... What protocol?")
    match.llm_suggestion = llm_suggestion
    match.warnings.append("Low confidence, LLM suggests: " + llm_suggestion)
```

**预计**: 100 行 Python, 后续按需

---

## 5. 风险与缓解 (Risks & Mitigation)

| # | 风险 | 缓解 |
|---|------|------|
| 1 | co-occurrence 太宽松 → 误配对 (e.g. irq + ack) | 加 same_clock + same_always_block 约束 |
| 2 | clock/reset 被误判为 ready | 排除 known 1bit signals (clk, rst, nRst, irq) |
| 3 | 跨模块的 valid/ready 误配 | 配对限制在同一模块内, 或显式跨模块信号 |
| 4 | generate block / 数组信号 | Session 5 调参处理, 暂只支持一维数组 |
| 5 | packed struct 字段 | Session 5 调参处理, 让 graph_builder 先展开 struct |
| 6 | APB 3-way handshake (psel/penable/pready) | Session 3 单独写 APB 模板, 用 3 信号模板而非 2 信号 |
| 7 | Wishbone 风格 (cyc/stb/we/ack) | Session 3 单独模板 |
| 8 | Parameterized 宽度 (e.g. ADDR_WIDTH = 32) | 跳过 parameter 化宽度的精确判断, 用 `>= 8` 即可 |

---

## 6. 与现有代码的集成 (Integration)

**复用现有**:
- `graph_builder.build()` — 已建好的信号图
- `trace_fanin_detailed()` — 驱动链分析
- `handshake_detector` — 现有握手分类 (Phase B 验证)
- `UnifiedTracer` — 文件加载

**新增模块路径**:
```
src/trace/core/protocol/
    __init__.py
    role_detector.py      # Session 1
    pair_finder.py        # Session 2
    schema.py             # Session 3
    matcher.py            # Session 3
```

**YAML 路径**:
```
config/protocols/
    axi4.yaml             # Session 3
    axi4_lite.yaml        # Session 3
    tlul.yaml             # Session 3
    ahb.yaml              # Session 3
    apb.yaml              # Session 3
    wishbone.yaml         # Session 5 (可选)
```

**对握手检测器的反向增强 (Session 3 末)**:
- 协议识别后, 知道哪些是 valid/ready 配对
- 把这些"已知配对"喂给 handshake_detector, 提升 Phase B 置信度

---

## 7. 验收标准 (Acceptance Criteria)

**Session 1 通过**:
- [ ] `find_role_candidates` 在 5 个真实模块上正确分类
- [ ] clock/reset 永远不被判为 ready
- [ ] 单测 ≥ 20 个全过

**Session 2 通过**:
- [ ] `find_handshake_pairs` 在 AXI 5 通道上找到 5 对
- [ ] picorv32 找到 wb_valid/wb_ready 等关键对
- [ ] 单测 ≥ 15 个全过

**Session 3 通过**:
- [ ] 5 个 YAML 文件加载正确
- [ ] `match_protocol` 在 verilog-axi 模块上识别为 AXI4_FULL
- [ ] picorv32 识别为 Wishbone 或自定义 (如果有 wb_* 信号)
- [ ] 单测 ≥ 15 个全过

**Session 4 通过**:
- [ ] `sv_query protocol detect --module axi_adapter` 输出结果
- [ ] 4 个真实项目都能跑
- [ ] 单测 ≥ 10 个全过

**Session 5 通过**:
- [ ] verilog-axi / picorv32 / opentitan 都能识别
- [ ] 0 误报
- [ ] 真实 AXI 模块置信度 ≥ 0.85

---

## 8. 工作量估算 (Effort Estimate)

| Session | 预计代码 | 预计测试 | 预计时间 |
|---------|----------|----------|----------|
| Session 1 | 150-200 行 | 100 行 (20 测试) | 1-2 hours |
| Session 2 | 200-250 行 | 150 行 (15 测试) | 2-3 hours |
| Session 3 | 350 行 + 200 行 YAML | 200 行 (15 测试) | 3-4 hours |
| Session 4 | 200 行 | 100 行 (10 测试) | 1-2 hours |
| Session 5 | 100-200 行 (调参) | 真实项目 e2e | 2-3 hours |
| Session 6 (可选) | 100 行 | 50 行 | 1 hour |
| **总计** | **~1200 行 + 200 YAML** | **~700 行** | **10-15 hours (1-2 days)** |

---

## 9. 下一步行动 (Next Step)

**Session 1 立即开始**:
1. 读 graph_builder 现有 API, 找 module.port 列表的访问方式
2. 写 `is_valid_like` / `is_ready_like` / `is_wide_payload_like` 函数
3. 写 20 个单元测试
4. 跑通 picorv32 验证基础可行性

**Session 1 的成功标志**:
- `find_role_candidates(verilog_axi.axi_adapter)` 返回正确的 valid/ready/data 候选
- 现有 1616 测试仍然全过

---

## 10. 决策记录 (Decision Log)

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-06-10 | 采用"关键信号 + 语义匹配"方案, 不用纯名字 | 用户的真实场景是生成代码, 命名不规范 |
| 2026-06-10 | YAML 退化为辅助, 核心靠 width+dir+co-occurrence | 零配置可用, 鲁棒性最强 |
| 2026-06-10 | LLM 留到 Session 6 可选 | 主要靠 rule-based, LLM 兜底 |
| 2026-06-10 | 先做 AXI4 + AXI4-Lite, 其他协议后做 | 真实项目以 AXI 为主, 先验证方法论 |
# Protocol Detection Plan — Critical Review (模糊点审查)

> 状态: Plan v1 写完后, 自我审查
> 日期: 2026-06-10
> 目的: 在写代码前, 把所有"以为清楚其实不清楚"的地方标出来

---

## 🔴 BLOCKER (8 个 — 实现前必须解决)

### B1. **Master vs Slave 方向反转问题** (3.1 + 3.2 + 3.3)

**问题**: 同一个协议, master 和 slave 看到的信号方向**完全相反**:
```
AXI4 master:  awvalid=output,  awready=input
AXI4 slave:   awvalid=input,   awready=output
```

**Plan 哪里没说清**:
- 3.1 表格里写"valid: output (master) / input (slave)" — 但**怎么知道是 master 还是 slave**?
- 3.2 Layer 1 写"1bit output → 候选 valid" — 这对 slave 错! slave 的 valid 是 input
- 3.3 模板的 B 通道写"dir_in: [valid]" — 但**没有 master/slave 标记**, 怎么应用?

**需要的回答**:
- Master/Slave 在哪个阶段判定?
- 同一个模块可能是 master 也可能是 slave (e.g. switch), 怎么处理?
- 判定失败时默认按 master 还是双向?

**建议方案**:
```
对每个模块, 维护两个视图:
  - "as_master": 把 output 当 source, input 当 sink
  - "as_slave":  把 input 当 source, output 当 sink
两个视图都跑一遍 matcher, 取最高分
```

---

### B2. **信号如何分组到通道** (3.3 + Session 1/2/3)

**问题**: 协议模板是按通道 (AW/W/B/AR/R) 组织的, 但**怎么知道哪些信号属于 AW, 哪些属于 W**?

**Plan 哪里没说清**:
- 假设了"知道是 AW 通道"才能匹配模板, 但**没定义分组算法**
- 现实里, 名字可能 `awvalid` / `wvalid` / `valid` (无前缀) / `s_axi_*` 全混
- 5 个通道的 addr/data 可能宽度不同 (AWaddr 32bit, Wdata 64bit), 但仅靠宽度不够分组

**需要的回答**:
- 分组依据: 名字前缀? 宽度? 配对关系? 同 always 块?
- 名字无前缀时怎么办?
- 分组与匹配是否同时进行 (鸡和蛋)?

**建议方案**:
```
两步法:
  Step A: 候选分组 (基于 name hint 或 width cluster)
  Step B: 模板匹配 (基于 group + role 集合)
失败 fallback: 把整组信号当一个"未识别协议"报告
```

---

### B3. **Co-occurrence 的"共现"具体是什么** (3.2 + Session 2)

**问题**: "与配对信号在 if/always 共现 → +0.4", 什么叫"共现"?

**Plan 哪里没说清**:
- 是出现在**同一个 `if (cond)` 条件里**?
- 是出现在**同一个 `always` 块里**?
- 是**同 cycle 翻转**?
- 是有**因果依赖** (graph 里的边)?

**需要的回答**:
- 共现的精确定义
- 多种"共现"如何打分 (e.g. `if (a && b) c <= d` vs `c <= a & b`)
- 没有 if (纯 `assign a = b`) 时怎么处理

**建议方案**:
```
定义 co-occurrence = 下列 3 个指标之和:
  C1: 同 always 块         → 0.1
  C2: 同 if 条件           → 0.3
  C3: 同 if 的不同 operand → 0.4 (最强, 典型 `if (v && r) ...`)
无 if 也能配对: 权重降低, 但不全否决
```

---

### B4. **clock/reset 排除规则** (Section 5 风险 + Session 1)

**问题**: 1bit input `clk` 和 1bit input `ready` 宽度方向都相同, 怎么区分?

**Plan 哪里没说清**:
- 风险说"排除 known 1bit signals (clk, rst, nRst, irq)" — 这是**hardcoded 黑名单**?
- 黑名单谁来维护? 怎么扩展?
- 项目的 reset 命名五花八门: `rst`, `rstn`, `rst_n`, `nRst`, `resetn`, `arstn`...

**需要的回答**:
- 黑名单的**正则规则** vs 字面列表
- YAML 可配置吗? 还是 hardcode?
- 误判一个 clk 当 ready 的代价 (影响 protocol 识别)

**建议方案**:
```
默认黑名单 (YAML 可覆盖):
  hard_exclude: 
    - ^(clk|clock|clk_.*)$  # 时钟
    - ^(rst|rstn|rst_n|nrst|resetn|arstn|por_n)$  # 复位
    - ^(irq|nmi|interrupt.*)$  # 中断 (虽然也是 valid-like, 但不走 handshake 协议)
启发式: 时钟通常**只**作为 always 的 sensitivity list, 不参与 if 条件
       → 时钟永远 co-occurrence = 0
```

---

### B5. **"valid pair" 判定阈值** (Session 2)

**问题**: PairFinder 输出 `HandshakePair(confidence=0.0-1.0)`, 但**多少算"有效"**?

**Plan 哪里没说清**:
- Session 2 没写 threshold
- Session 3 matcher 用 `pair_coverage = valid_pairs / required_pairs` — 多少算"覆盖"?

**需要的回答**:
- Pair confidence 阈值 (e.g. ≥ 0.5)
- 协议最少需要几对 (e.g. AXI 至少 3 对)

**建议方案**:
```
默认阈值 (YAML 可覆盖):
  min_pair_confidence: 0.5
  min_pairs_for_protocol: 3  # 至少 3 对才认是协议
协议特例: APB 是 3-way (psel+penable+pready), TL-UL 是 2 对 (A/D)
```

---

### B6. **YAML 协议模板的完整内容** (Session 3 + 3.3)

**问题**: 只给了 AXI4 的示例, 没给 TL-UL / AHB / APB / Wishbone 的模板

**Plan 哪里没说清**:
- TL-UL 模板: 几个通道? 什么 role?
- AHB: hready/hgrant/hbusreq, master/slave 方向?
- APB: psel+penable+pready 3-way 怎么表达?
- Wishbone: cyc+stb+we+ack 4-way 怎么表达?

**需要的回答**:
- 5 个协议的完整模板
- ChannelSpec / VariantSpec 数据类的明确定义
- 3-way / 4-way handshake 怎么用 2-way 模板表达

**建议方案**:
```
扩展 channel spec:
  handshake_type: 
    - 2-way: valid + ready (AXI/TL-UL)
    - 3-way: req + ack + data_phase (APB psel/penable/pready)
    - 4-way: cyc + stb + we + ack (Wishbone)
为每种类型写一个 Yaml 例子 (而不是只 AXI4)
```

---

### B7. **如何排除 packed struct 字段** (Session 5 风险 + Architecture)

**问题**: AXI4 在 axi_pkg 里是 packed struct, e.g.:
```systemverilog
typedef struct packed {
    logic [3:0]   id;
    logic [31:0]  addr;
    logic         valid;
    logic         ready;
} aw_chan_t;

output aw_chan_t slv_req_o_aw;  // 整个 struct 作为一个 port
```

**Plan 哪里没说清**:
- graph_builder 怎么处理 packed struct (展开? 整体?)
- 如果不展开, `slv_req_o_aw.valid` 怎么被识别?
- 这是个**前置依赖**, 不是 Session 5 才解决

**建议方案**:
```
前置: 让 graph_builder 支持 struct field extraction (跟 sync_sram_proj 那个 issue 类似)
  - flat_name: slv_req_o_aw__valid (下划线拼接)
  - 字段类型继承自 struct
如果 graph_builder 还没支持, 先用 port-list 模式工作, struct 留到 Session 5
```

---

### B8. **graph_builder 在新架构里的角色** (Architecture + Section 6)

**问题**: Architecture 图里只有 Role/Pair/Matcher, 没提 graph_builder, 但 Session 2 又说"用现有 graph 找 co-occurrence"

**Plan 哪里没说清**:
- graph_builder 输出的什么 API 给 PairFinder 用?
- 如果 graph_builder 不可用, PairFinder 怎么 fallback?
- RoleDetector 完全不用 graph_builder, 但 PairFinder 深度依赖

**需要的回答**:
- 明确 PairFinder 的数据源 (graph builder output? AST 二次遍历?)
- graph_builder 失败时 PairFinder 怎么办
- graph_builder 已有 API 的清单 (我还没查)

**建议方案**:
```
PairFinder 数据源:
  优先: graph_builder.get_co_occurrences(sig1, sig2)  # 现成的图边
  Fallback: AST 二次遍历 (在所有 always/if 里数 co-occurrence)
RoleDetector 完全用 port list (不动 graph)
```

---

## 🟡 DEFER (7 个 — 实现时再定)

### D1. **数据类的完整签名** (Session 3)

```python
@dataclass
class ChannelSpec:  # 没定义
    name: str
    handshake_type: str  # 2-way/3-way/4-way
    roles_required: list[RoleRequirement]  # RoleRequirement 没定义
    roles_direction: dict[str, str]  # ?

@dataclass  
class VariantSpec:  # 没定义
    name: str
    needs: dict[str, list[str]]  # ?
    needs_absent: dict[str, list[str]]  # ?

@dataclass
class RoleRequirement:  # 没定义
    role: str  # 'valid' / 'ready' / ...
    direction: str  # 'input' / 'output' / 'any'
    width: str  # '1' / '>=8' / '==data/8'
```

**实现时定**: 但要在 Session 1 之前先把这 3 个 class 草拟出来, 否则 Session 3 YAML 写不下去

---

### D2. **"0 误报" 的精确定义** (Section 1 + 7)

**Plan 写**: "0 误报 (宁可 UNKNOWN, 不乱猜)"

**没定义**:
- UNKNOWN 算误报吗?
- 报 AXI 但实际是 TL-UL 算误报吗?
- AXI4-FULL 错判成 AXI4-Lite 算误报吗?
- 多协议候选时报第一个, 但实际是第二个, 算误报吗?

**建议**:
- 误报 = "报告的 protocol + variant 都不对"
- UNKNOWN 永远不是误报
- 同协议不同变体 算 "准确但不够精确", 不算误报

---

### D3. **"< 50ms/模块" 的硬件基准** (Section 1)

**没定义**:
- 什么机器? (M1 MacBook Air / 服务器?)
- 单文件还是项目? (parse + analyze 总时间)
- 第一次还是缓存后?

**建议**:
- 改写为 "M1 Air 上单文件解析+识别 ≤ 200ms, 缓存后 ≤ 20ms"
- 加 1 个 benchmark 测试

---

### D4. **"5 个真实模块"具体是哪 5 个** (Section 7)

**没定义**: Session 1 验收说"5 个真实模块", 没说哪 5 个

**建议**:
```
Session 1 验收用:
  1. verilog-axi/axi_adapter.v
  2. picorv32/picorv32.v (Wishbone 部分)
  3. 一个简单自定义模块
  4. opentitan/tlul_adapter_reg.sv
  5. 一个全 port 都匿名的测试模块
```

---

### D5. **confidence 各分项的归一化** (3.4 评分)

**没定义清楚**:
- `pair_coverage` = valid_pairs / required_min_pairs
  - 0 pairs 时 = 0, 1 pair = ?, 全部 = 1.0?
  - 实际是 `min(1.0, found/required)` 还是 `found/required`?
- `name_hint_match` 分母是 total_hint 数? matched_hint 数?

**建议**:
```
pair_coverage = min(1.0, found_pairs / min_required_pairs)
name_hint_match = matched_hints / total_hints
role_classification = avg of matched candidates' confidence
structural_purity = (clean_pairs / total_pairs)  # 排除冲突的配对
```

---

### D6. **失败优雅降级的具体行为** (架构 原则 3)

**说**: "任何一层失败, 上一层的 best-effort 结果仍然有用"

**没定义**:
- "失败"是什么? (Exception? 0 候选?)
- "上一层的 best-effort" 长什么样?
- 返回值是 None? 还是 partial result?

**建议**:
```
返回值统一用 Optional[ProtocolMatch]:
  - 0 candidates: 返回 None (UNDEFINED, not an error)
  - Exception: log + 返回 None
  - 上一层的 best-effort: 加 warnings 字段, 但不阻塞
```

---

### D7. **picorv32 协议识别** (Section 7 + 5)

**说**: "picorv32 识别为 Wishbone 或自定义"

**没定义**:
- picorv32 实际用啥? (内部是 Wishbone-style, 但 verilog 输出用 `wb_*` 命名)
- 如果 YAML 没 Wishbone, 怎么识别?
- "自定义" 协议怎么表示? 叫什么名? confidence 多少?

**建议**:
- 加 `wishbone.yaml` 模板
- 自定义协议: protocol = "CUSTOM", variant = None, confidence = 任意
- picorv32 测试**推迟到 Wishbone YAML 写完**, Session 3 末

---

## 📋 总结

| 类别 | 数量 | 处理方式 |
|------|------|----------|
| 🔴 Blocker | 8 | **实现前必须解决** (改 plan 或开 mini-session 探路) |
| 🟡 Defer | 7 | 实现时遇到再定, 但要在 Session 1-3 进度中逐步明确 |

**特别建议**: 在 Session 1 之前, 先开一个 **"Spike 0"** (半天), 验证:
1. graph_builder 是否能给出 co-occurrence (B8)
2. packed struct 怎么处理 (B7)
3. Module 的 port list 怎么访问 (B1, B2 的输入)

**Spike 0 输出**: 1 份 1 页的"API 可行性报告", 决定 Session 1 怎么写

---

## 🛠️ 修订后 Session 0 (新建议)

把 Session 1 拆成 2 步:
- **Session 0 (Spike)**: 1-2 小时, 探路 graph_builder + port list + struct, 输出可行 API
- **Session 1 (原计划)**: RoleDetector, 在 Session 0 探明的基础上写
