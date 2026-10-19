# ==============================================================================
# visualize_plots.py — visualize 子命令: graph/dataflow/pipeline/compute/timed/gap/datapath
# ==============================================================================
"""[iter_254 T3-3] 从 `view/visualize.py` (2,376 行 / 10 个命令) 拆出: graph/dataflow/pipeline/compute/timed/gap/datapath。
命令注册仍在 `visualize.py` (避免循环 import); 本模块只含实现。
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from cli._paths import ensure_on_path, SRC_DIR  # noqa: E402
ensure_on_path(SRC_DIR)
import warnings

import typer

warnings.filterwarnings("ignore")

from cli._viz_common import (  # noqa: E402
    FILE_OPTION,
    FILELIST_OPTION,
    INCLUDE_OPTION,
    SHOW_SOURCE_OPTION,
    build_viz_tracer,
    get_viz_sources,
)
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.analyzer._dot_common import (  # noqa: E402
    format_node_label_chain,
    render_with_engine,
    sanitize_dot_id,
    sanitize_dot_id_inner,
)
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer
import logging

logger = logging.getLogger(__name__)

from cli.view.visualize_common import _emit_split_by_module, _run_gap_visualization

def graph(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    dot_output: str = typer.Option(None, "--svg", "-d", help="Output SVG file"),
    mmd_output: str = typer.Option(None, "--mmd", "-m", help="Output Mermaid file"),
    html_output: str = typer.Option(None, "--html", help="Output HTML file"),
    layout: str = typer.Option("TB", "--layout", "-l", help="Layout: TB (top-bottom) or LR (left-right)"),
    no_edges: bool = typer.Option(False, "--no-edges", help="Hide edges"),
    show_labels: bool = typer.Option(False, "--show-labels", help="Show edge labels (type)"),
    show_conditions: bool = typer.Option(False, "--show-conditions", help="Show driver conditions on edges"),
    max_edges: int = typer.Option(200, "--max-edges", help="Max edges to display"),
    exclude_clock: bool = typer.Option(False, "--exclude-clock", help="Exclude clock edges"),
    exclude_reset: bool = typer.Option(False, "--exclude-reset", help="Exclude reset edges"),
    cluster_modules: bool = typer.Option(False, "--cluster-modules", help="Cluster nodes by module"),
    layout_engine: str = typer.Option("dot", "--layout-engine", help="Layout engine: dot, neato, fdp"),
    cache: bool = typer.Option(
        False, "--cache", help="Use cache for faster loading (skip re-parsing if file unchanged)"
    ),
    module_only: bool = typer.Option(False, "--module-only", help="Show only top-module signals (skip sub-module internals, show only port/instantiation level)"),
    show_source: bool = SHOW_SOURCE_OPTION,
) -> None:
    """可视化信号图（包含数据流关系）"""

    # [FIX 2026-08-13] show_source 现已接入 SVG 渲染链路:
    #   graph 命令把 show_source 传进 render_dataflow config, 由
    #   viz_engine._render_svg_direct 在 leaf 节点下方标注 file:line +
    #   URL=/tooltip= (SVG <a href> + <title> 承载).
    #   旧 DOT 路径 (viz_dot_renderer) 已废弃, 此链路通过 VizNode.file/line
    #   → elk_bridge _meta → viz_engine 渲染.

    from cli._common import handle_compilation_error
    from trace.core.compiler import CompilationError
    from trace.core.graph.viz import VizBuildOptions, build_viz_data
    from trace.core.graph.viz.viz_engine import render_dataflow

    try:
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            use_cache=cache,
        )
    except CompilationError as e:
        handle_compilation_error(e)
        return

    # [V12] 统一 ELK.js 渲染管线
    from trace.core.graph.analyzer.signal_classifier import classify_graph
    classification = classify_graph(graph)

    # Normalize title: strip path+ext to avoid --file (.sv) vs --filelist (.f) diff
    title = Path(file or filelist).stem if (file or filelist) else "Signal Graph"
    viz = build_viz_data(graph, VizBuildOptions(
        target_module=title,
        max_edges=max_edges,
        include_node_class=True,
        classification=classification,
        include_edge_condition=show_conditions,
        include_edge_expression=True,
    ))
    svg = render_dataflow(viz, {"title": title, "show_source": show_source})

    if dot_output:
        Path(dot_output).write_text(svg)
        typer.echo(f"\u2713 SVG: {dot_output}")
    else:
        typer.echo(svg)

def dataflow(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    module: str = typer.Option(None, "--module", "-m", help="Focus on specific module (filter edges to this module's signals)"),
    dot_output: str = typer.Option(None, "--svg", "-d", help="Output SVG file. Prefix when --split-by-module."),
    include_clk_rst: bool = typer.Option(False, "--with-clk-rst", help="Include clock/reset nodes"),
    split_by_module: bool = typer.Option(False, "--split-by-module", help="[Phase 6.1 2026-07-12] Generate one DOT per sub-instance (e.g. darksocv.bridge0). Output: <prefix>_<sub>.dot"),
    show_source: bool = SHOW_SOURCE_OPTION,
) -> None:
    """数据流图: 显示 data path (运算表达式) + 关键 control 边 (enable/valid/mux sel)

    基于 SignalGraph 自动分类 clock/reset/control/data, 生成 DOT 图:
    - 数据边: 蓝色实线,标注运算表达式 (a+b, {rx, sreg[10:1]})
    - 控制边: 橙色虚线 (valid/ready/enable -> 数据目标)
    - MUX 目标: 加粗边 (多源数据汇聚)
    - 寄存器: 粗边框

    [Phase 6.1] Use --split-by-module to split into per-instance DOTs when graph is large.

    [Phase B 2026-07-17] --file/--filelist/--include via shared options.
    """
    from cli._common import handle_compilation_error
    from trace.core.compiler import CompilationError
    from trace.core.graph.analyzer.signal_classifier import classify_graph
    from trace.core.graph.viz import VizBuildOptions, build_viz_data
    from trace.core.graph.viz.viz_engine import render_dataflow

    try:
        # [Phase 3 2026-07-11] Pass --module as target_module so SignalGraph uses user namespace
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            target_module=module,
        )
    except CompilationError as e:
        handle_compilation_error(e)
        return

    classification = classify_graph(graph)
    typer.echo(f"  Data nodes: {len(classification.data_nodes)}", err=True)
    typer.echo(f"  Control nodes: {len(classification.control_nodes)}", err=True)
    typer.echo(f"  Clock nodes: {len(classification.clock_nodes)}", err=True)

    # [V12] ELK.js 渲染管线
    viz = build_viz_data(graph, VizBuildOptions(
        target_module=module or file or filelist or "",
        include_node_class=True,
        classification=classification,
        include_edge_expression=True,
    ))
    # Strip path+ext for consistent --file vs --filelist titles
    title = module or (Path(file or filelist).stem if (file or filelist) else "Dataflow")
    svg = render_dataflow(viz, {"title": f"Dataflow: {title}"})

    if dot_output:
        Path(dot_output).write_text(svg)

    if split_by_module:
        _emit_split_by_module(graph, classification, module or file or filelist or "", dot_output, include_clk_rst, Path)
        typer.echo(f"✓ SVG: {dot_output}")
    else:
        typer.echo(svg)

def pipeline(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    module: str = typer.Option(None, "--module", "-m", help="Focus on specific module"),
    dot_output: str = typer.Option(None, "--svg", "-d", help="Output SVG file"),
    json_output: bool = typer.Option(
        False, "--json", "-j",
        help="[iter_198] 输出**结构化 JSON** (PipelineInfo: stages/延迟/寄存器分类) 到 stdout, "
             "不渲染可视化。诊断与告警仍走 stderr (stdout 为纯 JSON)。"
             "文本结构化输出是 pipeline 的验收标准 (可视化暂冻结)。",
    ),
    max_comb_per_stage: int = typer.Option(8, "--max-comb-per-stage", help="[P0 fix 2026-07-10] Max combinational nodes per stage (default 8)"),
    max_control_nodes: int = typer.Option(12, "--max-control-nodes", help="[P0 fix 2026-07-17] Max control signals in header row (default 12, was 8). 0 = hide all."),
    unfold: bool = typer.Option(False, "--unfold", help="[Phase 6.2 2026-07-12] Disable stage folding, show all stages individually"),
    fold_every: int = typer.Option(5, "--fold-every", help="[Phase 6.2] Number of stages per fold group when total > 30 (default 5)"),
    timing: bool = typer.Option(False, "--timing", help="[Phase 7 2026-07-13] Render as parallel pipeline timing diagram (lanes × cycles) instead of folded/unfolded stage flow"),
    load_path: bool = typer.Option(False, "--load-path", help="[V6.6 deprecated] Use --timing instead. Render by load path (experimental, may be removed)"),
) -> None:
    """Pipeline 流图: 检测 register chain -> 划分 time cycle/stage

    从 SignalGraph 自动检测 pipeline 结构:
    - 识别 pipeline registers (排除 clock/reset/state-machine regs)
    - 每个 stage 一个 subgraph: 含 registers + 组合逻辑
    - 控制信号 (valid/stall) 标记为跨 stage 虚线
    - 左->右布局 = 时间流方向

    [P0 fix 2026-07-10] 控制节点不再堆成 31k PNG, 默认限制每 stage 8 个组合节点 +
    控制信号区最多 30 个节点。用 --max-control-nodes 0 隐藏控制信号区。

    [Phase B 2026-07-17] --file/--filelist/--include via shared options.
    """
    from cli._common import emit_json_error, handle_compilation_error, warn_flags_ignored_by_json
    from trace.core.compiler import CompilationError
    from trace.core.graph.analyzer.pipeline_viz import detect_pipeline
    from trace.core.graph.analyzer.signal_classifier import classify_graph
    from trace.core.graph.viz import VizBuildOptions, build_viz_data
    from trace.core.graph.viz.viz_engine import render_dataflow

    try:
        # [Phase 3 2026-07-11] Pass --module as target_module for correct namespace
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            target_module=module,
        )
    except CompilationError as e:
        # [iter_201 F1] --json 模式下错误也要是结构化 JSON (stdout), 不只 stderr
        if json_output:
            emit_json_error("visualize pipeline", e)
        handle_compilation_error(e)
        return

    classification = classify_graph(graph)
    info = detect_pipeline(graph, classification)
    info.module_name = module or file or filelist or ""

    # [iter_201 F2/F3] --json 下被忽略的输出/模式 flag 必须显式告警 (过去静默丢弃)
    warn_flags_ignored_by_json(json_output, {
        "--svg": dot_output, "--timing": timing, "--load-path": load_path,
        "--unfold": unfold,
    })

    from trace.core.compiler import is_quiet as _is_quiet  # [iter_202]
    if not _is_quiet():
        typer.echo(f"  Pipeline regs: {len(info.pipeline_regs)}", err=True)
        typer.echo(f"  Control regs: {len(info.control_regs)}", err=True)
        typer.echo(f"  State regs: {len(info.state_regs)}", err=True)
        typer.echo(f"  Stages: {info.total_latency}", err=True)

    # [iter_198] --json: 结构化输出是 pipeline 的验收标准 → 只导数据, 不渲染可视化。
    # 信封与 `sv_query timing analyze --json` 对齐 ({ok, command, result}),
    # 便于统一消费/断言; 诊断 (上面几行) 走 stderr → stdout 保持纯 JSON。
    if json_output:
        import dataclasses
        import json as _json

        payload = {
            "ok": True,
            "command": "visualize pipeline",
            "result": {
                "module": info.module_name,
                "total_latency": info.total_latency,
                "stage_count": len(info.stages),
                "pipeline_regs": list(info.pipeline_regs),
                "control_regs": list(info.control_regs),
                "state_regs": list(info.state_regs),
                "stages": [dataclasses.asdict(st) for st in info.stages],
            },
        }
        typer.echo(_json.dumps(payload, ensure_ascii=False, indent=2))
        return

    # [V6.7] 统一 VizData 渲染管线 — pipeline stages
    # stage_map: pipeline regs + comb nodes + state regs (FSM) + control inputs
    stage_map = {}
    for s in info.stages:
        stage_map[s.stage_id] = s.reg_nodes + s.comb_nodes + s.data_inputs
    # State regs (FSM) always in stage 0
    stage_map[0] = list(set(stage_map.get(0, []) + info.state_regs))

    viz = build_viz_data(graph, VizBuildOptions(
        target_module=module or file or filelist or "",
        include_node_class=True,
        classification=classification,
        include_node_stage=True,
        pipeline_stages=stage_map,
        include_edge_expression=True,
        include_edge_condition=True,
    ))
    title = module or file or filelist or "Pipeline"
    svg = render_dataflow(viz, {"title": f"Pipeline: {title}"})

    if dot_output:
        Path(dot_output).write_text(svg)
        typer.echo(f"✓ SVG: {dot_output}")
    else:
        typer.echo(svg)

def compute(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    module: str = typer.Option(None, "--module", "-m", help="Target module"),
    dot_output: str = typer.Option(None, "--svg", "-d", help="Output SVG file"),
) -> None:
    """运算架构图: 边上直接显示运算符 (+, -, &, >>, ==, etc.)

    基于 SignalSource.op 字段, 映射 pyslang 操作符名到可读符号:
    - 算术 (Add/Subtract/Multiply): 橙色
    - 逻辑 (And/Or/Xor): 蓝色
    - 移位 (LogicalShiftLeft/Right): 绿色
    - 比较 (GreaterThan/LessThan/Equality): 紫色
    - MUX 目标: 粗边

    V6.7 新命令.
    """
    from cli._common import handle_compilation_error
    from trace.core.compiler import CompilationError
    from trace.core.graph.viz import VizBuildOptions, build_viz_data
    from trace.core.graph.viz.viz_engine import render_dataflow

    try:
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            target_module=module,
        )
    except CompilationError as e:
        handle_compilation_error(e)
        return

    # [V12] 运算架构图: ELK.js 渲染
    title = module or file or filelist or "Compute"
    viz = build_viz_data(graph, VizBuildOptions(
        target_module=title,
        include_edge_expression=True,
        include_edge_condition=True,
    ))
    svg = render_dataflow(viz, {"title": f"Compute: {title}"})

    if dot_output:
        Path(dot_output).write_text(svg)
        typer.echo(f"\u2713 SVG: {dot_output}")
    else:
        typer.echo(svg)

def timed(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    module: str = typer.Option(None, "--module", "-m", help="Target module"),
    dot_output: str = typer.Option(None, "--svg", "-d", help="Output SVG file"),
) -> None:
    """时间轴运算架构图: 从左到右时间轴 + 运算作为圆形节点

    每个 cycle 一个 vertical cluster (Cycle 0, Cycle 1, ...).
    REG 寄存器是 cycle 边界 (方框).
    运算 (+/×/>>) 是独立圆形节点，按颜色分类:
    - 算术: 橙色, 逻辑: 蓝色, 移位: 绿色

    V6.7 新命令.
    """
    from cli._common import handle_compilation_error
    from trace.core.compiler import CompilationError
    from trace.core.graph.analyzer.pipeline_viz import detect_pipeline
    from trace.core.graph.analyzer.signal_classifier import classify_graph
    from trace.core.graph.viz import VizBuildOptions, build_viz_data
    from trace.core.graph.viz.viz_engine import render_dataflow

    try:
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            target_module=module,
        )
    except CompilationError as e:
        handle_compilation_error(e)
        return

    classification = classify_graph(graph)
    info = detect_pipeline(graph, classification)

    # Build stage_map for VizData
    stage_map = {}
    for s in info.stages:
        stage_map[s.stage_id] = s.reg_nodes + s.comb_nodes + s.data_inputs
    stage_map[0] = list(set(stage_map.get(0, []) + info.state_regs))

    # [V6.7 fix] CONST/input nodes driving a REG inherit that REG's stage
    node_stage: dict[str, int] = {}
    for sid, node_list in stage_map.items():
        for nid in node_list:
            node_stage[nid] = sid
    # [V6.7 fix] CONST/PORT_IN nodes: push to the stage where the OP happens
    # (the stage BEFORE the REG that consumes them)
    # Use the initial pipeline stage of the dst REG, not the mutable node_stage
    reg_stage_map: dict[str, int] = {}
    for s in info.stages:
        for nid in s.reg_nodes:
            reg_stage_map[nid] = s.stage_id
    for src, dst in graph.edges():
        if src in graph.nodes() and dst in reg_stage_map:
            node = graph.get_node(src)
            if node and (node.kind.name == "CONST" or node.kind.name == "PORT_IN"):
                dst_reg_stage = reg_stage_map[dst]
                op_stage = max(0, dst_reg_stage - 1)
                # Only move if currently in the wrong stage
                if op_stage < dst_reg_stage:
                    for sid, nl in list(stage_map.items()):
                        if src in nl:
                            stage_map[sid] = [x for x in nl if x != src]
                    node_stage[src] = op_stage
                    stage_map[op_stage] = list(set(stage_map.get(op_stage, []) + [src]))

    title = module or file or filelist or "Timed Compute"
    viz = build_viz_data(graph, VizBuildOptions(
        target_module=title,
        include_node_stage=True,
        pipeline_stages=stage_map,
        include_edge_expression=True,
        include_edge_condition=True,
        include_node_class=True,
        classification=classification,
    ))
    svg = render_dataflow(viz, {"title": f"Timed: {title}"})

    if dot_output:
        Path(dot_output).write_text(svg)
        typer.echo(f"\u2713 SVG: {dot_output}")
    else:
        typer.echo(svg)

def gap(
    file: str = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    dot_output: str = typer.Option(None, "--svg", "-d", help="Output SVG file"),
    html_output: str = typer.Option(None, "--html", help="Output HTML file"),
    min_risk: float = typer.Option(20.0, "--min-risk", "-r", help="Minimum risk threshold"),
    cache: bool = typer.Option(False, "--cache", help="Use cache for faster loading"),
) -> None:
    """可视化验证缺口（高亮无覆盖的高风险信号及其数据流关系）"""
    _run_gap_visualization(file, dot_output, html_output, min_risk, cache)

def datapath(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    target: str = typer.Option(
        "top", "--target", "-t",
        help="Target module",
    ),
    focus: str = typer.Option(
        "", "--focus", "-F",
        help="[可选] 只画指定信号的 N-hop 邻域",
    ),
    focus_depth: int = typer.Option(
        2, "--focus-depth", "-d",
        help="Focus 邻域的 BFS 深度 (默认 2)",
    ),
    stages: str = typer.Option(
        "auto", "--stages",
        help="Stage 划分: auto(默认) | reg | depth2 | depth3",
    ),
    show_control: bool = typer.Option(
        True, "--show-control/--no-control",
        help="显示控制/条件边 (默认开启)",
    ),
    show_source: bool = SHOW_SOURCE_OPTION,
    dot: str = typer.Option(
        "", "--emit-dot",
        help="Output DOT file (raw DOT)",
    ),
    png: str = typer.Option(
        "", "--png",
        help="Output PNG file (auto-call dot -Tpng)",
    ),
    svg: str = typer.Option(
        "", "--svg",
        help="Output SVG file (auto-call dot -Tsvg)",
    ),
):
    """[V6.9] 定点数计算架构图: 运算链、时延、控制、位宽、选择逻辑。

    Example:
        sv_query visualize datapath -f binary_ops.sv --target binary_ops_test --png /tmp/dp.png
        sv_query visualize datapath -f alu.sv --target alu_top --focus result --depth 3 --png /tmp/dp.png
    """
    tracer, graph = build_viz_tracer(
        file=file, filelist=filelist, include=include,
        
    )

    # Build VizData
    from trace.core.graph.analyzer.signal_classifier import classify_graph as _classify
    from trace.core.graph.viz.viz_data_builder import VizBuildOptions, build_viz_data
    from trace.core.graph.viz.viz_engine import render_dataflow

    try:
        classification = _classify(graph)
    except Exception:
        classification = None

    opts = VizBuildOptions(
        target_module=target,
        include_edge_expression=True,
        include_edge_condition=True,
        include_node_class=True,
        include_node_stage=True,
        classification=classification,
    )
    viz = build_viz_data(graph, opts)

    # Render (V12 ELK.js)
    cfg = {
        "title": f"Datapath: {target}",
        "layout": "LR",
        "focus": focus,
        "focus_depth": focus_depth,
        "show_control": show_control,
        "show_source": show_source,
    }
    svg_text = render_dataflow(viz, cfg)

    # Output
    if dot:
        from pathlib import Path
        Path(dot).parent.mkdir(parents=True, exist_ok=True)
        Path(dot).write_text(svg_text)
        typer.echo(f"✓ SVG: {dot}")

    if png:
        from pathlib import Path
        import subprocess
        svg_path = str(Path(png).with_suffix('.svg'))
        Path(svg_path).write_text(svg_text)
        rc = subprocess.run(['cairosvg', svg_path, '-o', png], capture_output=True).returncode
        if rc == 0:
            typer.echo(f"✓ PNG: {png}")
        else:
            typer.echo(f"✗ PNG render failed (rc={rc})", err=True)

    if svg:
        from pathlib import Path
        Path(svg).parent.mkdir(parents=True, exist_ok=True)
        Path(svg).write_text(svg_text)
        typer.echo(f"✓ SVG: {svg}")

    if not (dot or png or svg):
        typer.echo(svg_text)
