# test_timing_analyzer.py - 时序分析器测试
# [铁律13] 金标准测试
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.sva_extractor import SVAExtractor
from trace.core.graph.models import NodeKind


def _build(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    graph = tracer.build_graph()
    sva = SVAExtractor({'test.sv': source}).extract()
    return graph, sva, tracer


class TestTimingAnalyzer(unittest.TestCase):
    """时序分析器核心功能"""

    def test_simple_pipeline_depth(self):
        """[金标准] 简单流水线深度

        a → reg1 → reg2 → reg3 → out
        深度: a→reg1=1, a→reg2=2, a→reg3=3
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] out);
    logic [7:0] reg1, reg2, reg3;
    always_ff @(posedge clk) reg1 <= a;
    always_ff @(posedge clk) reg2 <= reg1;
    always_ff @(posedge clk) reg3 <= reg2;
    always_ff @(posedge clk) out <= reg3;
endmodule'''
        graph, sva, _ = _build(source)

        # 计算 reg3 的时序深度
        depth = _timing_depth(graph, 'top.reg3')
        self.assertEqual(depth, 3)

    def test_parallel_paths_same_depth(self):
        """[金标准] 并行路径同深度

        a → reg1 → reg2 → out
        b → reg_b → out
        reg2 深度=2, reg_b 深度=1
        """
        source = '''module top(input clk, input [7:0] a, b, output logic [7:0] out);
    logic [7:0] reg1, reg2, reg_b;
    always_ff @(posedge clk) reg1 <= a;
    always_ff @(posedge clk) reg2 <= reg1;
    always_ff @(posedge clk) reg_b <= b;
    always_ff @(posedge clk) out <= reg2 + reg_b;
endmodule'''
        graph, sva, _ = _build(source)

        depth_reg2 = _timing_depth(graph, 'top.reg2')
        depth_reg_b = _timing_depth(graph, 'top.reg_b')
        self.assertEqual(depth_reg2, 2)
        self.assertEqual(depth_reg_b, 1)

    def test_combinational_depth_limit(self):
        """[金标准] 组合逻辑深度限制

        a → comb1 → comb2 → comb3 → comb4 → reg
        组合深度 4 > 阈值 3，应被截断
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] out);
    logic [7:0] c1, c2, c3, c4;
    assign c1 = a + 1;
    assign c2 = c1 + 1;
    assign c3 = c2 + 1;
    assign c4 = c3 + 1;
    always_ff @(posedge clk) out <= c4;
endmodule'''
        graph, sva, _ = _build(source)

        # 组合深度阈值=3，c4 超过阈值，depth 应为 1（只有最后一级寄存器）
        depth = _timing_depth(graph, 'top.out', max_comb_depth=3)
        self.assertEqual(depth, 1)

    def test_combinational_depth_within_limit(self):
        """[金标准] 组合逻辑深度在阈值内

        a → comb1 → comb2 → reg
        组合深度 2 ≤ 阈值 3，正常计算
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] out);
    logic [7:0] c1, c2;
    assign c1 = a + 1;
    assign c2 = c1 + 1;
    always_ff @(posedge clk) out <= c2;
endmodule'''
        graph, sva, _ = _build(source)

        depth = _timing_depth(graph, 'top.out', max_comb_depth=3)
        self.assertEqual(depth, 1)

    def test_cycle_scc_collapse(self):
        """[金标准] 组合环 SCC 缩点

        assign a = b;
        assign b = a;  // 组合环

        验证不应死循环
        """
        source = '''module top(input clk, input [7:0] d, output logic [7:0] out);
    logic [7:0] a, b;
    assign a = b + d;
    assign b = a;
    always_ff @(posedge clk) out <= a;
endmodule'''
        graph, sva, _ = _build(source)

        # 不应死循环，depth 应该能计算出来
        depth = _timing_depth(graph, 'top.out')
        self.assertIsInstance(depth, int)

    def test_async_reset_excluded(self):
        """[金标准] 异步复位不计入数据路径

        rst_n → reg (异步)
        d → reg (同步)

        depth 应只算同步路径
        """
        source = '''module top(input clk, rst_n, input [7:0] d, output logic [7:0] out);
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) out <= 0;
        else out <= d;
endmodule'''
        graph, sva, _ = _build(source)

        depth = _timing_depth(graph, 'top.out')
        self.assertEqual(depth, 1)


class TestTimingSVAMatch(unittest.TestCase):
    """时序深度 vs SVA 比对"""

    def test_sva_next_cycle_match(self):
        """[金标准] SVA |=> 对应 1 级寄存器

        RTL: d → reg (1 级)
        SVA: d |=> reg  (下一周期)
        """
        source = '''module top(input clk, input [7:0] d, output logic [7:0] q);
    always_ff @(posedge clk) q <= d;
    property p1;
        @(posedge clk) d |=> q;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build(source)

        depth = _timing_depth(graph, 'top.q')
        self.assertEqual(depth, 1)

        prop = list(sva.properties.values())[0]
        self.assertIn('|=>', prop.operators)

    def test_sva_same_cycle_assert(self):
        """[金标准] SVA |-> 对应 0 级寄存器（同周期）

        RTL: assign out = a; (组合逻辑)
        SVA: a |-> out
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] out);
    assign out = a;
    property p1;
        @(posedge clk) a |-> out;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build(source)

        depth = _timing_depth(graph, 'top.out')
        self.assertEqual(depth, 0)

        prop = list(sva.properties.values())[0]
        self.assertIn('|->', prop.operators)

    def test_sva_two_cycle_delay(self):
        """[金标准] SVA ##2 对应 2 级寄存器

        RTL: d → reg1 → reg2 (2 级)
        SVA: d |-> ##1 reg1 ##1 reg2  或  d ##2 reg2
        """
        source = '''module top(input clk, input [7:0] d, output logic [7:0] q);
    logic [7:0] reg1;
    always_ff @(posedge clk) reg1 <= d;
    always_ff @(posedge clk) q <= reg1;
    property p1;
        @(posedge clk) d |=> ##1 q;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build(source)

        depth = _timing_depth(graph, 'top.q')
        self.assertEqual(depth, 2)


def _timing_depth(graph, target_id, max_comb_depth=3):
    """计算从主输入到目标寄存器的时序深度（经过几级寄存器）

    算法：
    1. 构建寄存器级图（跳过时钟/复位边）
    2. BFS 找从 PORT_IN 到 target 的路径
    3. 组合逻辑深度 ≤ max_comb_depth 时算同一级
    4. 时序深度 = 路径上的寄存器级数
    """
    target_node = graph.get_node(target_id)
    if target_node is None:
        return -1
    
    # 收集所有寄存器节点
    reg_nodes = set()
    for nid in graph.nodes():
        n = graph.get_node(nid)
        if n and n.kind == NodeKind.REG:
            reg_nodes.add(nid)
    
    # 收集 PORT_IN（排除时钟/复位）
    primary_inputs = set()
    for nid in graph.nodes():
        n = graph.get_node(nid)
        if n and n.kind == NodeKind.PORT_IN:
            if not n.is_clock and not n.is_reset:
                name = nid.split('.')[-1]
                if name not in ('clk', 'clk_i', 'rst_n', 'rst'):
                    primary_inputs.add(nid)
    
    # 如果目标就是主输入，深度=0
    if target_id in primary_inputs:
        return 0
    
    # BFS：从主输入出发，找到达 target 的最短路径
    # 路径上的寄存器级数 = 时序深度
    from collections import deque
    
    visited = set()
    queue = deque()
    
    # 初始：主输入节点，深度=0
    for pi in primary_inputs:
        queue.append((pi, 0, set()))  # (node_id, depth, visited_regs)
        visited.add(pi)
    
    max_depth = 0
    found = False
    
    while queue:
        current, depth, path_regs = queue.popleft()
        
        if current == target_id:
            max_depth = max(max_depth, depth)
            found = True
            continue
        
        # 遍历后继
        for successor in graph.successors(current):
            if successor in visited:
                continue
            
            succ_node = graph.get_node(successor)
            if succ_node is None:
                continue
            
            new_depth = depth
            new_regs = path_regs.copy()
            
            # 跳过时钟/复位边
            if succ_node.is_clock or succ_node.is_reset:
                continue
            
            # 寄存器：深度+1
            if successor in reg_nodes:
                new_depth += 1
                new_regs.add(successor)
            
            # 组合逻辑：检查深度限制
            else:
                # 计算当前组合逻辑深度
                comb_depth = _comb_depth_from_last_reg(graph, current, reg_nodes)
                if comb_depth > max_comb_depth:
                    continue  # 超过阈值，截断
            
            visited.add(successor)
            queue.append((successor, new_depth, new_regs))
    
    return max_depth if found else 0


def _comb_depth_from_last_reg(graph, node_id, reg_nodes):
    """计算从最近寄存器到当前节点的组合逻辑深度"""
    # 简化：用 BFS 往回找最近的寄存器
    from collections import deque
    
    visited = set()
    queue = deque([(node_id, 0)])
    visited.add(node_id)
    
    while queue:
        current, dist = queue.popleft()
        
        if current in reg_nodes:
            return dist
        
        for pred in graph.predecessors(current):
            if pred not in visited:
                visited.add(pred)
                queue.append((pred, dist + 1))
    
    return 0


if __name__ == '__main__':
    unittest.main()
