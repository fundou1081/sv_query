"""
viz_legend.py — Shared legend + TL;DR helpers for all viz commands.

[Phase 6.3 + 6.4 2026-07-12] Single source of truth for:
- Legend (color/shape meanings)
- TL;DR rendering (visible box, not just a comment)

Usage:
    from trace.core.graph.analyzer.viz_legend import (
        render_legend, render_tldr_box, COLORS, EDGE_STYLES,
    )

All viz commands should use these helpers so legends are consistent.
"""

from __future__ import annotations
from typing import List


# ----------------------------------------------------------------------------
# Color palette — referenced from docs/VIZ_DESIGN_SPEC.md
# ----------------------------------------------------------------------------

COLORS = {
    # REG (pipeline / state): blue
    "REG": "#4488cc",
    "STATE_REG": "#cc8844",
    # Combinational: light blue
    "COMB": "#88bbdd",
    # Critical path: red
    "CRITICAL": "#cc2222",
    # MUX target: deeper blue (penwidth=3)
    "MUX": "#226699",
    # Control signal: 4-color cycle by target stage
    "CONTROL_STAGE_0": "#cc6633",  # warm orange
    "CONTROL_STAGE_1": "#aa5599",  # purple
    "CONTROL_STAGE_2": "#5599aa",  # teal
    "CONTROL_STAGE_3": "#aa8855",  # brown
    # RTL anomaly
    "ANOMALY_DANGLING": "#cc0000",
    "ANOMALY_X_DRIVER": "#cc8800",
    "ANOMALY_ORPHAN": "#888888",
    # TL;DR box
    "TLDR_BG": "#fffbe6",
    "TLDR_BORDER": "#ccaa00",
    "TLDR_TEXT": "#664400",
    # Legend
    "LEGEND_BG": "#f8f8f8",
    "LEGEND_BORDER": "#aaaaaa",
    "LEGEND_TEXT": "#333333",
}


def get_control_color(stage_idx: int) -> str:
    """Cycle through 4 control colors based on stage index."""
    return [
        COLORS["CONTROL_STAGE_0"],
        COLORS["CONTROL_STAGE_1"],
        COLORS["CONTROL_STAGE_2"],
        COLORS["CONTROL_STAGE_3"],
    ][stage_idx % 4]


# ----------------------------------------------------------------------------
# TL;DR box (Phase 6.4)
# ----------------------------------------------------------------------------

def render_tldr_box(text: str) -> List[str]:
    """[Phase 6.4] Render TL;DR as a visible plaintext box (not just a comment).

    Args:
        text: Summary text, e.g. "5 sub-modules · 335 nodes · 168 anomalies"

    Returns:
        List of DOT lines to append.

    Layout: small box at top, fontsize=12, with light yellow background.
    Uses rank=min to place it at the top in LR layout.
    """
    return [
        '  // === TL;DR ===',
        '  TLDR [shape=plaintext, label="' + text + '",',
        '        fontsize=12, fontcolor="' + COLORS["TLDR_TEXT"] + '",',
        '        fillcolor="' + COLORS["TLDR_BG"] + '", style="rounded,filled",',
        '        margin=0.1];',
    ]


# ----------------------------------------------------------------------------
# Legend box (Phase 6.3)
# ----------------------------------------------------------------------------

# Standard legend items for each viz type.
# Each item is (label, color, style_attrs).
LEGEND_ITEMS = {
    "pipeline": [
        ("Pipeline Reg", COLORS["REG"], "shape=box"),
        ("Combinational", COLORS["COMB"], "shape=box"),
        ("State Reg", COLORS["STATE_REG"], "shape=box"),
        ("Control→S0", COLORS["CONTROL_STAGE_0"], "shape=box"),
        ("Control→S1", COLORS["CONTROL_STAGE_1"], "shape=box"),
        ("Control→S2", COLORS["CONTROL_STAGE_2"], "shape=box"),
        ("Control→S3", COLORS["CONTROL_STAGE_3"], "shape=box"),
    ],
    "dataflow": [
        ("Data Reg", COLORS["REG"], "shape=box"),
        ("Combinational", COLORS["COMB"], "shape=box"),
        ("Control", COLORS["CONTROL_STAGE_0"], "shape=box,style=dashed"),
        ("Clock", "#996633", "shape=octagon"),
        ("DANGLING", COLORS["ANOMALY_DANGLING"], "shape=diamond"),
        ("X_DRIVER", COLORS["ANOMALY_X_DRIVER"], "shape=diamond"),
        ("ORPHAN", COLORS["ANOMALY_ORPHAN"], "shape=diamond"),
    ],
    "chain": [
        ("Input Port", "#22aa55", "shape=invhouse"),
        ("Output Port", "#cc3333", "shape=invhouse"),
        ("Pipeline Reg", COLORS["REG"], "shape=box"),
        ("Combinational", COLORS["COMB"], "shape=box"),
        ("Critical Path", COLORS["CRITICAL"], "shape=box,style=bold"),
        ("X_DRIVER", COLORS["ANOMALY_X_DRIVER"], "shape=diamond"),
    ],
    "timing": [
        ("Combinational", COLORS["COMB"], "shape=box"),
        ("Reg", COLORS["REG"], "shape=box"),
        ("Critical Path", COLORS["CRITICAL"], "shape=box"),
        ("DANGLING", COLORS["ANOMALY_DANGLING"], "shape=diamond"),
        ("X_DRIVER", COLORS["ANOMALY_X_DRIVER"], "shape=diamond"),
        ("ORPHAN", COLORS["ANOMALY_ORPHAN"], "shape=diamond"),
    ],
    "arch": [
        ("Sub-instance", "#22aa55", "shape=box"),
        ("User CPU", "#dd8822", "shape=box"),
        ("DANGLING", COLORS["ANOMALY_DANGLING"], "shape=diamond"),
        ("X_DRIVER", COLORS["ANOMALY_X_DRIVER"], "shape=diamond"),
        ("ORPHAN", COLORS["ANOMALY_ORPHAN"], "shape=diamond"),
    ],
}


def render_legend(viz_type: str, title: str = "Legend") -> List[str]:
    """[Phase 6.3] Render legend box at bottom-right of diagram.

    Args:
        viz_type: One of 'pipeline', 'dataflow', 'chain', 'timing', 'arch'
        title: Cluster label

    Returns:
        List of DOT lines.
    """
    items = LEGEND_ITEMS.get(viz_type, [])
    if not items:
        return []

    lines = [
        '',
        '  // === Legend ===',
        '  subgraph cluster_legend {',
        '    label="' + title + '";',
        '    style="rounded,filled";',
        '    fillcolor="' + COLORS["LEGEND_BG"] + '";',
        '    color="' + COLORS["LEGEND_BORDER"] + '";',
        '    fontsize=10;',
        '    rank=sink;',  # place at bottom in LR layout
    ]

    for i, (label, color, attrs) in enumerate(items):
        node_id = f"legend_{viz_type}_{i}"
        # Default style
        style_attrs = attrs + ',style="filled,rounded"'
        lines.append(
            f'    "{node_id}" [label="{label}" {style_attrs} '
            f'fillcolor="{color}" fontcolor="white" fontsize=9];'
        )

    lines.append('  }')
    return lines