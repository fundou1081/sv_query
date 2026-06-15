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
