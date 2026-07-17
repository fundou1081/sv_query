# 架构可视化 (arch 命令 + 信号图)

> **本文档** 涵盖 sv_query 的可视化能力: `arch` 命令 (项目架构) + `visualize` 命令 (信号图)
> 
> 用户场景 + 4 维 L1-L4 能力 → 见 [README.md#用户场景](README.md#用户场景)
> Python API → 见 [README.md#python-api](README.md#python-api)

---

## arch 命令 (2026-06-25 加)

**`arch`** 一键生成整个项目的架构图: 模块层级 + 跨模块端口连线.

### 用法

```bash
# 简单项目 (单文件)
python run_cli.py arch -f top.sv -t top --summary

# 工业项目 (filelist + 多文件 + 含 typedef headers)
python run_cli.py arch --filelist=project.f -t top -d 10 --cluster-by-type \
    --format svg -o arch.svg

# 输出格式: dot / mermaid / html / svg / summary
python run_cli.py arch -f top.sv --format mermaid   # GitHub README 友好
python run_cli.py arch -f top.sv --format html      # 交互式
python run_cli.py arch -f top.sv --format svg       # 调 graphviz, 浏览器看
```

### 5 种输出格式

| 格式 | 用途 | 例子 |
|------|------|------|
| `--summary` | 一段话描述项目架构 | Top module types + 端口连接计数 |
| `--format dot` | Graphviz, `dot -Tpng` 渲染 | 适合 PNG/SVG 生成 |
| `--format mermaid` | GitHub README 友好, 自动渲染 | Markdown 里直接显示 |
| `--format html` | 交互式 (vis.js), 浏览器打开 | 缩放/拖拽/层次布局 |
| `--format svg` | 标准 SVG (调 `dot -Tsvg`) | 嵌入网页/文档 |

### v2 features

- `--cluster-by-type`: 同一 module type 的 instance 合并 cluster + hash-based 颜色
- `--max-nodes N`: 限制 nodes 数 (默认 100), 超出折叠 + collapse note
- `--with-ports`: 显示跨 module 端口连线 (`cva6.flush_i` 同时连 `i_frontend`, `id_stage`, `ex_stage`)

### 实测案例 (5 个开源项目)

| 项目 | Instances | Hierarchy | Ports | 说明 |
|------|-----------|-----------|-------|------|
| Google CoralNPU | 28 | 4 层 | 31+ | 2025 最新 RISC-V RVV NPU |
| CVA6 / Ariane | 11 | 3 层 | 31 | ETH Zurich 工业 RISC-V CPU |
| Vortex | 3+ | 2 层 | - | 工业 RISC-V GPU |
| SERV | 9 | 1 层 | - | "世界最小 RISC-V" (~200 gates) |
| darkriscv | 5 | 2 层 | - | 极简 RISC-V SoC |

### 实际例子 (CoralNPU summary 输出)

```
📐 Project Architecture: RvvCore
============================================================
Total instances:  28
Hierarchy depth:  4 levels
Port connections: 31 (cross-module)

Top module types (by instance count):
  RvvFrontEnd                                 1  █
  Aligner                                     1  █
  rvv_backend                                 1  █
  rvv_backend_decode                          1  █
  rvv_backend_decode_de2                      1  █
  ...

Most common port connections:
  clk_i                             4
  rst_ni                            4
  flush_i                           3
```

详细 examples: [docs/ARCH_EXAMPLES.md](ARCH_EXAMPLES.md)

---

## visualize 命令 (信号图)

### 核心特性

| 特性 | 说明 |
|------|------|
| 数据流边 | 显示驱动/负载关系 (而非简单连接线) |
| 风险热力图 | 按功能复杂度 × 时序复杂度评分 |
| 覆盖状态标记 | ✓ SVA / 🟡 Coverage / ✓🟡 两者 / 🚨 缺口 |
| 边颜色编码 | 黑色=数据流, 蓝色=时钟, 红色=复位 |
| 分层布局 | INPUT 在上 (rank=source), OUTPUT 在下 (rank=sink) |
| 模块聚类 | `--cluster-modules` 按子模块分组显示, 跨模块边用虚线 |
| 驱动条件 | `--show-conditions` 在边上显示 if (cond) 才驱动的条件 |
| 曲线边 | `splines=spline` 曲线边, 更清晰美观 |
| 边粗细区分 | 数据流边加粗 (penwidth=2), 时钟/复位边细虚线 |

### 命令行参数

```bash
python run_cli.py visualize graph [OPTIONS]

选项:
  -f, --file PATH          输入 SystemVerilog 文件
  -d, --dot PATH           输出 DOT 文件
  -m, --mmd PATH           输出 Mermaid 文件
  --html PATH              输出 HTML 文件
  -l, --layout TEXT        布局方向: TB (上下) 或 LR (左右), 默认 TB
  --max-edges INTEGER      最大边数, 默认 200
  --exclude-clock          排除时钟边
  --exclude-reset          排除复位边
  --show-labels            在边上显示边类型标签 (CLOCK/RESET/DRIVER)
  --show-conditions        在边上显示驱动条件
  --no-edges               隐藏边, 只显示节点
  --cluster-modules        按子模块聚类显示 (大型设计推荐)
  --layout-engine TEXT     布局引擎: dot (层次), neato (力导向), fdp (分组)
```

### 一键生成可视化报告

```bash
# 生成信号图 (含数据流关系)
python run_cli.py visualize graph -f top.sv --dot /tmp/graph.dot --html /tmp/graph.html

# 生成验证缺口分析图 (高亮无覆盖的高风险信号)
python run_cli.py verify gap -f top.sv --dot /tmp/gap.dot --mmd /tmp/gap.mmd

# DOT 渲染为 PNG (需安装 graphviz, 见 README 安装步骤)
dot -Tpng /tmp/graph.dot -o graph.png
```

### Dataflow 可视化

```bash
python run_cli.py visualize dataflow -f top.sv --dot /tmp/dataflow.dot
```

自动分类 clock/reset/control/data, 显示运算表达式 (a+b) + MUX 选择 + 关键控制边.

### Pipeline 可视化

```bash
python run_cli.py visualize pipeline -f uart.sv --dot /tmp/pipeline.dot
```

自动检测 pipeline registers (排除 FSM state regs), 按 stage 分组, 左→右时间流布局.

#### V4 (2026-07-17): stage clusters + 跨 stage DRIVER 边 + state→stage 影响

```bash
# 默认参数已优化, 直接跑即可:
python run_cli.py visualize pipeline -f uart.sv --dot /tmp/pipeline.dot
```

主要内容 (Phase 6.5.4 + V4):
- **每个 stage 一个 cluster**: 蓝色虚线框包裹该 fold 的 REG 节点 (openofdm 92 stages → 10 clusters)
- **跨 stage 边**: 一条粗蓝色 `#226699` 箭头, 标签 `flow_S0_to_S1` (数据流向)
- **state_reg → stage 边**: 橙色虚线, `affects SN` (state machine 影响哪个 stage)
- **max_control_nodes=12**: 12 个 AXI/控制信号在顶部 header 行
- **max_regs_per_fold=3**: 每个 fold 显示 3 个 REG 节点
- **target_folds=10**: 默认 fold_every=10 (大规模 pipeline 更细致)

调优参数: `--unfold` (全部 stages), `--fold-every N` (自定义 fold 数), `--max-control-nodes N` (更多控制信号), `--timing` (车道×周期 timing 图), `--load-path` (按 load port 分段).

### Chain 可视化 (输入到输出链路)

```bash
# 手动指定 from → to:
sv_query visualize chain -f dot11_tx.v --no-strict \
  --from dot11_tx.phy_tx_start --to dot11_tx.result_i \
  --layout LR --layout-engine neato --png /tmp/chain.png

# Auto mode: 自动从 --target module 的 input ports 到 output ports:
sv_query visualize chain -f dot11_tx.v --no-strict \
  --target dot11_tx --auto --max-edges 30 \
  --layout LR --layout-engine neato --png /tmp/chain.png
```

方形 layout, 二维定位. 适合 "深入到具体 module, 完整 input → output 图".

### Module 可视化 (架构层级)

```bash
# L1 module-only (默认):
sv_query visualize module -f top.sv --target axi_xbar_intf

# L2 cross-instance port edges (--mig):
sv_query visualize module -f top.sv --target axi_xbar_intf --depth 2 --mig
```

1 box = 1 sub-module instance. `--mig` 加跨实例 port 边 (`--depth` 决定层级深度). 适合架构 review.

---

## Phase B Refactor (2026-07-17)

### 目标

合并 5 个 viz 子命令 (`graph`/`dataflow`/`pipeline`/`chain`/`module`) 的重复 boilerplate, 使 1 个开发者维护 10+ viz 子命令仍然可读可扩展.

### 新增模块

1. `src/cli/_viz_common.py` (115 LOC) — CLI 层共享
   - `FILE_OPTION` / `FILELIST_OPTION` / `INCLUDE_OPTION` / `STRICT_OPTION`: typer option 常量
   - `build_viz_tracer()`: 验证 + handle CompilationError + return (tracer, graph)
   - `get_viz_sources()`: 单文件 / filelist 模式统一取 sources

2. `src/trace/core/graph/analyzer/_dot_common.py` (从 81 → 170 LOC) — DOT utilities
   - `escape_dot_label(s)`: DOT label 特殊字符转义
   - `format_node_label_chain(node_id, top)`: 链路多行 label formatter
   - `sanitize_dot_id_inner(s)`: 链路 sanitizer (alternative to `sanitize_dot_id`)
   - `render_with_engine(dot, out, engine, fmt)`: graphviz 包装

### 代码量变化

| | 之前 | 现在 | 变化 |
|---|---|---|---|
| `visualize.py` | 1750 LOC | **1682** | **-68 (-3.9%)** |
| `_viz_common.py` | (无) | 115 | 新建 |
| `_dot_common.py` | 81 | 170 | +89 (DOT helper 集中) |
| 5 子命令间 duplicate boilerplate | ~85 行 | **~0 行** | -85 |

### 如何加新 viz 子命令 (推荐范式)

```python
from cli._viz_common import (
    FILE_OPTION, FILELIST_OPTION, INCLUDE_OPTION, STRICT_OPTION,
    build_viz_tracer,
)
from trace.core.graph.analyzer._dot_common import (
    escape_dot_label, format_node_label_chain,
    sanitize_dot_id_inner, render_with_engine,
)

@app.command(name="controlflow")  # 假设加 visualize controlflow
def controlflow(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    strict: bool = STRICT_OPTION,
    target: str = typer.Option(None, "--target", "-t", ...),
    ...
):
    """你的 viz 子命令 docstring."""
    from trace.core.compiler import CompilationError
    from cli._common import handle_compilation_error
    try:
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            strict=strict, target_module=target,
        )
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return
    # 业务逻辑... (不用再说 12 行 tracer build)
```

vs 之前要写 ~85 行 boilerplate.

### Phase 3 留后

未来出现以下场景时再上 Phase 3:
- 需要 `OutputFormat` enum (DOT/MMD/HTML/PNG/SVG 统一抽象) — 目前 5 子命令各自处理
- 需要 `BaseVizRenderer` ABC — 需要插件机制时再抽象
- 需要 `viz/__init__.py` 统一入口 — 目前 `cli/commands/visualize.py` Typer group 工作

(这 3 项都是 YAGNI, 1 个维护者不需要, 加了反而 over-engineering.)

---

## 综合分析案例 (Python API)

`examples/comprehensive_analysis.py` 提供**信号图 + SVA + Coverage 一体化**分析和可视化:

```bash
python examples/comprehensive_analysis.py sim/tests/regression/test_data_path.sv /tmp/analysis

# 输出:
#   /tmp/analysis.json   - 完整分析结果 (节点, 边, SVA, Coverage)
#   /tmp/analysis.dot    - Graphviz DOT 格式 (可渲染为 PNG/SVG)
#   /tmp/analysis.mmd    - Mermaid 格式 (可嵌入 Markdown)
```

**包含**:
- 双维度风险评分 (功能复杂度 × 时序复杂度)
- SVA 结构提取 (sequence, property, assertion)
- Coverage 结构提取 (covergroup, coverpoint, bins)
- 信号分类 (时钟/复位/数据)
- 覆盖缺口报告
