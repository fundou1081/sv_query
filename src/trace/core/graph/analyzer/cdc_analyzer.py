# ==============================================================================
# cdc_analyzer.py - CDC (Clock Domain Crossing) 检测
# ==============================================================================
"""
CDC 检测：识别跨时钟域的信号路径

算法：
1. 识别所有时钟信号和时钟域
2. 构建每个节点的时钟域归属
3. 找出跨时钟域的数据路径（源时钟域 ≠ 目标时钟域）
4. 识别 CDC 风险点（无同步器）

基本假设：
- 每个 module 有自己的时钟域
- 跨 module 连接时检查时钟域一致性
"""

import sys
from collections import defaultdict
from pathlib import Path

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from trace.core.graph.models import NodeKind


class CDCAnalyzer:
    """CDC 检测器"""

    def __init__(self, graph):
        self.graph = graph
        self._clock_signals = {}
        self._domain_nodes = {}  # domain -> set of nodes
        self._node_domains = {}  # node -> domain

    def identify_clock_domains(self) -> dict[str, set[str]]:
        """识别所有时钟域（按 module 分组）"""
        self._clock_signals = {}
        self._domain_nodes = {}

        clock_names = {"clk", "clock", "clk_i", "clk_p", "clk_n"}

        for node_id in self.graph.nodes():
            node = self.graph.get_node(node_id)
            if node is None:
                continue
            name = node_id.split(".")[-1].lower()
            if node.is_clock or name in clock_names:
                # 提取 module 名
                parts = node_id.rsplit(".", 1)
                module = parts[0] if len(parts) > 1 else "top"
                domain_key = f"{module}.{name}"
                if domain_key not in self._clock_signals:
                    self._clock_signals[domain_key] = []
                    self._domain_nodes[domain_key] = set()
                self._clock_signals[domain_key].append(node_id)
                self._domain_nodes[domain_key].add(node_id)

        return self._domain_nodes

    def assign_domains(self) -> dict[str, str]:
        """为每个节点分配时钟域（基于驱动关系传播）"""
        if not self._domain_nodes:
            self.identify_clock_domains()

        self._node_domains = {}

        # 初始化：时钟信号属于自己的域
        for domain, nodes in self._domain_nodes.items():
            for n in nodes:
                self._node_domains[n] = domain

        # BFS 传播：从时钟信号出发，通过所有边传播域
        visited = set(self._node_domains.keys())
        queue = list(self._node_domains.keys())

        while queue:
            cur = queue.pop(0)
            cur_domain = self._node_domains.get(cur)
            if cur_domain is None:
                continue

            for succ in self.graph.successors(cur):
                if succ in visited:
                    continue
                edge = self.graph.get_edge(cur, succ)
                if edge is None:
                    continue
                ek = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)
                # 跳过常量
                if succ.startswith("1'b") or succ in ("0", "1", "'0", "'1"):
                    continue

                # CLOCK/RESET 边：目标节点属于该时钟域
                if ek in ("CLOCK", "RESET", "PosEdge", "NegEdge"):
                    self._node_domains[succ] = cur_domain
                    visited.add(succ)
                    queue.append(succ)
                    continue

                # 其他边（DRIVER/CONNECTION 等）：同样传播域
                self._node_domains[succ] = cur_domain
                visited.add(succ)
                queue.append(succ)

        return self._node_domains

    def find_cdc_paths(self, max_depth: int = 10) -> list[dict]:
        """找出所有跨时钟域的路径"""
        if not self._node_domains:
            self.assign_domains()

        cdc_paths = []

        for src, dst in self.graph.edges():
            src_domain = self._node_domains.get(src)
            dst_domain = self._node_domains.get(dst)
            if src_domain is None or dst_domain is None:
                continue
            if src_domain == dst_domain:
                continue

            # 跨时钟域！
            edge = self.graph.get_edge(src, dst)
            ek = edge.kind.name if hasattr(edge.kind, "kind") else str(edge.kind)

            # 检查是否有同步器
            sync_info = self._analyze_sync_for_path(dst)

            src_node = self.graph.get_node(src)
            dst_node = self.graph.get_node(dst)

            path_info = {
                "source": src,
                "target": dst,
                "source_domain": src_domain,
                "target_domain": dst_domain,
                "source_domain_short": src_domain.split(".")[-1],
                "target_domain_short": dst_domain.split(".")[-1],
                "edge_kind": ek,
                "has_synchronizer": sync_info["has_sync"],
                "sync_type": sync_info["type"],
                "sync_flops": sync_info["flops"],
                "risk": "HIGH" if not sync_info["has_sync"] else "LOW",
            }
            cdc_paths.append(path_info)

        return cdc_paths

    def _analyze_sync_for_path(self, cdc_target: str) -> dict:
        """分析 CDC 目标的同步器类型

        Returns:
            {'has_sync': bool, 'type': str, 'flops': int, 'chain': list}
        """
        dst_domain = self._node_domains.get(cdc_target)
        if dst_domain is None:
            return {"has_sync": False, "type": "NONE", "flops": 0, "chain": []}

        # BFS 追溯目标时钟域内的寄存器链
        visited = {cdc_target}
        queue = [cdc_target]
        flop_count = 1  # CDC 目标本身
        sync_chain = [cdc_target]

        while queue:
            cur = queue.pop(0)

            for succ in self.graph.successors(cur):
                if succ in visited:
                    continue
                succ_domain = self._node_domains.get(succ)
                if succ_domain != dst_domain:
                    continue

                edge = self.graph.get_edge(cur, succ)
                ek = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)

                if ek in ("CLOCK", "RESET", "PosEdge", "NegEdge"):
                    continue

                visited.add(succ)

                # 只数寄存器节点
                node = self.graph.get_node(succ)
                if node and node.kind == NodeKind.REG:
                    flop_count += 1
                    sync_chain.append(succ)
                    queue.append(succ)
                else:
                    # 遇到非寄存器，停止追溯
                    break

        # 判断同步器类型
        if flop_count == 1:
            return {"has_sync": False, "type": "NONE", "flops": 1, "chain": sync_chain}
        elif flop_count == 2:
            return {"has_sync": True, "type": "2-FLOP", "flops": 2, "chain": sync_chain}
        elif flop_count >= 3:
            return {"has_sync": True, "type": f"{flop_count}-FLOP", "flops": flop_count, "chain": sync_chain}
        else:
            return {"has_sync": False, "type": "UNKNOWN", "flops": flop_count, "chain": sync_chain}

    def _check_sync_path(self, src: str, dst: str) -> bool:
        """检查 src → dst 之间是否有同步器（2-flop 结构）"""
        sync_info = self._analyze_sync_for_path(dst)
        return sync_info["has_sync"]

    def cdc_report(self) -> dict:
        """生成 CDC 量化报告"""
        paths = self.find_cdc_paths()

        high_risk = [p for p in paths if p["risk"] == "HIGH"]
        low_risk = [p for p in paths if p["risk"] == "LOW"]

        domains = list(self._domain_nodes.keys())

        # 按时钟域对统计
        domain_pair_stats = defaultdict(lambda: {"count": 0, "high_risk": 0, "paths": []})
        for p in paths:
            key = (p["source_domain_short"], p["target_domain_short"])
            domain_pair_stats[key]["count"] += 1
            domain_pair_stats[key]["paths"].append(p)
            if p["risk"] == "HIGH":
                domain_pair_stats[key]["high_risk"] += 1

        # 高风险 CDC 排行
        high_risk_paths = sorted(high_risk, key=lambda x: x["target"])

        # 同步器类型统计
        sync_type_stats = defaultdict(int)
        for p in paths:
            sync_type_stats[p["sync_type"]] += 1

        return {
            "domains": domains,
            "domain_count": len(domains),
            "total_cdc": len(paths),
            "high_risk": len(high_risk),
            "low_risk": len(low_risk),
            "paths": paths,
            "domain_pairs": dict(domain_pair_stats),
            "high_risk_paths": high_risk_paths,
            "sync_type_stats": dict(sync_type_stats),
        }


def run_cli():
    import argparse

    parser = argparse.ArgumentParser(description="CDC 检测")
    parser.add_argument("-f", "--file", required=True, help="SystemVerilog 文件")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--high-only", action="store_true", help="只显示高风险")
    args = parser.parse_args()

    from trace.unified_tracer import UnifiedTracer

    with open(args.file) as f:
        source = f.read()

    tracer = UnifiedTracer(sources={args.file: source})
    graph = tracer.build_graph()
    cdc = CDCAnalyzer(graph)
    cdc.identify_clock_domains()
    cdc.assign_domains()
    report = cdc.cdc_report()

    if args.json:
        import json

        print(json.dumps(report, indent=2, default=str))
        return

    print(f"{'=' * 70}")
    print(f"CDC 检测报告: {args.file}")
    print(f"{'=' * 70}")

    print(f"\n  时钟域 ({report['domain_count']}):")
    for d in report["domains"]:
        print(f"    - {d}")

    print("\n  CDC 路径统计:")
    print(f"    总计: {report['total_cdc']}")
    print(f"    🔴 高风险: {report['high_risk']}")
    print(f"    🟢 低风险: {report['low_risk']}")

    if report["sync_type_stats"]:
        print("\n  同步器类型分布:")
        for stype, count in sorted(report["sync_type_stats"].items()):
            print(f"    {stype}: {count} 条")

    if report["domain_pairs"]:
        print("\n  跨时钟域路径统计:")
        for (src_clk, dst_clk), stats in sorted(report["domain_pairs"].items()):
            high = stats["high_risk"]
            icon = "🔴" if high > 0 else "🟢"
            print(f"    {src_clk} → {dst_clk}: {stats['count']} 条 {icon}")

    paths = report["paths"]
    if args.high_only:
        paths = [p for p in paths if p["risk"] == "HIGH"]

    if paths:
        print("\n  CDC 路径详情:")
        for i, p in enumerate(paths, 1):
            risk_icon = "🔴" if p["risk"] == "HIGH" else "🟢"
            sync_info = f"{p['sync_type']}" if p["sync_type"] != "NONE" else "无同步器"
            print(f"\n  [{i}] {risk_icon} {p['source']} → {p['target']}")
            print(f"      域: {p['source_domain_short']} → {p['target_domain_short']}")
            print(f"      同步器: {sync_info}")
    else:
        print("\n  未发现 CDC 路径")


if __name__ == "__main__":
    run_cli()
