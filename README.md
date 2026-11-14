# sv_query — 面向 agent 的 SystemVerilog 语义查询 + 客观校验引擎

**让 agent 查询并验证 RTL 事实，而不是靠读源码猜。**

> agent 面向的 RTL **查询 + 客观校验层**：服务动态 debug（波形值由外部工具提供）与 design 理解；
> 核心是 canonical identity、evidence、双向验证，而不是自然语言解释。

> 回归基线见 [docs/INDEX.md 当前基线](docs/INDEX.md#-当前基线-单一真相源--计数只写在这里) | Python 3.11+ | pyslang 语义 AST | NetworkX graph | 真实项目 + 性能基准 + agent 对照（内部）

> 更新日期: 2026-11-11（基线计数不再写死，统一引用 INDEX）

---

## 为什么用 sv_query

- **位精确追踪**: `SignalSource` 结构化存储 bit_range + op + casts，知道信号 `[7:0]` 的确切来源；位对位跨模块贯通
- **穿透子模块**: wrapper port passthrough + bus 位桥（同构直连 / 切片偏移）
- **语义优先**: class / constraint / covergroup / UVM role 走 pyslang semantic AST；
  UVM 宏/调用因预处理器会丢宏，是唯一 `syntactic` regex 例外（显式标 confidence，不作为 verify 证明）
- **class/constraint/covergroup/UVM**: 继承约束链、rand/randc 标记、covergroup 采样/反向查询、
  UVM sequence/factory 静态关系
- **客观校验**: 全图 / bit-level 结构一致性 + claim 验证 + finding 局部证据
- **可复现验证**: strict_uart / verilog-axi / picorv32 / SERV smoke；3 设计性能基准；
  单级 CDC 反幻觉 walkthrough；12 题双模型 source-only vs sv_query 对照（内部）。
  **尚未跑 HWE-Bench/VeriBugBench**，不宣称对外准确率/成本收益。

> 全设计图已退役；局部 finding review 仍为 `exp`（`review render`），不是核心能力。
> 语义纪律见 [DISCIPLINE §3.5](docs/dev/DISCIPLINE.md)。

---

## 项目定位（2026-11-05）

完整方向见 [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md)。

- **主场景**：agent 的 RTL debug / design 理解；迭代查询、多批脚本、按结论继续追问。
- **动态 debug 分工**：波形值由外部工具提取；sv_query 提供 canonical id/别名、层级、位映射、clock/reset、sequential stage、源码 evidence。
- **函数/class**：RTL 函数名 + 源码足够（不 inline）；class 关注调用链/继承/对象关系、
  constraint/covergroup 与 UVM 静态关系。
- **证据分级**：semantic 结果优先；UVM 宏相关的 `confidence=syntactic` 只作线索，不作证明。
- **核心原则**：事实与证据优先；未知/空/歧义显式；双向一致性 + claim verification。

---

## 5 分钟快速上手

```bash
git clone https://github.com/fundou1081/sv_query.git
cd sv_query
pip install -e .
sv_query capabilities --json
```

### 查询信号驱动

```bash
# 谁驱动 result
sv_query drivers top.result -f top.sv --json

# 下游负载
sv_query loads top.result -f top.sv --json

# 跨模块路径
sv_query paths top.a top.y -f top.sv --json

# 结构一致性
sv_query verify consistency --full --checks reciprocity,bit -f top.sv --json
```

### 波形 / 类型元数据

```bash
sv_query trace profile top.data -f top.sv --json
sv_query trace manifest --path top.data -f top.sv --json
```

### 5 分钟反幻觉 walkthrough：单级 CDC

一个常见错误结论：

> “`dst_valid` 在 `dst_clk` 域寄存过，所以有两级同步器，CDC 安全。”

```bash
sv_query trace profile cdc_bug.dst_valid   -f examples/anti_hallucination_cdc/cdc_bug.sv --json
# clock_domains = ["dst_clk"]  ← 只能说明域，不证明同步链

sv_query trace fanin cdc_bug.dst_valid   -f examples/anti_hallucination_cdc/cdc_bug.sv --json
# drivers: src_valid (distance=1), 1'b0  ← 没有 meta 中间级
```

结构证据直接反驳“两级同步器”：`src_valid → dst_valid` 只有一拍。  
完整命令、输出与 ground truth：  
[examples/anti_hallucination_cdc/README.md](examples/anti_hallucination_cdc/README.md)。

性能数据（单机实测、构图 vs 图内查询拆分）：  
[docs/validation/QUERY_PERF_2026-11-04.md](docs/validation/QUERY_PERF_2026-11-04.md)。

---

## 功能分层

| 层 | 命令 |
|---|---|
| **Scope** | `scope` / `instances` / `hierarchy` / `ports` / `params` / `connections` / `class` |
| **Trace** | `drivers` / `loads` / `paths` / `dataflow` / `controlflow` / `trace evidence/profile/lookup/manifest` |
| **Verify** | `verify consistency` / `verify claim` / `verify structural` |
| **Class/约束/覆盖** | `class --relations`（含 UVM 静态） / `trace constraints` / `trace covergroups` / `trace coverpoints` / `trace covergroup` |
| **Locate** | `stats` / `search` / `graph nodes/edges` / `graph subgraph` / `capabilities` |
| **State** | `snapshot save/list/compare/delete` |
| **exp** | `audit` / `diagnose` / `trace overview` / `review render` / `architecture graph` / `trace impact`（默认隐藏，不承诺契约） |

> `visualize` / `arch` / `design` 全设计图命令已于 2026-11-03 退役；`review render` 仍是 exp。

---

## 验证状态（2026-11-11）

| 项 | 状态 |
|---|---|
| 全量回归 | 见 [INDEX 当前基线](docs/INDEX.md#-当前基线-单一真相源--计数只写在这里)：canonical 0 failed；opensource 114 passed / 9 显式 skip |
| 开源 smoke | strict_uart / verilog-axi / picorv32 / SERV |
| 性能基准 | picorv32 / verilog-axi / SERV；build、warm query、cold CLI、peak RSS |
| 反幻觉 | 单级 CDC walkthrough：profile + fanin/fanout 反驳“两级同步器” |
| Agent 对照（内部） | 固定协议 12 题 ×2 模型 ×2 臂 ×2 seed：**T2 48/48，source 32/48**；见下方 |
| 硬隔离 | 96-cell 矩阵；source 无 repo/CLI，T2 无 truth/task JSON；12×3 未跑 |
| 未做 | 外部 VeriBug/HWE 对照、真实根因/patch、token 成本、3rd seed |

性能：构图是 cold CLI 主导成本（本机 verilog-axi 约 26 s / 13.8k nodes），
图内查询为毫秒级。不要把 warm query 的毫秒数字误读成冷启动查询。
详见 [性能基准](docs/validation/QUERY_PERF_2026-11-04.md) 与
[反幻觉 walkthrough](examples/anti_hallucination_cdc/README.md)。

### Agent 对照（内部，2026-11-07）

12 个“源码远、结构近”任务（AXI / SERV / PicoRV32），固定协议：
source/T2 hard isolation、fact check、`--depth 1`、query log；2 seed。

| 模型 / 臂 | exact（24 cells） | high-conf 错 |
|---|---:|---:|
| MiniMax-M3 / source | 17/24 | 7/24 |
| MiniMax-M3 / svq | **24/24** | 0/24 |
| DeepSeek-Flash / source | 15/24 | 2/24 |
| DeepSeek-Flash / svq | **24/24** | 0/24 |

合计：

```text
source: 32/48
svq:    48/48
```

观察：

- svq 在两个 seed、两个模型上均 48/48；
- source 仍出现 high-confidence 错误（9/48）；
- 这是 **direct structural query**，不是 debug reasoning；
- token/cold-warm 成本未拆分，不能声称成本更低；
- 不声称 HWE/VeriBug 或真实项目准确率。

硬隔离：source 臂拒绝 repo / `sv_query` / pilot artifact；T2 拒绝 task JSON/truth。
已跑 96-cell 矩阵；12×3 未跑（3rd seed 不做）。

详见 [12-task 固定协议](docs/validation/LONG_RANGE_12_FIXED_2026-11-07.md)、
[最终验证摘要](docs/validation/FINAL_VALIDATION_SUMMARY_2026-11-07.md)、
[硬隔离审计](docs/validation/HARD_ISOLATION_2026-11-05.md)。

---

## Python API

```python
from sv_query.sv_query.trace.unified_tracer import UnifiedTracer

tracer = UnifiedTracer(sources={"top.sv": src})
tracer.build_graph()
graph = tracer.get_graph()

drivers = tracer.trace_fanin_detailed("top.result")
for d in drivers:
    print(d.node.id, "<-", d.expression)
    print("  when:", d.condition or "always")
```

---

## 项目结构

```
sv_query/
├── src/sv_query/trace/              # 核心图/追踪/校验
│   ├── unified_tracer.py   # 统一入口
│   ├── core/
│   │   ├── graph/          # SignalGraph / models / analyzer
│   │   ├── driver_extractor.py
│   │   ├── graph_builder.py
│   │   └── visitors/
├── src/cli/                # CLI (core/exp)
├── sim/tests/              # 测试
├── examples/               # 可复现 walkthrough（反幻觉 CDC）
├── docs/                   # 文档 / 性能数据
├── skills/                # OpenClaw skill 包 (sv-query, 供 agent 加载)
└── tools/                  # 独立工具（含 benchmark/query_perf.py）
```

---

## 测试

```bash
pip install -e ".[dev]"

# 日常主回归
python -m pytest sim/tests/ -m "not opensource" -q

# 开源项目验证
python -m pytest sim/tests/ -m opensource -v
```

详见 [TESTING.md](TESTING.md)。计数以 [docs/INDEX.md](docs/INDEX.md) 当前基线为准。

---

## 相关文档

- [产品方向](docs/architecture/product_direction_2026-10-31.md)
- [结构审查/动态子图计划](docs/architecture/structural_review_plan_2026-11-02.md)
- [查询性能基准](docs/validation/QUERY_PERF_2026-11-04.md) · [反幻觉 CDC walkthrough](examples/anti_hallucination_cdc/README.md)
- [12-task 固定协议](docs/validation/LONG_RANGE_12_FIXED_2026-11-07.md) · [最终验证摘要](docs/validation/FINAL_VALIDATION_SUMMARY_2026-11-07.md) · [硬隔离审计](docs/validation/HARD_ISOLATION_2026-11-05.md)
- [架构文档](docs/ARCHITECTURE.md)
- [准确性审计](docs/architecture/signal_graph_accuracy_audit.md)
- [语义 regex 纪律](docs/dev/DISCIPLINE.md) · [开发纪律](AGENTS.md) · [当前任务](CURRENT_TODO.md)
- [文档索引](docs/INDEX.md)
- [已知限制](docs/KNOWN_LIMITATIONS.md)

## 许可

MIT + Apache 2.0 双许可
