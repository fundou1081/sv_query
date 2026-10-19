# ==============================================================================
# visualize.py - 信号图可视化命令
# ==============================================================================
"""
强大的信号图可视化功能

Usage:
  python run_cli.py visualize graph -f top.sv --dot /tmp/graph.dot --html /tmp/graph.html
  python run_cli.py visualize gap -f top.sv --html /tmp/gap.html
  python run_cli.py visualize graph -f top.sv --layout LR --no-edges
"""

import sys
from collections import defaultdict
from pathlib import Path

from cli._paths import ensure_on_path, SRC_DIR  # noqa: E402
ensure_on_path(SRC_DIR)
import warnings

import typer

warnings.filterwarnings("ignore")

# [Phase B 2026-07-17] 共享 viz 子命令的 typer options + build_viz_tracer helper
from cli._viz_common import (
    FILE_OPTION,
    FILELIST_OPTION,
    INCLUDE_OPTION,
    SHOW_SOURCE_OPTION,
    build_viz_tracer,
    get_viz_sources,
)
from trace.core.covergroup_extractor import CovergroupExtractor

# [Phase B 2026-07-17] 共享 DOT helpers (从 _dot_common 移过来)
from trace.core.graph.analyzer._dot_common import (
    format_node_label_chain,
    render_with_engine,
    sanitize_dot_id,
    sanitize_dot_id_inner,
)

# [V6.7] SignalGraphViewer removed — use trace.core.graph.viz instead
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer
import logging

logger = logging.getLogger(__name__)

vis_app = typer.Typer(help="Signal graph visualization: DOT, Mermaid, HTML with data flow edges")

# [iter_254 T3-3] 实现拆到 5 个模块 (原 2,376 行 → 5 文件); 这里只做注册。
from cli.view.visualize_plots import (  # noqa: E402
    graph, dataflow, pipeline, compute, timed, gap, datapath,
)
from cli.view.visualize_chain import chain  # noqa: E402
from cli.view.visualize_module import module  # noqa: E402
from cli.view.visualize_teach import teach  # noqa: E402

vis_app.command("graph")(graph)
vis_app.command("dataflow")(dataflow)
vis_app.command("pipeline")(pipeline)
vis_app.command("compute")(compute)
vis_app.command("timed")(timed)
vis_app.command("gap")(gap)
vis_app.command("datapath")(datapath)
vis_app.command("chain")(chain)
vis_app.command("module")(module)
vis_app.command("teach")(teach)
