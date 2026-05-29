#==============================================================================
# cdc_analyzer.py - CDC (Clock Domain Crossing) 检测
#==============================================================================
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
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

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

    def identify_clock_domains(self) -> Dict[str, Set[str]]:
        """识别所有时钟域（按 module 分组）"""
        self._clock_signals = {}
        self._domain_nodes = {}

        clock_names = {'clk', 'clock', 'clk_i', 'clk_p', 'clk_n'}

        for node_id in self.graph.nodes():
            node = self.graph.get_node(node_id)
            if node is None:
                continue
            name = node_id.split('.')[-1].lower()
            if node.is_clock or name in clock_names:
                # 提取 module 名
                parts = node_id.rsplit('.', 1)
                module = parts[0] if len(parts) > 1 else 'top'
                domain_key = f"{module}.{name}"
                if domain_key not in self._clock_signals:
                    self._clock_signals[domain_key] = []
                    self._domain_nodes[domain_key] = set()
                self._clock_signals[domain_key].append(node_id)
                self._domain_nodes[domain_key].add(node_id)

        return self._domain_nodes

    def assign_domains(self) -> Dict[str, str]:
        """为每个节点分配时钟域（基于驱动关系传播）"""
        if not self._domain_nodes:
            self.identify_clock_domains()

        self._node_domains = {}
        clock_names = {'clk', 'clock', 'clk_i'}

        # 初始化：时钟信号属于自己的域
        for domain, nodes in self._domain_nodes.items():
            for n in nodes:
                self._node_domains[n] = domain

        # BFS 传播：从时钟信号出发，通过数据边传播域
        visited = set(self._node_domains.keys())
        queue = list(self._node_domains.keys())

        while queue:
            cur = queue.pop(0)
            cur_domain = self._node_domains.get(cur)
            if cur_domain is None:
                continue

            # 从 cur 驱动哪些节点（通过非时钟/非复位边）
            for succ in self.graph.successors(cur):
                if succ in visited:
                    continue
                edge = self.graph.get_edge(cur, succ)
                if edge is None:
                    continue
                ek = edge.kind.name if hasattr(edge.kind, 'name') else str(edge.kind)
                # 跳过时钟/复位边
                if ek in ('CLOCK', 'RESET', 'PosEdge', 'NegEdge'):
                    continue
                # 跳过常量
                if succ.startswith("1'b") or succ in ('0', '1', "'0", "'1"):
                    continue

                self._node_domains[succ] = cur_domain
                visited.add(succ)
                queue.append(succ)

        return self._node_domains

    def find_cdc_paths(self, max_depth: int = 10) -> List[Dict]:
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
            ek = edge.kind.name if hasattr(edge.kind, 'kind') else str(edge.kind)

            # 检查是否有同步器
            has_sync = self._check_sync_path(src, dst)

            src_node = self.graph.get_node(src)
            dst_node = self.graph.get_node(dst)

            path_info = {
                'source': src,
                'target': dst,
                'source_domain': src_domain,
                'target_domain': dst_domain,
                'edge_kind': ek,
                'has_synchronizer': has_sync,
                'risk': 'HIGH' if not has_sync else 'LOW',
            }
            cdc_paths.append(path_info)

        return cdc_paths

    def _check_sync_path(self, src: str, dst: str) -> bool:
        """检查 src → dst 之间是否有同步器（2-flop 结构）"""
        # 简化：检查 dst 是否被同一域的某个信号（可能作为同步器）驱动
        # 更准确的做法是识别 sync module 或特定命名模式
        src_name = src.split('.')[-1].lower()
        dst_name = dst.split('.')[-1].lower()
        # 带 sync 关键字的信号
        if 'sync' in dst_name or 'synced' in dst_name:
            return True
        # 两级寄存器结构通常表示同步器
        return False

    def cdc_report(self) -> Dict:
        """生成 CDC 报告"""
        paths = self.find_cdc_paths()

        high_risk = [p for p in paths if p['risk'] == 'HIGH']
        low_risk = [p for p in paths if p['risk'] == 'LOW']

        domains = list(self._domain_nodes.keys())

        return {
            'domains': domains,
            'total_cdc': len(paths),
            'high_risk': len(high_risk),
            'low_risk': len(low_risk),
            'paths': paths,
        }


def run_cli():
    import argparse
    parser = argparse.ArgumentParser(description='CDC 检测')
    parser.add_argument('-f', '--file', required=True, help='SystemVerilog 文件')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    parser.add_argument('--high-only', action='store_true', help='只显示高风险')
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
        print(json.dumps(report, indent=2))
    else:
        print(f"{'='*70}")
        print(f"CDC 检测报告: {args.file}")
        print(f"{'='*70}")

        print(f"\n  时钟域 ({len(report['domains'])}):")
        for d in report['domains']:
            print(f"    - {d}")

        print(f"\n  CDC 路径统计:")
        print(f"    总计: {report['total_cdc']}")
        print(f"    🔴 高风险: {report['high_risk']}")
        print(f"    🟢 低风险: {report['low_risk']}")

        paths = report['paths']
        if args.high_only:
            paths = [p for p in paths if p['risk'] == 'HIGH']

        if paths:
            print(f"\n  CDC 路径详情:")
            for i, p in enumerate(paths, 1):
                risk_icon = '🔴' if p['risk'] == 'HIGH' else '🟢'
                sync_icon = '✓' if p['has_synchronizer'] else '✗'
                print(f"\n  [{i}] {risk_icon} {p['source']} → {p['target']}")
                print(f"      域: {p['source_domain']} → {p['target_domain']}")
                print(f"      边: {p['edge_kind']} | 同步器: {sync_icon}")


if __name__ == "__main__":
    run_cli()