# ==============================================================================
# timing_analyzer.py - 关键路径分析（SCC + DAG 最长路径）
# ==============================================================================
"""
关键路径分析：
1. 构建寄存器级图（排除时钟/复位边）
2. 对图进行拓扑排序（SCC 缩点）
3. 在 DAG 上找最长路径
4. 输出关键路径（按深度排序）
5. 估算时钟周期数和时序风险

增强功能 (2026-05-30):
- cycle_estimate: 预估时钟周期数（基于寄存器深度）
- combo_delay_estimate: 组合逻辑延迟估计
- risk_level: 超长路径风险
- violation_risk: 时序违例风险
"""

import sys
from pathlib import Path

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent  # src/trace/core/graph/analyzer/

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from trace.core.graph.models import NodeKind


class TimingAnalyzer:
    """时序关键路径分析器"""

    def __init__(self, graph):
        self.graph = graph
        self._reg_graph = None
        self._reg_depth = {}
        self._scc = None

    def _build_reg_graph(self):
        """构建寄存器级图（排除时钟/复位边）"""
        import networkx as nx

        G = nx.DiGraph()

        clock_names = {"clk", "clock", "clk_i", "clk_p", "clk_n"}
        reset_names = {"rst", "rst_n", "reset", "resetn", "reset_n"}

        # 所有寄存器节点
        reg_nodes = set()
        for nid in self.graph.nodes():
            node = self.graph.get_node(nid)
            if node and node.kind == NodeKind.REG:
                reg_nodes.add(nid)

        # 主输入（不含时钟/复位）
        primary_inputs = set()
        for nid in self.graph.nodes():
            node = self.graph.get_node(nid)
            if node and node.kind == NodeKind.PORT_IN:
                name = nid.split(".")[-1].lower()
                if name not in clock_names and name not in reset_names:
                    primary_inputs.add(nid)

        # 添加所有节点（即使不是 REG/PORT_IN 也添加，用于路径追踪）
        for nid in self.graph.nodes():
            G.add_node(nid)

        # 边：排除时钟/复位边，重建数据流图
        for src, dst in self.graph.edges():
            edge = self.graph.get_edge(src, dst)
            ek = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)
            # 排除时钟/复位边
            if ek in ("CLOCK", "RESET", "PosEdge", "NegEdge"):
                continue
            # 只保留涉及 REG 的路径（简化）
            if src in reg_nodes or dst in reg_nodes or src in primary_inputs:
                if not G.has_edge(src, dst):
                    G.add_edge(src, dst)

        self._reg_graph = G
        return G

    @property
    def reg_graph(self) -> object:
        if self._reg_graph is None:
            self._build_reg_graph()
        return self._reg_graph

    def _find_scc(self):
        """找强连通分量（SCC）"""
        import networkx as nx

        if self._scc is not None:
            return self._scc
        G = self.reg_graph
        self._scc = list(nx.strongly_connected_components(G))
        return self._scc

    def _condensation_graph(self):
        """构建 SCC 缩点后的 DAG"""
        import networkx as nx

        G = self.reg_graph
        scc_list = self._find_scc()
        scc_map = {}
        for i, comp in enumerate(scc_list):
            for node in comp:
                scc_map[node] = i

        dag = nx.DiGraph()
        for src, dst in G.edges():
            s_src, s_dst = scc_map[src], scc_map[dst]
            if s_src != s_dst:
                dag.add_edge(s_src, s_dst)

        return dag, scc_map

    def estimate_reg_depth(self, target_id: str) -> int:
        """估计从主输入到目标节点的寄存器深度（路径上最大寄存器数）"""

        G = self.reg_graph
        if target_id not in G:
            return 0

        clock_names = {"clk", "clock", "clk_i"}
        reset_names = {"rst", "rst_n", "reset", "resetn"}
        primary_inputs = set()
        for nid in self.graph.nodes():
            node = self.graph.get_node(nid)
            if node and node.kind == NodeKind.PORT_IN:
                name = nid.split(".")[-1].lower()
                if name not in clock_names and name not in reset_names:
                    primary_inputs.add(nid)

        # BFS from primary inputs
        visited = {}
        queue = [(pi, 0) for pi in primary_inputs if pi in G]
        for pi, d in queue:
            visited[pi] = d

        max_depth = 0
        found = False

        while queue:
            cur, depth = queue.pop(0)
            if cur == target_id:
                max_depth = max(max_depth, depth)
                found = True
                continue
            if cur not in G:
                continue
            for succ in G.successors(cur):
                if succ in visited:
                    continue
                node = self.graph.get_node(succ)
                if node is None:
                    continue
                is_reg = node.kind == NodeKind.REG
                nd = depth + (1 if is_reg else 0)
                visited[succ] = nd
                queue.append((succ, nd))

        return max_depth if found else 0

    def longest_path_in_dag(self, start_nodes: list[int], end_nodes: list[int]) -> tuple[int, list[str]]:
        """在 DAG 上找最长路径"""
        import networkx as nx

        G = self.reg_graph
        scc_list = self._find_scc()

        if len(scc_list) <= 1:
            # 无 SCC，直接在原图上找最长路径
            dag = G
            node_list = list(start_nodes)
        else:
            # SCC 缩点
            dag, scc_map = self._condensation_graph()
            node_list = list(set(scc_map.get(n, -1) for n in start_nodes if n in scc_map))

        if not node_list or not dag.nodes():
            return 0, []

        # 按拓扑序计算最长路径
        try:
            topo_order = list(nx.topological_sort(dag))
        except nx.NetworkXError:
            return 0, []

        # dist[i] = (length, path)
        dist = {n: (0, []) for n in dag.nodes()}

        for node in topo_order:
            length, path = dist[node]
            for succ in dag.successors(node):
                new_len = length + 1
                if new_len > dist[succ][0]:
                    dist[succ] = (new_len, path + [node])

        # 找最长路径的终点
        max_len, max_path = 0, []
        for n in end_nodes:
            if n in dist:
                length_val, prev = dist[n]
                if length_val > max_len:
                    max_len = length_val
                    max_path = prev + [n]

        return max_len, [scc_list[n][0] for n in max_path] if len(scc_list) > 1 else max_path

    def get_critical_paths(self, max_paths: int = 5) -> list[dict]:
        """获取最关键的多条路径"""

        G = self.reg_graph
        if not G.nodes():
            return []

        clock_names = {"clk", "clock", "clk_i"}
        reset_names = {"rst", "rst_n", "reset", "resetn"}
        primary_inputs = set()
        reg_nodes = set()

        for nid in self.graph.nodes():
            node = self.graph.get_node(nid)
            if node:
                name = nid.split(".")[-1].lower()
                if node.kind == NodeKind.PORT_IN and name not in clock_names and name not in reset_names:
                    primary_inputs.add(nid)
                if node.kind == NodeKind.REG:
                    reg_nodes.add(nid)

        if not primary_inputs or not reg_nodes:
            return []

        # 计算每个节点的深度
        self._reg_depth = {}
        for nid in reg_nodes:
            self._reg_depth[nid] = self.estimate_reg_depth(nid)

        # 按深度排序的寄存器
        sorted_regs = sorted(reg_nodes, key=lambda x: self._reg_depth.get(x, 0), reverse=True)

        paths = []
        for target in sorted_regs[: max_paths * 2]:
            d = self._reg_depth.get(target, 0)
            if d == 0:
                continue
            path = self._reconstruct_path(primary_inputs, target, reg_nodes)
            if path and len(path) >= 2:
                score = sum(self._reg_depth.get(n, 0) for n in path)

                # 增强：计算组合逻辑延迟和时序风险
                reg_chain = [n for n in path if n in reg_nodes]
                combo_nodes = []

                # 计算寄存器间的组合逻辑节点
                for j in range(len(path) - 1):
                    src, dst = path[j], path[j + 1]
                    if src not in reg_nodes and dst not in reg_nodes:
                        node = self.graph.get_node(src)
                        if node and node.kind not in (NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.SIGNAL):
                            combo_nodes.append(src.split(".")[-1])

                # cycle_estimate: 寄存器数 = 预估周期数
                cycle_estimate = len(reg_chain)

                # combo_delay_estimate: 组合逻辑延迟（简化计数）
                combo_delay = len(combo_nodes)

                # risk_level: 时序风险
                if cycle_estimate >= 5:
                    risk_level = "CRITICAL"
                elif cycle_estimate >= 3:
                    risk_level = "HIGH"
                elif cycle_estimate >= 2:
                    risk_level = "MEDIUM"
                else:
                    risk_level = "LOW"

                # violation_risk: 违例风险（组合逻辑过多或路径过长）
                if combo_delay > cycle_estimate or cycle_estimate >= 5:
                    violation_risk = "HIGH"
                elif combo_delay > 0 and cycle_estimate >= 3:
                    violation_risk = "MEDIUM"
                else:
                    violation_risk = "LOW"

                paths.append(
                    {
                        "depth": d,
                        "score": score,
                        "path": path,
                        "registers": reg_chain,
                        "cycle_estimate": cycle_estimate,
                        "combo_delay_estimate": combo_delay,
                        "combo_nodes": combo_nodes,
                        "risk_level": risk_level,
                        "violation_risk": violation_risk,
                    }
                )
            if len(paths) >= max_paths:
                break

        # 按 score 排序
        paths.sort(key=lambda x: x["score"], reverse=True)
        return paths[:max_paths]

    def _reconstruct_path(self, start_set: set[str], end: str, reg_nodes: set[str]) -> list[str]:
        """重建从 start_set 到 end 的路径"""

        G = self.reg_graph
        if end not in G:
            return []

        # BFS from any start to end
        visited = {s: None for s in start_set}
        queue = list(start_set)

        while queue:
            cur = queue.pop(0)
            if cur == end:
                break
            for succ in G.successors(cur):
                if succ not in visited:
                    visited[succ] = cur
                    queue.append(succ)

        if end not in visited or visited[end] is None:
            # 尝试从 primary_inputs
            pass

        # 回溯路径
        path = []
        cur = end
        while cur is not None and cur in visited:
            path.append(cur)
            cur = visited[cur]
            if cur is None:
                break

        path.reverse()
        return path if path and (path[0] in start_set or path[0] in reg_nodes) else []

    def timing_risk(self, node_id: str) -> str:
        """评估节点的时序风险等级"""
        depth = self.estimate_reg_depth(node_id)
        node = self.graph.get_node(node_id)
        is_reg = node and node.kind == NodeKind.REG

        score = depth * 10 + (15 if is_reg else 0)

        if score >= 60:
            return "CRITICAL"
        elif score >= 40:
            return "HIGH"
        elif score >= 20:
            return "MEDIUM"
        else:
            return "LOW"

    def timing_report(self) -> dict:
        """生成时序分析量化报告"""
        paths = self.get_critical_paths(max_paths=10)

        # 统计
        total_paths = len(paths)
        critical_paths = [p for p in paths if p.get("risk_level") == "CRITICAL"]
        high_risk_paths = [p for p in paths if p.get("risk_level") == "HIGH"]
        medium_risk_paths = [p for p in paths if p.get("risk_level") == "MEDIUM"]
        low_risk_paths = [p for p in paths if p.get("risk_level") == "LOW"]

        # 最大周期数
        max_cycles = max(p.get("cycle_estimate", 0) for p in paths) if paths else 0

        # 平均周期数
        avg_cycles = sum(p.get("cycle_estimate", 0) for p in paths) / total_paths if total_paths > 0 else 0

        # 风险路径排行
        risk_ranking = sorted(paths, key=lambda x: x.get("violation_risk", "LOW") == "HIGH", reverse=True)[:5]

        return {
            "total_paths": total_paths,
            "max_cycles": max_cycles,
            "avg_cycles": round(avg_cycles, 1),
            "risk_breakdown": {
                "CRITICAL": len(critical_paths),
                "HIGH": len(high_risk_paths),
                "MEDIUM": len(medium_risk_paths),
                "LOW": len(low_risk_paths),
            },
            "paths": paths,
            "risk_ranking": risk_ranking,
        }


# === CLI 接口 ===
def run_cli():
    import argparse

    parser = argparse.ArgumentParser(description="关键路径分析")
    parser.add_argument("-f", "--file", required=True, help="SystemVerilog 文件")
    parser.add_argument("--max-paths", type=int, default=5, help="最大路径数")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    from trace.unified_tracer import UnifiedTracer

    with open(args.file) as f:
        source = f.read()

    tracer = UnifiedTracer(sources={args.file: source})
    graph = tracer.build_graph()
    analyzer = TimingAnalyzer(graph)

    paths = analyzer.get_critical_paths(max_paths=args.max_paths)

    if args.json:
        import json

        result = {
            "file": args.file,
            "paths": [
                {
                    "depth": p["depth"],
                    "score": p["score"],
                    "path": p["path"],
                    "registers": p["registers"],
                    "cycle_estimate": p.get("cycle_estimate", 0),
                    "combo_delay_estimate": p.get("combo_delay_estimate", 0),
                    "risk_level": p.get("risk_level", "LOW"),
                    "violation_risk": p.get("violation_risk", "LOW"),
                }
                for p in paths
            ],
            "node_count": len(graph.nodes()),
            "reg_count": sum(1 for n in graph.nodes() if graph.get_node(n) and graph.get_node(n).kind == NodeKind.REG),
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"{'=' * 70}")
        print(f"关键路径分析: {args.file}")
        print(f"{'=' * 70}")

        for i, p in enumerate(paths, 1):
            risk = p.get("risk_level", "LOW")
            risk_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk, "")
            cycles = p.get("cycle_estimate", p["depth"])
            combo = p.get("combo_delay_estimate", 0)

            print(f"\n路径 {i} {risk_icon}")
            regs = " -> ".join([n.split(".")[-1] for n in p["registers"]])
            print(f"  寄存器链: {regs}")
            print(f"  预估周期: {cycles} cycles")
            print(f"  组合逻辑延迟: {combo} 级")
            print(f"  风险等级: {risk}")
            print(f"  违例风险: {p.get('violation_risk', 'LOW')}")


if __name__ == "__main__":
    run_cli()
