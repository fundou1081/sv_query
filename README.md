# sv_query — SystemVerilog 信号追踪查询引擎

**让验证工程师直接问"这个信号谁驱动的"，而不是去读代码。**

> 2958 测试 (97.1% pass) | Python 3.11+ | pyslang AST | NetworkX graph | 7 个开源项目验证

---

## 为什么用 sv_query

- **位精确追踪**: V6.5 `SignalSource` 结构化存储 bit_range + op + casts，知道信号 `[7:0]` 确切来源
- **穿透子模块**: 跨 wrapper port passthrough，追踪真实物理连接 (MIG 跨模块)
- **数据可信**: [pyslang](https://github.com/MikePopoloski/pyslang) 语义 AST，不是正则匹配
- **7 个开源项目跑通**: picorv32, darkriscv, CVA6, OpenTitan, Ventus, CoralNPU, NaplesPU
- **架构可视化**: `arch show` 一键生成项目架构图 (DOT/Mermaid/HTML/summary)
- **数据与渲染解耦**: V6.7 VizData 统一可视化数据层

---

## 5 分钟快速上手

```bash
git clone https://github.com/fundou1081/sv_query.git
cd sv_query
pip install -e .
sv_query --help
```

### 查询信号驱动

```bash
# 看谁驱动了 result
sv_query trace fanin top.result -f top.sv

# 画信号关系图
sv_query visualize graph -f top.sv

# 画数据流图 (控制边=虚线，数据边=实线)
sv_query visualize dataflow -f top.sv

# 看模块架构
sv_query arch show -f top.sv -t top --summary
```

### 可选: graphviz

```bash
brew install graphviz  # macOS
# 生成 PNG:
sv_query visualize graph -f top.sv --dot /tmp/g.dot && dot -Tpng /tmp/g.dot -o /tmp/g.png
```

---

## 功能分层 (3-tier)

### ⭐ 主要功能 (Primary) — 重点投入

| 命令 | 价值 |
|------|------|
| `dataflow analyze A B` | A→B 数据流 + cycle latency |
| `controlflow analyze A` | 看 signal 的 if/case 条件树 |
| `visualize graph/dataflow/pipeline` | 画 DOT 图 (V6.7 统一渲染) |

### ✅ 稳定功能 (Stable)

- `trace fanin/fanout/impact` — 信号追踪
- `arch show` — 架构图
- `stats/search` — 查询
- `sva extract/coverage/timing` — SVA
- `snapshot save/list/show/delete/compare` — 快照
- `diff compare` — 版本对比
- `protocol detect/show/semantics` — 总线协议

### 🟡 实验功能 (Experimental)

- `cdc analyze` / `timing analyze` / `risk analyze`
- `coverage generate/gap` / `verify gap`
- `fix timescale/report/imports/widths`

---

## CLI 命令参考

| 命令 | 用途 |
|------|------|
| `trace` | 信号驱动/负载/影响 |
| `visualize` | graph/dataflow/pipeline/chain/module/teach |
| `arch` | 架构图 |
| `dataflow` | 数据流路径分析 |
| `controlflow` | 控制流条件分析 |
| `stats/search` | 统计/搜索 |
| `cdc/timing/risk` | 跨时钟域/时序/风险 |
| `sva/coverage/verify` | SVA 提取/覆盖率/验证 |
| `protocol/handshake` | 总线/握手协议 |
| `snapshot/diff` | 快照/版本对比 |
| `fix` | 自动修复 elaboration 错误 |
| `design` | 项目概述 |

完整 → `sv_query <command> --help`

---

## Python API

```python
from trace.unified_tracer import UnifiedTracer

tracer = UnifiedTracer(sources={"top.sv": src}, strict=False)
tracer.trace_module("top")
graph = tracer.get_graph()

# 查询
from trace.core.graph.viz import build_viz_data, VizBuildOptions, render_dot
viz = build_viz_data(graph)
dot = render_dot(viz, {"title": "My Design"})
```

---

## 项目结构

```
sv_query/
├── src/trace/              # 核心 (~39K 行)
│   ├── unified_tracer.py   # 统一入口
│   ├── core/
│   │   ├── graph/
│   │   │   ├── models.py        # TraceNode/TraceEdge/SignalSource/DriverInfo
│   │   │   ├── viz/             # V6.7 VizData 统一可视化层
│   │   │   └── analyzer/        # dataflow/cdc/timing/pipeline/classifier
│   │   ├── driver_extractor.py  # Driver 提取 (2639 行)
│   │   ├── graph_builder.py     # 图构建器
│   │   └── visitors/            # AST Visitor (~10K 行)
│   └── cli/commands/            # 27 CLI 命令
├── sim/tests/              # 2958 测试 (247+ 文件)
├── docs/                   # 文档
└── tools/                  # 独立工具
```

---

## 测试

```bash
pip install -e ".[dev]"

# 日常开发 (跳过开源项目依赖，~30s)
python -m pytest sim/tests/ -m "not opensource" -q

# 全量
python -m pytest sim/tests/ -q
# 2958 tests, 97.1% pass (55 pre-existing failures)
```

详见 [测试指南](docs/TESTING.md)

---

## 依赖

| 包 | 必需 |
|----|------|
| networkx>=3.0 | ✅ |
| typer>=0.9 | ✅ |
| pyslang>=10.0.0 | ✅ |
| graphviz | ❌ (只 PNG/SVG) |

---

## 相关文档

- [架构文档](docs/ARCHITECTURE.md)
- [可视化设计规范](docs/VIZ_DESIGN_SPEC.md)
- [文档索引](docs/INDEX.md)
- [已知限制](docs/KNOWN_LIMITATIONS.md)

## 许可

MIT + Apache 2.0 双许可
