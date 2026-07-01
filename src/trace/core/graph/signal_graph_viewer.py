# ==============================================================================
# signal_graph_viewer.py - 信号图可视化器
# ==============================================================================
"""
强大的信号图可视化功能：
- 支持分层布局、风险热力图、覆盖状态标记
- 边表示数据流关系（驱动/时钟/复位）
- 可配置过滤、聚类、样式
- 输出 DOT / Mermaid / HTML
"""

import sys
from pathlib import Path

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import re


class SignalGraphViewer:
    """
    强大的信号图可视化器

    使用示例:
        viewer = SignalGraphViewer(graph)
        viewer.configure(
            layout='TB',
            show_edges=True,
            edge_filter={'exclude_clock', 'exclude_reset'},
            node_style={'risk_color': True, 'cover_marker': True},
            cluster_by='risk_level'
        )
        viewer.render_dot('/tmp/output.dot')
        viewer.render_mermaid('/tmp/output.mmd')
        viewer.render_html('/tmp/output.html')
    """

    # 颜色常量
    RISK_COLORS = {
        "CRITICAL": "#ff0000",
        "HIGH": "#ff8800",
        "MEDIUM": "#ffcc00",
        "LOW": "#00cc00",
    }

    COVER_COLORS = {
        "BOTH": "#00aa00",
        "SVA": "#0088ff",
        "COV": "#ffaa00",
        "NONE": "#ff6666",
    }

    NODE_KIND_SHAPES = {
        "REG": "box",
        "PORT_IN": "ellipse",
        "PORT_OUT": "ellipse",
        "SIGNAL": "diamond",
        "CONST": "parallelogram",
        "INSTANTIATED_MODULE": "folder",
    }

    EDGE_COLORS = {
        "DRIVER": "#333333",
        "CLOCK": "#8888ff",
        "RESET": "#ff8888",
        "CONNECTION": "#aaaaaa",
        "BIT_SELECT": "#aaaaaa",
        "DATA": "#666666",
    }

    def __init__(self, graph, sva_signals=None, cov_signals=None):
        """
        初始化可视化器

        Args:
            graph: SignalGraph 对象
            sva_signals: SVA 覆盖的信号名集合
            cov_signals: Coverage 覆盖的信号名集合
        """
        self.graph = graph
        self.sva_signals = sva_signals or set()
        self.cov_signals = cov_signals or set()

        # 默认配置
        self.config = {
            "layout": "TB",  # TB (top-bottom) / LR (left-right)
            "show_edges": True,  # 是否显示边
            "edge_filter": set(),  # 'exclude_clock', 'exclude_reset', 'exclude_constant'
            "max_edges": 500,  # 边的最大数量（防止过于密集）
            "node_style": {
                "risk_color": True,  # 风险等级着色
                "cover_marker": True,  # 覆盖状态标记
                "show_type": True,  # 显示节点类型
                "show_fan": True,  # 显示 fan-in/fan-out
            },
            "cluster_by": None,  # 'module', 'risk_level', 'cover_status', None
            "cluster_modules": True,  # 按模块聚类（跨模块边用虚线）
            "module_only": False,  # 只显示顶层模块信号（跳过子模块内部信号）
            "highlight_gaps": True,  # 高亮高风险无覆盖信号
            "min_risk_for_highlight": 20.0,
            "edge_labels": False,  # 显示边类型标签 (CLOCK/RESET/DRIVER)
            "edge_conditions": False,  # 显示驱动条件 (如 if (cond) 才驱动)
            "rank_separation": 0.5,  # 层级间距
            "node_spacing": 0.3,  # 节点间距
            "focus_risk_threshold": 40.0,  # 高风险阈值，触发聚焦模式
            "layout_engine": "dot",  # 'dot' (层次布局) / 'neato' (力导向) / 'fdp' (分组布局)
        }

        self._risk_cache = {}

    def _extract_modules(self) -> dict[str, list[str]]:
        """从节点 ID 中提取模块层级信息

        Returns:
            Dict[str, List[str]]: 模块名 -> 节点 ID 列表
        """
        modules = {}
        for node_id in self.graph.nodes():
            parts = node_id.split(".")
            if len(parts) >= 2:
                # 模块路径：module.instance.signal 或 module.signal
                module = parts[0]
                if module not in modules:
                    modules[module] = []
                modules[module].append(node_id)
            else:
                # 顶层信号
                if "__top__" not in modules:
                    modules["__top__"] = []
                modules["__top__"].append(node_id)
        return modules

    def _get_module_name(self, node_id: str) -> str:
        """获取节点所属的模块名"""
        parts = node_id.split(".")
        if len(parts) >= 2:
            return parts[0]
        return "__top__"

    def _is_cross_module(self, src: str, dst: str) -> bool:
        """判断是否为跨模块边"""
        return self._get_module_name(src) != self._get_module_name(dst)

    def configure(self, **kwargs: object) -> object:
        """配置可视化参数"""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
            elif key == "node_style" and isinstance(value, dict):
                self.config["node_style"].update(value)
            elif key == "edge_filter" and isinstance(value, (set, list)):
                self.config["edge_filter"] = set(value)
        return self

    def _compute_risk(self, node_id: str) -> tuple[float, str]:
        """计算节点风险分数和等级"""
        if node_id in self._risk_cache:
            return self._risk_cache[node_id]

        node = self.graph.get_node(node_id)
        if node is None:
            return 0.0, "LOW"

        fan_in = self.graph.in_degree(node_id)
        fan_out = self.graph.out_degree(node_id)

        func = fan_in * 3 + fan_out * 2
        func += 15 if fan_in >= 3 else 0
        func += 10 if fan_out >= 3 else 0

        timing = 15 if node.kind.name == "REG" else 0
        timing += fan_in * 2

        total = func + timing
        if total >= 40:
            level = "CRITICAL"
        elif total >= 25:
            level = "HIGH"
        elif total >= 15:
            level = "MEDIUM"
        else:
            level = "LOW"

        self._risk_cache[node_id] = (total, level)
        return total, level

    def _get_cover_status(self, name: str) -> str:
        """获取覆盖状态"""
        has_sva = name in self.sva_signals
        has_cov = name in self.cov_signals
        if has_sva and has_cov:
            return "BOTH"
        elif has_sva:
            return "SVA"
        elif has_cov:
            return "COV"
        return "NONE"

    def _should_show_edge(self, src: str, dst: str, edge) -> bool:
        """判断边是否应该显示"""
        ek = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)

        if "exclude_clock" in self.config["edge_filter"] and ek in ("CLOCK", "PosEdge"):
            return False
        if "exclude_reset" in self.config["edge_filter"] and ek in ("RESET", "NegEdge"):
            return False
        if "exclude_constant" in self.config["edge_filter"]:
            if src.startswith("1'b") or dst.startswith("1'"):
                return False

        return True

    def _is_top_module_signal(self, node_id: str) -> bool:
        """判断是否为顶层模块信号（而非子模块内部信号）

        显示: module.signal (深度<=2, 即顶层模块的端口/内部信号)
        隐藏: module.inst.signal (深度>=3, 即子模块实例的内部信号)
        """
        parts = node_id.split(".")
        # 深度 1: signal (顶层无模块前缀)
        # 深度 2: module.signal (顶层模块的信号)
        # 深度 >=3: module.inst.signal (子模块实例内部)
        return len(parts) <= 2

    def _filter_edges(self, edges: list[tuple]) -> list[tuple]:
        """过滤边，防止过于密集"""
        result = []
        module_only = self.config.get("module_only", False)
        for src, dst in edges:
            # module_only 模式: 跳过连接隐藏节点的边
            if module_only:
                if not self._is_top_module_signal(src) or not self._is_top_module_signal(dst):
                    continue
            edge = self.graph.get_edge(src, dst)
            if edge is None:
                continue
            if not self._should_show_edge(src, dst, edge):
                continue
            result.append((src, dst, edge))

        # 如果边太多，按风险排序，只保留高风险路径的边
        if len(result) > self.config["max_edges"]:
            # 计算每条边的风险分（两端节点的风险分之和）
            edge_risks = []
            for src, dst, edge in result:
                r_src, _ = self._compute_risk(src)
                r_dst, _ = self._compute_risk(dst)
                edge_risks.append((src, dst, edge, r_src + r_dst))

            # 按风险排序，保留最高的
            edge_risks.sort(key=lambda x: x[3], reverse=True)
            result = [(s, d, e) for s, d, e, _ in edge_risks[: self.config["max_edges"]]]

        return result

    def render_dot(self, output_path: str, title: str = "Signal Graph") -> str:
        """渲染为 DOT 格式

        增强功能：
        - 模块聚类（cluster_modules）
        - 跨模块边用虚线区分
        - 高风险区域聚焦模式（focus_risk_threshold）
        """
        # 布局引擎选择
        self.config.get("layout_engine", "dot")

        dot_lines = [
            "digraph signal_graph {",
            f"  rankdir={self.config['layout']};",
            '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10];',
            f'  label="{title}";',
            "  splines=spline;",
            "  nodesep=0.4;",
            "  ranksep=0.6;",
            "  concentrate=true;",
            "  compound=true;",
            '  size="10";',
            "  ratio=compress;",
        ]

        # 模块聚类
        modules = self._extract_modules() if self.config.get("cluster_modules", False) else {}

        # 收集所有节点（用于后续边处理）
        node_name_map = {}  # full_node_id -> safe_name

        # 生成节点声明
        for node_id in self.graph.nodes():
            # module_only 模式: 跳过子模块内部信号
            if self.config.get("module_only", False) and not self._is_top_module_signal(node_id):
                continue
            node = self.graph.get_node(node_id)
            if node is None:
                continue

            name = node_id.split(".")[-1]
            risk_score, risk_level = self._compute_risk(node_id)
            cover_status = self._get_cover_status(name)

            # 颜色
            if self.config["node_style"]["risk_color"]:
                fillcolor = self.RISK_COLORS.get(risk_level, "#cccccc") + "22"
            else:
                fillcolor = "#f0f0f0"

            shape = self.NODE_KIND_SHAPES.get(str(node.kind), "box")

            # 标签
            labels = [name]
            if self.config["node_style"]["show_type"]:
                labels.append(str(node.kind).split(".")[-1])
            if self.config["node_style"]["show_fan"]:
                fan_in_count = 0
                fan_out_count = 0
                for pred in self.graph.predecessors(node_id):
                    edge = self.graph.get_edge(pred, node_id)
                    if edge and edge.kind.name == "DRIVER":
                        fan_in_count += 1
                for succ in self.graph.successors(node_id):
                    edge = self.graph.get_edge(node_id, succ)
                    if edge and edge.kind.name == "DRIVER":
                        fan_out_count += 1
                labels.append(f"In:{fan_in_count} Out:{fan_out_count}")

            # 覆盖标记
            if self.config["node_style"]["cover_marker"]:
                if cover_status == "BOTH":
                    labels.append("✓🟡")
                elif cover_status == "SVA":
                    labels.append("✓")
                elif cover_status == "COV":
                    labels.append("🟡")
                elif risk_score >= self.config["min_risk_for_highlight"]:
                    labels.append("🚨")

            # Escape DOT-special chars in label strings (handles ), \\n, quotes, etc.)
            def _dot_label_escape(s):
                return (s.replace("\\", "\\\\").replace('"', '\\"')
                        .replace("\n", "\\n").replace("(", "\\(").replace(")", "\\)"))

            label_str = "\\n".join(_dot_label_escape(l) for l in labels)
            color = (
                self.COVER_COLORS.get(cover_status, "#888888")
                if self.config["node_style"]["cover_marker"]
                else self.RISK_COLORS.get(risk_level, "#888888")
            )

            # 处理特殊字符 — 转义 DOT special chars: \", (, ), [, ], -, :, \
            def _dot_escape(s):
                return s.replace("\\", "\\\\").replace('"', '\\"').replace("(", "_").replace(")", "_").replace("[", "_").replace("]", "_").replace("-", "_").replace(":", "_")

            name_escaped = _dot_escape(name)

            if "'" in name:
                safe_name = f'"{name_escaped}"'
            else:
                # 当启用模块聚类时，使用完整层级路径作为节点名，避免同名信号冲突
                if self.config.get("cluster_modules", False):
                    # 用下划线替换点号，保留完整路径信息
                    safe_name = node_id.replace(".", "_").replace("[", "_").replace("]", "_").replace("(", "_").replace(")", "_")
                else:
                    safe_name = name_escaped
            node_name_map[node_id] = safe_name

            dot_lines.append(
                f'    {safe_name}[label="{label_str}" shape={shape} fillcolor="{fillcolor}" color="{color}"];'
            )

        dot_lines.append("")

        # 模块聚类 subgraph
        if modules and self.config.get("cluster_modules", False):
            for module_name, node_ids in sorted(modules.items()):
                dot_lines.append(f'    subgraph "cluster_{module_name}" {{')
                dot_lines.append(f'        label="{module_name}";')
                dot_lines.append('        style=filled; fillcolor="#f0f0f044";')
                for nid in sorted(node_ids):
                    if nid in node_name_map:
                        dot_lines.append(f"        {node_name_map[nid]};")
                dot_lines.append("    }")
                dot_lines.append("")

        # 按类型排列层级：PORT_IN 在上方，PORT_OUT 在下方
        in_nodes = []
        out_nodes = []
        reg_nodes = []
        other_nodes = []
        def _rank_safe_name(name):
            esc = name.replace("\\", "\\\\").replace('"', '\\"').replace("(", "_").replace(")", "_")
            esc = esc.replace("[", "_").replace("]", "_").replace("-", "_").replace(":", "_")
            if "'" in name or "." in name:
                return f'"{esc}"'
            return esc

        for node_id in self.graph.nodes():
            if self.config.get("module_only", False) and not self._is_top_module_signal(node_id):
                continue
            node = self.graph.get_node(node_id)
            if node is None:
                continue
            name = node_id.split(".")[-1]
            safe_name = _rank_safe_name(name)
            if "PORT_IN" in str(node.kind):
                in_nodes.append(safe_name)
            elif "PORT_OUT" in str(node.kind):
                out_nodes.append(safe_name)
            elif "REG" in str(node.kind):
                reg_nodes.append(safe_name)
            else:
                other_nodes.append(safe_name)

        if in_nodes:
            dot_lines.append(f"    {{ rank=source; {' '.join(in_nodes)}; }}")
        if out_nodes:
            dot_lines.append(f"    {{ rank=sink; {' '.join(out_nodes)}; }}")

        dot_lines.append("")

        # 按类型排列层级：PORT_IN 在上方，PORT_OUT 在下方
        # 注意：当启用模块聚类时，不使用 rank 约束（与 subgraph 冲突）
        if not self.config.get("cluster_modules", False):
            in_nodes = []
            out_nodes = []
            reg_nodes = []
            other_nodes = []

            for node_id in self.graph.nodes():
                if self.config.get("module_only", False) and not self._is_top_module_signal(node_id):
                    continue
                node = self.graph.get_node(node_id)
                if node is None:
                    continue
                name = node_id.split(".")[-1]
                safe_name = _rank_safe_name(name)
                if "PORT_IN" in str(node.kind):
                    in_nodes.append(safe_name)
                elif "PORT_OUT" in str(node.kind):
                    out_nodes.append(safe_name)
                elif "REG" in str(node.kind):
                    reg_nodes.append(safe_name)
                else:
                    other_nodes.append(safe_name)

            if in_nodes:
                dot_lines.append(f"    {{ rank=source; {' '.join(in_nodes)}; }}")
            if out_nodes:
                dot_lines.append(f"    {{ rank=sink; {' '.join(out_nodes)}; }}")

            dot_lines.append("")

        # 边
        if self.config["show_edges"]:
            edges = list(self.graph.edges())
            filtered_edges = self._filter_edges(edges)

            for src, dst, edge in filtered_edges:
                ek = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)
                ek_short = ek.replace("EdgeKind.", "").replace('"', '\\"')

                # 获取安全节点名
                src_safe = node_name_map.get(src, src.split(".")[-1])
                dst_safe = node_name_map.get(dst, dst.split(".")[-1])

                # 边样式
                if ek in ("CLOCK", "PosEdge"):
                    style = "dashed"
                    color = self.EDGE_COLORS["CLOCK"]
                    penwidth = "1"
                elif ek in ("RESET", "NegEdge"):
                    style = "dashed"
                    color = self.EDGE_COLORS["RESET"]
                    penwidth = "1"
                elif self.config.get("cluster_modules") and self._is_cross_module(src, dst):
                    # 跨模块边用虚线
                    style = "dashed"
                    color = "#888888"
                    penwidth = "1"
                else:
                    style = "solid"
                    color = self.EDGE_COLORS.get(ek, "#666666")
                    penwidth = "2"

                # 边标签
                label_parts = []
                if self.config["edge_labels"]:
                    label_parts.append(ek_short)
                if self.config["edge_conditions"] and edge.condition:
                    cond = edge.condition.replace("!!", "").replace("&&", "&")
                    if len(cond) > 30:
                        cond = cond[:30] + "..."
                    label_parts.append(cond)

                if label_parts:
                    label_attr = f' xlabel="{chr(10).join(label_parts)}"'
                else:
                    label_attr = ""

                dot_lines.append(
                    f'    {src_safe} -> {dst_safe}[color="{color}" style={style} penwidth={penwidth}{label_attr}];'
                )

        dot_lines.append("}")

        dot_content = "\n".join(dot_lines)

        if output_path:
            with open(output_path, "w") as f:
                f.write(dot_content)

        return dot_content

    def render_mermaid(self, output_path: str = None) -> str:
        """渲染为 Mermaid 格式"""
        mmd_lines = [
            "flowchart " + self.config["layout"],
        ]

        # 统计信息
        total = len(list(self.graph.nodes()))
        mmd_lines.append(f"    %% Total nodes: {total}")

        # 节点
        for node_id in self.graph.nodes():
            # module_only 模式: 跳过子模块内部信号
            if self.config.get("module_only", False) and not self._is_top_module_signal(node_id):
                continue
            node = self.graph.get_node(node_id)
            if node is None:
                continue

            name = node_id.split(".")[-1]
            risk_score, risk_level = self._compute_risk(node_id)
            cover_status = self._get_cover_status(name)

            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name)

            # 图标
            if risk_level == "CRITICAL":
                icon = "🔴"
            elif risk_level == "HIGH":
                icon = "🟠"
            elif risk_level == "MEDIUM":
                icon = "🟡"
            else:
                icon = "🟢"

            # 覆盖标记
            if cover_status == "BOTH":
                cover_icon = " ✓🟡"
            elif cover_status == "SVA":
                cover_icon = " ✓"
            elif cover_status == "COV":
                cover_icon = " 🟡"
            elif risk_score >= self.config["min_risk_for_highlight"]:
                cover_icon = " 🚨"
            else:
                cover_icon = ""

            kind_short = str(node.kind).split(".")[-1][:3]

            mmd_lines.append(f'    N_{safe_name}["{icon} {name} ({kind_short}){cover_icon}"]')

        mmd_lines.append("")

        # 边
        if self.config["show_edges"]:
            edges = list(self.graph.edges())
            filtered_edges = self._filter_edges(edges)

            for src, dst, edge in filtered_edges:
                ek = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)
                ek_short = ek.replace("EdgeKind.", "")

                src_name = re.sub(r"[^a-zA-Z0-9_]", "_", src.split(".")[-1])
                dst_name = re.sub(r"[^a-zA-Z0-9_]", "_", dst.split(".")[-1])

                # 边样式
                if ek in ("CLOCK", "PosEdge"):
                    arrow = "-->"  # 虚线用 --
                elif ek in ("RESET", "NegEdge"):
                    arrow = "-->"
                else:
                    arrow = "-->"

                # 边标签
                label_parts = []
                if self.config["edge_labels"]:
                    label_parts.append(ek_short)
                if self.config["edge_conditions"] and edge.condition:
                    cond = edge.condition.replace("!!", "").replace("&&", "&")
                    if len(cond) > 25:
                        cond = cond[:25] + "..."
                    label_parts.append(cond)

                if label_parts:
                    label = "|".join(label_parts)
                    mmd_lines.append(f"    N_{src_name} {arrow}|{label}| N_{dst_name}")
                else:
                    mmd_lines.append(f"    N_{src_name} {arrow} N_{dst_name}")

        mmd_content = "\n".join(mmd_lines)

        if output_path:
            with open(output_path, "w") as f:
                f.write(mmd_content)

        return mmd_content

    def render_html(self, output_path: str) -> str:
        """渲染为交互式 HTML"""
        # 先获取 DOT 和 Mermaid
        self.render_dot(None)

        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Signal Graph Viewer</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { display: flex; gap: 20px; }
        .panel { flex: 1; border: 1px solid #ccc; padding: 15px; border-radius: 8px; }
        .panel h3 { margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        .controls { margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 5px; }
        .controls label { margin-right: 15px; }
        .mermaid { background: white; padding: 20px; border-radius: 5px; }
        .stats { display: flex; gap: 20px; margin-bottom: 15px; }
        .stat-box { background: #f0f8ff; padding: 10px 15px; border-radius: 5px; }
        .stat-box strong { font-size: 1.2em; color: #333; }
    </style>
</head>
<body>
    <h1>📊 Signal Graph Visualization</h1>

    <div class="controls">
        <label><input type="checkbox" id="showEdges" checked onchange="location.reload()"> Show Edges</label>
        <label><input type="checkbox" id="showLabels" onchange="location.reload()"> Show Edge Labels</label>
        <label>Layout: <select id="layout" onchange="location.reload()">
            <option value="TB">Top-Bottom</option>
            <option value="LR">Left-Right</option>
        </select></label>
    </div>

    <div class="stats">
        <div class="stat-box"><strong>{{TOTAL_NODES}}</strong><br>Total Nodes</div>
        <div class="stat-box"><strong>{{TOTAL_EDGES}}</strong><br>Total Edges</div>
        <div class="stat-box"><strong>{{HIGH_RISK}}</strong><br>High Risk</div>
    </div>

    <div class="container">
        <div class="panel" style="flex:2">
            <h3>🗺️ Graph View (Mermaid)</h3>
            <div class="mermaid">
{{MERMAID_CONTENT}}
            </div>
        </div>
        <div class="panel">
            <h3>📋 Legend</h3>
            <pre>
🔴 CRITICAL (≥40)
🟠 HIGH (≥25)
🟡 MEDIUM (≥15)
🟢 LOW (<15)

Edge Colors:
─ Black: Data/Driver
─ Blue: Clock
─ Red: Reset

Cover Status:
✓ = SVA covered
🟡 = Coverage covered
✓🟡 = Both
🚨 = Gap (high risk, no cover)
            </pre>
        </div>
    </div>

    <script>
        mermaid.initialize({
            startOnLoad: true,
            theme: 'base',
            flowchart: { useMaxWidth: true, htmlLabels: true }
        });
    </script>
</body>
</html>"""

        # 计算统计
        total_nodes = len(list(self.graph.nodes()))
        total_edges = len(list(self.graph.edges()))
        high_risk = sum(1 for n in self.graph.nodes() if self._compute_risk(n)[0] >= 25)

        # 模块聚类统计
        modules = self._extract_modules() if self.config.get("cluster_modules", False) else {}
        len(modules)
        sum(1 for n in self.graph.nodes() if self._compute_risk(n)[0] >= 40)

        # 渲染 Mermaid
        mermaid_content = self.render_mermaid(None)

        # 替换占位符
        html = html_template.replace("{{TOTAL_NODES}}", str(total_nodes))
        html = html.replace("{{TOTAL_EDGES}}", str(total_edges))
        html = html.replace("{{HIGH_RISK}}", str(high_risk))
        html = html.replace("{{MERMAID_CONTENT}}", mermaid_content)

        with open(output_path, "w") as f:
            f.write(html)

        return html


def create_gap_viewer(graph: object, sva_signals: set, cov_signals: set, gap_signals: list, output_prefix: str) -> object:
    """
    创建验证缺口可视化（带数据流边）

    Args:
        graph: SignalGraph
        sva_signals: SVA 覆盖信号集合
        cov_signals: Coverage 覆盖信号集合
        gap_signals: 高风险缺口信号列表
        output_prefix: 输出文件前缀
    """
    {g["name"] for g in gap_signals}

    viewer = SignalGraphViewer(graph, sva_signals, cov_signals)
    viewer.configure(
        layout="TB",
        show_edges=True,
        edge_filter={"exclude_clock", "exclude_reset"},
        max_edges=200,
        node_style={"risk_color": True, "cover_marker": True, "show_fan": True},
        highlight_gaps=True,
        min_risk_for_highlight=20.0,
    )

    # 渲染 DOT
    dot_path = f"{output_prefix}_gap.dot"
    viewer.render_dot(dot_path, "Verification Gap Analysis")

    # 渲染 HTML
    html_path = f"{output_prefix}_gap.html"
    viewer.render_html(html_path)

    return dot_path, html_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Signal Graph Visualization")
    parser.add_argument("-f", "--file", required=True, help="SystemVerilog file")
    parser.add_argument("--dot", help="Output DOT file")
    parser.add_argument("--mmd", help="Output Mermaid file")
    parser.add_argument("--html", help="Output HTML file")
    parser.add_argument("--no-edges", action="store_true", help="Hide edges")
    parser.add_argument("--layout", default="TB", choices=["TB", "LR"], help="Layout direction")
    parser.add_argument("--show-labels", action="store_true", help="Show edge labels")
    args = parser.parse_args()

    from trace.core.covergroup_extractor import CovergroupExtractor
    from trace.core.sva_extractor import SVAExtractor
    from trace.unified_tracer import UnifiedTracer

    with open(args.file) as f:
        source = f.read()

    tracer = UnifiedTracer(sources={args.file: source})
    graph = tracer.build_graph()
    sva = SVAExtractor({args.file: source}).extract()
    cov_list = CovergroupExtractor({args.file: source}).extract()

    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)

    cov_signals = set()
    for cg in cov_list:
        for cp in cg.coverpoints:
            cov_signals.add(cp.signal)

    viewer = SignalGraphViewer(graph, sva_signals, cov_signals)
    viewer.configure(
        layout=args.layout,
        show_edges=not args.no_edges,
        edge_labels=args.show_labels,
        node_style={"risk_color": True, "cover_marker": True, "show_fan": True},
    )

    if args.dot:
        viewer.render_dot(args.dot, f"Signal Graph: {args.file}")
        print(f"DOT saved: {args.dot}")

    if args.html:
        viewer.render_html(args.html)
        print(f"HTML saved: {args.html}")

    if args.mmd:
        viewer.render_mermaid(args.mmd)
        print(f"Mermaid saved: {args.mmd}")
