# sv_query — SystemVerilog 信号追踪查询引擎

**让 agent 查询并验证 RTL 事实，而不是靠读源码猜。**

> agent 面向的 RTL **查询 + 客观校验层**：服务动态 debug（波形值由外部工具提供）与 design 理解；
> 核心是 canonical identity、evidence、双向验证，而不是自然语言解释。

> 2502 passed (canonical 主回归) | Python 3.11+ | pyslang 语义 AST | NetworkX graph | 真实项目验证

> 更新日期: 2026-11-03

---

## 为什么用 sv_query

- **位精确追踪**: `SignalSource` 结构化存储 bit_range + op + casts，知道信号 `[7:0]` 的确切来源；位对位跨模块贯通
- **穿透子模块**: wrapper port passthrough + bus 位桥（同构直连 / 切片偏移）
- **数据可信**: pyslang 语义 AST，不是正则匹配；失败显式可见，不静默出假数据
- **class/constraint 追踪**: 实例属性数据流含方法调用链、实例↔类型级关系、约束查询
- **客观校验**: 全图 / bit-level 结构一致性 + claim 验证
- **真实项目验证**: strict_uart / verilog-axi / picorv32 smoke；bit consistency 三项目 0 violation

> 可视化方向已调整：全设计图退出产品面，动态子图/finding 局部 review 是下一阶段方向。
> 详见 [structural_review_plan_2026-11-02](docs/architecture/structural_review_plan_2026-11-02.md)。

---

## 项目定位（2026-11-02）

完整方向见 [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md)。

- **主场景**：agent 的 RTL debug / design 理解；迭代查询、多批脚本、按结论继续追问。
- **动态 debug 分工**：波形值由外部工具提取；sv_query 提供 canonical id/别名、层级、位映射、clock/reset、sequential stage、源码 evidence。
- **函数/class**：RTL 函数名 + 源码足够（不 inline）；class 关注调用链/继承/对象关系。
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

---

## 功能分层

| 层 | 命令 |
|---|---|
| **Scope** | `scope` / `instances` / `hierarchy` / `ports` / `params` / `connections` / `class` |
| **Trace** | `drivers` / `loads` / `paths` / `dataflow` / `controlflow` / `trace evidence/profile/lookup/manifest` |
| **Verify** | `verify consistency` / `verify claim` |
| **Locate** | `stats` / `search` / `graph nodes/edges` / `capabilities` |
| **State** | `snapshot save/list/compare/delete` |
| **exp** | `audit` / `diagnose` / `trace overview`（默认隐藏，不承诺契约） |

> `visualize` / `arch` / `design` 全设计图命令已于 2026-11-03 退役。

---

## Python API

```python
from trace.unified_tracer import UnifiedTracer

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
├── src/trace/              # 核心图/追踪/校验
│   ├── unified_tracer.py   # 统一入口
│   ├── core/
│   │   ├── graph/          # SignalGraph / models / analyzer
│   │   ├── driver_extractor.py
│   │   ├── graph_builder.py
│   │   └── visitors/
├── src/cli/                # CLI (core/exp)
├── sim/tests/              # 测试
├── docs/                   # 文档
└── tools/                  # 独立工具
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
- [架构文档](docs/ARCHITECTURE.md)
- [准确性审计](docs/architecture/signal_graph_accuracy_audit.md)
- [开发纪律](AGENTS.md) · [当前任务](CURRENT_TODO.md)
- [文档索引](docs/INDEX.md)
- [已知限制](docs/KNOWN_LIMITATIONS.md)

## 许可

MIT + Apache 2.0 双许可
