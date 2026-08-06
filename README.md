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

## 数据流可视化 (Dataflow Visualization)

`visualize dataflow` 将 SystemVerilog 的 `assign` 和 `always` 逻辑自动渲染为 ELK.js 数据流图。

### 设计理念

- **双层渲染引擎**: 纯组合逻辑走 ExpressionTree 路径（ELK layered layout），时序/条件逻辑走 compound graph 路径（case/if branch 范围框）
- **条件分离**: 三元运算符 `? :` 的条件信号用**灰色虚线**标注，数据信号用实线
- **嵌套支持**: 嵌套三元 `(sel_b ? a : b)` 自动展开为子节点，标签 `?: (sel_b)`
- **零配置**: 不需要 graphviz，内部集成 ELK.js + rsvg-convert 直接出 SVG/PNG

### 快速使用

```bash
# 数据流图（运算表达式）
sv_query visualize dataflow -f top.sv

# 指定模块
sv_query visualize dataflow -f top.sv -m counter

# 导出 SVG（--dot 参数复用为 SVG 输出，兼容旧接口）
sv_query visualize dataflow -f top.sv --dot output.svg
```

### 效果展示

**函数调用 + 运算** (`assign y = add_sat(a,b); assign z = (a*b)+c`)

![with_function dataflow](docs/images/with_function_dataflow.png)

节点: `a,b,c` → `×` `add_sat` `+` → `z,y`

**三元运算符** (`assign y = sel_a ? (sel_b ? a : b) : c`)

![ternary dataflow](docs/images/with_ternary_dataflow.png)

`?: (sel_a)` / `?: (sel_b)` — 条件边=灰色虚线，数据边=实线

**case 多路选择** (`always @(*) case(sel) ...`)

![case dataflow](docs/images/with_case_dataflow.png)

`case (sel)` 紫色实线框 + 绿色虚线分支标签

**if-else 条件分支** (`always @(posedge clk) if(!rst_n) ... else if(a>10) ...`)

![ifelse dataflow](docs/images/with_ifelse_dataflow.png)

复合条件展开，分支内嵌操作符

### 实现细节

| 路径 | 条件 | 渲染方式 |
|------|------|---------|
| ExpressionTree | 有 `assign` / 组合逻辑 | `expr_trees_to_elk()` → ELK layered layout |
| Compound fallback | 纯时序 / case / if | `viz_to_elk()` → ELK compound graph |

- **三目展开**: `ExpressionTree._build_ternary()` 从 pyslang AST `ConditionalPredicate` 提取条件+真/假分支
- **边颜色**: dataflow 实线 `#555` / condition_select 虚线 `#989` (stroke-dasharray 6,3)
- **节点类型**: port_in/port_out (灰色圆角) · op (橙色方框) · signal (黄色圆角) · const (青色圆角)

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

# 1. 构建图
tracer = UnifiedTracer(sources={"top.sv": src}, strict=False)
tracer.trace_module("top")
graph = tracer.get_graph()

# 2. 查询信号驱动 (含 condition, clock, 位精确 source)
drivers = tracer.trace_fanin_detailed("top.result")
for d in drivers:
    print(f"{d.node.id} ← {d.expression}")
    if d.source:
        print(f"  bit:[{d.source.bit_start}:{d.source.bit_end}] op={d.source.op}")
    print(f"  when: {d.condition or 'always'}")

# 3. 导出可视化数据 (V6.7)
from trace.core.graph.viz import build_viz_data, VizBuildOptions, render_dot
viz = build_viz_data(graph, VizBuildOptions(include_edge_condition=True))
dot = render_dot(viz, {"title": "My Design"})    # DOT 字符串
data = viz.to_json()                               # JSON 纯数据
```

更多 → [CONTRIBUTING.md](CONTRIBUTING.md)

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

# 日常开发 — golden 测试 (纯 SV, 30s)
python -m pytest sim/tests/ -m golden -q

# 日常开发 — 跳过开源项目依赖 (~2min)
python -m pytest sim/tests/ -m "not opensource" -q

# 发布前 — 开源项目验证 (picorv32, darkriscv, OpenTitan...)
python -m pytest sim/tests/ -m opensource -v

# 全量
python -m pytest sim/tests/ -q
# 2958 tests, 97.1% pass
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
