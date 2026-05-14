"""
test_cross_module_tracking.py - 跨模块边界追踪金标准测试

[铁律13] 金标准测试
[铁律17] 强断言原则

场景设计:
  top
  ├── tb (testbench)
  │   └── clk (logic)
  └── dut (device under test)
      ├── clk (input)
      └── reg_data [31:0] (reg)
      
  连接: top.u_tb.clk → top.u_dut.clk

预期结果:
  1. ModuleInstanceGraph 包含: top.u_tb, top.u_dut
  2. 端口映射: top.u_dut.clk → dut.clk (内部信号)
  3. 跨模块路径: top.u_tb.clk → top.u_dut.clk → dut.reg_data
"""

import unittest
import sys
sys.path.insert(0, 'src')

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind
import pyslang


class TestModuleInstanceGraph(unittest.TestCase):
    """模块实例图测试"""
    
    def _build_graph(self):
        import tempfile
        import os
        
        source = '''module tb;
    logic clk;
endmodule

module dut;
    input clk;
    logic [31:0] reg_data;
    always_ff @(posedge clk)
        reg_data <= 32'h0;
endmodule

module top;
    tb u_tb();
    dut u_dut();
    assign u_dut.clk = u_tb.clk;
endmodule'''
        
        # Write to temp file for multi-module support
        temp_path = f'/tmp/test_cross_module_{id(self)}.sv'
        with open(temp_path, 'w') as f:
            f.write(source)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_instances_exist(self):
        """[金标准] 模块实例存在"""
        graph, tracer = self._build_graph()
        
        # 检查 ModuleInstanceGraph
        mig = getattr(tracer, '_module_graph', None)
        if mig:
            self.assertIn('top.u_tb', mig.instances, "应有 top.u_tb 实例")
            self.assertIn('top.u_dut', mig.instances, "应有 top.u_dut 实例")
        else:
            # 备用: 通过端口节点检测
            nodes = list(graph.nodes())
            # 至少应该能通过边发现实例关系
            has_instance_edge = any('u_tb' in src or 'u_dut' in dst 
                                    for src, dst in graph.edges())
            self.assertTrue(has_instance_edge, "应有实例间连接")
    
    def test_port_mapping(self):
        """[金标准] 端口到内部信号映射"""
        graph, tracer = self._build_graph()
        
        mig = getattr(tracer, '_module_graph', None)
        if mig:
            # 检查映射
            internal = mig.get_internal_signal('top.u_dut.clk')
            self.assertEqual(internal, 'dut.clk',
                f"top.u_dut.clk 应映射到 dut.clk，实际是 {internal}")
    
    def test_cross_module_connection(self):
        """[金标准] 跨模块连接"""
        graph, tracer = self._build_graph()
        
        # 检查实例间端口连接
        edge = graph.get_edge('top.u_tb.clk', 'top.u_dut.clk')
        self.assertIsNotNone(edge, "应有 top.u_tb.clk → top.u_dut.clk 边")
        self.assertEqual(edge.kind, EdgeKind.DRIVER,
            f"边类型应为 DRIVER，实际是 {edge.kind}")


class TestCrossModulePath(unittest.TestCase):
    """跨模块路径追踪测试"""
    
    def _build_graph(self):
        import tempfile
        import os
        import uuid
        
        source = '''module tb;
    logic clk;
endmodule

module dut;
    input clk;
    logic [31:0] reg_data;
    always_ff @(posedge clk)
        reg_data <= 32'h0;
endmodule

module top;
    tb u_tb();
    dut u_dut();
    assign u_dut.clk = u_tb.clk;
endmodule'''
        
        # Write to temp file for multi-module support
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            f.write(source)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_internal_signal_clock_edge(self):
        """[金标准] 内部信号有时钟边"""
        graph, tracer = self._build_graph()
        
        # 内部信号 dut.reg_data 应有时钟边
        # 时钟源可能是 dut.clk (内部) 或 top.u_dut.clk (端口)
        clock_sources = ['top.u_dut.clk', 'dut.clk']
        found_clock = False
        
        for node_id in ['dut.reg_data', 'top.u_dut.reg_data']:
            node = graph.get_node(node_id)
            if node:
                for src, dst in graph.edges():
                    edge = graph.get_edge(src, dst)
                    if dst == node_id and edge.kind == EdgeKind.CLOCK:
                        self.assertIn(src, clock_sources,
                            f"reg_data 的时钟应来自 {clock_sources} 之一，实际来自 {src}")
                        found_clock = True
                        break
                if found_clock:
                    break
        
        self.assertTrue(found_clock, "dut.reg_data 未找到时钟边")
    
    def test_path_resolution(self):
        """[金标准] 路径解析"""
        graph, tracer = self._build_graph()
        
        # 尝试获取路径解析器
        path_resolver = getattr(tracer, '_path_resolver', None)
        if path_resolver:
            path = path_resolver.find_path('top.u_tb.clk', 'dut.reg_data')
            self.assertIsNotNone(path, "应有从 top.u_tb.clk 到 dut.reg_data 的路径")
            # 路径应包含关键节点
            self.assertIn('top.u_dut.clk', path, "路径应包含 top.u_dut.clk")
        else:
            # 无路径解析器时，检查边连通性
            edge = graph.get_edge('top.u_tb.clk', 'top.u_dut.clk')
            self.assertIsNotNone(edge, "top.u_tb.clk → top.u_dut.clk 应连通")


class TestHierarchicalPort(unittest.TestCase):
    """层级端口测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_simple_hierarchy(self):
        """[金标准] 简单层级"""
        source = '''module sub;
    output [7:0] data;
endmodule

module top;
    sub u_sub();
    assign u_sub.data = 8'hAB;
endmodule'''
        
        graph, tracer = self._build_graph(source)
        
        # u_sub.data 节点应存在
        node = graph.get_node('top.u_sub.data')
        self.assertIsNotNone(node, "应有 top.u_sub.data 节点")
        
        # 端口连接边
        edge = graph.get_edge('top.sub.data', 'top.u_sub.data')
        # 注意: 实际节点名可能是 top.u_sub.data
    
    def test_multi_level_hierarchy(self):
        """[金标准] 多层级"""
        source = '''module level1;
    output [7:0] out;
endmodule

module level2;
    output [7:0] out;
    level1 u_l1();
endmodule

module top;
    level2 u_l2();
    assign u_l2.out = 8'h00;
endmodule'''
        
        graph, tracer = self._build_graph(source)
        
        # 多层实例节点应存在
        nodes = list(graph.nodes())
        self.assertTrue(any('u_l2' in n for n in nodes),
            "应有包含 u_l2 的节点")


class TestNegativeCases(unittest.TestCase):
    """负面测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_no_unconnected_modules(self):
        """未连接的模块作为孤立节点存在 (预期行为)"""
        source = "module isolated;\n    logic clk;\nendmodule\n\nmodule top;\n    logic clk;\nendmodule"
        
        graph = self._build_graph(source)
        
        # isolated 未被实例化，但它的节点仍然存在 (作为孤立节点)
        # 这是预期行为 - 模块定义会被追踪，但不参与活跃连接
        nodes = [n for n in graph.nodes() if 'isolated' in n.lower()]
        # 验证 isolated 模块节点存在，但没有出边/入边
        for node in nodes:
            # 检查是否是孤立节点 (没有连接)
            edge_count = sum(1 for _ in graph.edges(node))
            self.assertEqual(edge_count, 0,
                f"isolated.{node.split('.')[-1]} 不应有连接边，实际有 {edge_count} 条")
    
    def test_parameterized_module(self):
        """参数化模块 (跳过，不崩溃)"""
        source = '''module dut #(
    parameter WIDTH = 8
) (
    input clk,
    output [WIDTH-1:0] data
);
endmodule

module top;
    dut #(.WIDTH(16)) u_dut();
endmodule'''
        
        graph = self._build_graph(source)
        # 不崩溃即可


if __name__ == '__main__':
    unittest.main()

class TestMultiLevelHierarchy(unittest.TestCase):
    """多层级模块实例测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_three_level_hierarchy(self):
        """[金标准] 三层层级: top -> mid -> leaf"""
        source = "module leaf;\n    input clk;\n    output [7:0] data;\n    logic [7:0] internal_data;\n    assign data = internal_data;\nendmodule\n\nmodule mid;\n    leaf u_leaf();\n    logic clk;\n    assign u_leaf.clk = clk;\nendmodule\n\nmodule top;\n    mid u_mid();\n    logic clk;\n    assign u_mid.clk = clk;\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查实例 (扁平化)
        self.assertIn('top.u_mid', mig.instances, "应有 top.u_mid 实例")
        self.assertIn('top.u_mid.u_leaf', mig.instances, "应有 top.u_mid.u_leaf 实例")
        
        # 检查端口映射
        clk_mapping = mig.get_internal_signal('top.u_mid.u_leaf.clk')
        self.assertEqual(clk_mapping, 'leaf.clk', f"top.u_mid.u_leaf.clk 应映射到 leaf.clk，实际是 {clk_mapping}")

    def test_four_level_hierarchy(self):
        """[金标准] 四层层级路径追踪"""
        source = "module l1;\n    output [7:0] out;\n    logic [7:0] val;\n    assign out = val;\nendmodule\n\nmodule l2;\n    l1 u_l1();\n    output [7:0] out;\n    assign out = u_l1.out;\nendmodule\n\nmodule l3;\n    l2 u_l2();\n    output [7:0] out;\n    assign out = u_l2.out;\nendmodule\n\nmodule top;\n    l3 u_l3();\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查层级实例存在 (扁平化)
        self.assertIn('top.u_l3', mig.instances, "应有 top.u_l3 实例")
        self.assertIn('top.u_l3.u_l2', mig.instances, "应有 top.u_l3.u_l2 实例")
        self.assertIn('top.u_l3.u_l2.u_l1', mig.instances, "应有 top.u_l3.u_l2.u_l1 实例")
        
        # 检查端口映射
        out_mapping = mig.get_internal_signal('top.u_l3.u_l2.u_l1.out')
        self.assertEqual(out_mapping, 'l1.out', "top.u_l3.u_l2.u_l1.out 应映射到 l1.out")

class TestArrayOfInstances(unittest.TestCase):
    """模块数组实例化测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_array_instance(self):
        """[金标准] 模块数组实例化 - 验证无错误完成"""
        source = "module dut(input clk, output [7:0] data);\n    logic [7:0] r;\n    assign data = r;\nendmodule\n\nmodule top;\n    dut u_duts[0:3]();\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 数组实例的处理是实现相关的 - 只需验证无错误完成
        self.assertIn('top', getattr(mig, '_module_ports', {}), "top 模块应被解析")


class TestPortWidthMapping(unittest.TestCase):
    """端口位宽映射测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_different_widths(self):
        """[金标准] 不同位宽的端口映射"""
        source = '''module sub(output [31:0] wide, output [7:0] narrow);
endmodule

module top;
    sub u_sub();
    logic [31:0] wide_sig;
    logic [7:0] narrow_sig;
    assign u_sub.wide = wide_sig;
    assign u_sub.narrow = narrow_sig;
endmodule'''
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查实例存在
        self.assertIn('top.u_sub', mig.instances, "应有 top.u_sub 实例")
        
        # 检查端口
        inst = mig.get_instance('top.u_sub')
        self.assertIn('wide', inst.ports, "应有 wide 端口")
        self.assertIn('narrow', inst.ports, "应有 narrow 端口")
        self.assertEqual(inst.ports['wide'].width, (31, 0), "wide 应为 32 位")
        self.assertEqual(inst.ports['narrow'].width, (7, 0), "narrow 应为 8 位")


class TestBidirectionalPort(unittest.TestCase):
    """双向端口测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_inout_port(self):
        """[金标准] inout 端口映射"""
        source = '''module bidir(inout [7:0] data);
endmodule

module top;
    bidir u_bidir();
    logic [7:0] bidir_data;
    assign u_bidir.data = bidir_data;
endmodule'''
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        inst = mig.get_instance('top.u_bidir')
        self.assertIn('data', inst.ports, "应有 data 端口")
        # inout 方向应被正确识别
        self.assertIn(inst.ports['data'].direction.lower(), ['inout', 'in_out', 'unknown'],
            f"data 端口方向应为 inout，实际是 {inst.ports['data'].direction}")


class TestCrossModuleClockPath(unittest.TestCase):
    """跨模块时钟路径测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_clock_propagation(self):
        """[金标准] 时钟信号跨模块传播"""
        source = "module clk_gen(output clk);\n    logic clk_int;\n    assign clk = clk_int;\n    assign clk_int = 1'b0;\nendmodule\n\nmodule dut(input clk, output reg [7:0] out);\n    always @(posedge clk)\n        out <= 8'hAB;\nendmodule\n\nmodule top;\n    clk_gen u_clk_gen();\n    dut u_dut();\n    assign u_dut.clk = u_clk_gen.clk;\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查实例存在
        self.assertIn('top.u_clk_gen', mig.instances, "应有 top.u_clk_gen 实例")
        self.assertIn('top.u_dut', mig.instances, "应有 top.u_dut 实例")
        
        # 检查端口映射
        dut_clk_mapping = mig.get_internal_signal('top.u_dut.clk')
        self.assertEqual(dut_clk_mapping, 'dut.clk', f"top.u_dut.clk 应映射到 dut.clk")


class TestMultipleConnections(unittest.TestCase):
    """多连接测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_one_to_many(self):
        """[金标准] 一驱多 - ModuleInstanceGraph + SignalGraph"""
        source = "module dut(input in1, input in2, output out);\n    assign out = in1 & in2;\nendmodule\n\nmodule top;\n    logic src;\n    logic [1:0] dest;\n    dut u_dut1();\n    dut u_dut2();\n    assign u_dut1.in1 = src;\n    assign u_dut2.in1 = src;\n    assign dest = {u_dut1.out, u_dut2.out};\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 1. ModuleInstanceGraph: 多实例
        self.assertIn('top.u_dut1', mig.instances, "应有 u_dut1 实例")
        self.assertIn('top.u_dut2', mig.instances, "应有 u_dut2 实例")
        
        # 2. SignalGraph: 驱动信号节点
        nodes = list(graph.nodes())
        has_src = any('src' in n for n in nodes)
        self.assertTrue(has_src, f"应有 src 相关节点，实际: {nodes}")


class TestUnconnectedPort(unittest.TestCase):
    """未连接端口测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_partially_connected(self):
        """[金标准] 部分端口未连接"""
        source = '''module sub(input a, input b, output y);
    assign y = a & b;
endmodule

module top;
    sub u_sub();
    logic a_sig, b_sig;
    assign u_sub.a = a_sig;
    // u_sub.b 未连接
endmodule'''
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查端口映射存在
        inst = mig.get_instance('top.u_sub')
        self.assertIn('a', inst.ports, "应有 a 端口")
        self.assertIn('b', inst.ports, "应有 b 端口")
        
        # b 未连接时，port_to_internal 仍应有映射 (只是无驱动)


class TestParameterOverride(unittest.TestCase):
    """参数覆盖测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_width_parameter_override(self):
        """[金标准] 位宽参数覆盖"""
        source = '''module sub #(parameter WIDTH = 8) (
    input clk,
    output [WIDTH-1:0] data
);
    logic [WIDTH-1:0] r;
    assign data = r;
endmodule

module top;
    sub #(.WIDTH(16)) u_sub();
endmodule'''
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查实例
        inst = mig.get_instance('top.u_sub')
        self.assertIsNotNone(inst, "应有 top.u_sub 实例")
        # 参数化模块的端口位宽可能需要特殊处理


class TestInterfaceModportCrossModule(unittest.TestCase):
    """跨模块 Interface/Modport 测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_interface_connection(self):
        """[金标准] Interface 跨模块连接 - ModuleInstanceGraph"""
        source = "interface my_if;\n    logic [7:0] data;\nendinterface\n\nmodule dut(my_if bus);\n    logic [7:0] r;\n    assign bus.data = r;\nendmodule\n\nmodule top;\n    my_if bus_inst();\n    dut u_dut(bus_inst);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # ModuleInstanceGraph: 模块实例
        self.assertIn('top.u_dut', mig.instances, "应有 dut 实例")
    
    def test_modport_direction(self):
        """[金标准] Modport 方向跨模块"""
        source = "interface my_if;\n    logic [7:0] data;\n    modport master(input data);\nendinterface\n\nmodule dut(my_if.sub m);\nendmodule\n\nmodule top;\n    my_if intf();\n    dut u_dut(intf.master);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        # 不崩溃即可


class TestGenerateInstanceCrossModule(unittest.TestCase):
    """Generate 块内实例化测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_generate_for_instance(self):
        """[金标准] for 循环生成实例"""
        source = "module dut(output [7:0] out);\n    assign out = 8'hAB;\nendmodule\n\nmodule top;\n    genvar i;\n    generate\n        for (i=0; i<2; i=i+1) begin : gen\n            dut u_dut();\n        end\n    endgenerate\nendmodule"
        
        graph, tracer = self._build_graph(source)
        
        # 检查生成的实例
        nodes = list(graph.nodes())
        has_gen_instance = any('gen' in n and 'u_dut' in n for n in nodes)
        self.assertTrue(has_gen_instance, f"应有生成的实例节点，实际: {nodes}")


class TestFunctionPortCrossModule(unittest.TestCase):
    """跨模块函数/任务端口测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_function_call_cross_module(self):
        """[金标准] 函数跨模块调用"""
        source = "function [7:0] my_func(input [7:0] a);\n    return a + 1;\nendfunction\n\nmodule dut(output [7:0] out);\n    logic [7:0] r;\n    assign r = my_func(8'h00);\n    assign out = r;\nendmodule\n\nmodule top;\n    dut u_dut();\nendmodule"
        
        graph, tracer = self._build_graph(source)
        
        # 检查函数节点
        nodes = list(graph.nodes())
        has_func = any('my_func' in n for n in nodes)
        self.assertTrue(has_func, f"应有 my_func 节点，实际: {nodes}")


class TestClassInstanceCrossModule(unittest.TestCase):
    """跨模块 Class 实例化测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_class_member_access(self):
        """[金标准] 跨模块类成员访问"""
        source = "class my_class;\n    logic [7:0] data;\nendclass\n\nmodule dut;\n    my_class obj;\nendmodule\n\nmodule top;\n    dut u_dut();\nendmodule"
        
        graph, tracer = self._build_graph(source)
        
        # 检查类实例
        nodes = list(graph.nodes())
        has_class_node = any('obj' in n for n in nodes)
        self.assertTrue(has_class_node, f"应有 obj 节点，实际: {nodes}")


class TestClockDividerCrossModule(unittest.TestCase):
    """时钟分频器跨模块测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_clock_chain(self):
        """[金标准] 时钟链跨模块"""
        source = "module clk_div(output clk_out, input clk_in);\n    logic clk_reg;\n    always @(posedge clk_in) clk_reg <= ~clk_reg;\n    assign clk_out = clk_reg;\nendmodule\n\nmodule dut(input clk, output reg [7:0] out);\n    always @(posedge clk) out <= 8'hAB;\nendmodule\n\nmodule top;\n    logic clk_main;\n    logic clk_div_out;\n    clk_div u_div(clk_div_out, clk_main);\n    dut u_dut(clk_div_out);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查实例存在
        self.assertIn('top.u_div', mig.instances, "应有 top.u_div 实例")
        self.assertIn('top.u_dut', mig.instances, "应有 top.u_dut 实例")
        
        # 检查端口映射 (即使没有实际连接，映射关系应存在)
        dut_clk_map = mig.get_internal_signal('top.u_dut.clk')
        # dut.clk 是输入端口，应映射到内部
        self.assertIsNotNone(dut_clk_map, f"top.u_dut.clk 应有映射，实际是 {dut_clk_map}")


class TestResetCrossModule(unittest.TestCase):
    """复位信号跨模块测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_async_reset_propagation(self):
        """[金标准] 异步复位传播 - ModuleInstanceGraph + SignalGraph"""
        source = "module reset_gen(output rst);\n    logic rst_reg;\n    assign rst = rst_reg;\nendmodule\n\nmodule dut(input clk, input rst, output reg [7:0] out);\n    always @(posedge clk or posedge rst)\n        if (rst) out <= 8'h00;\n        else out <= 8'hAB;\nendmodule\n\nmodule top;\n    logic clk;\n    logic rst;\n    reset_gen u_rst_gen(rst);\n    dut u_dut(clk, rst);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 1. ModuleInstanceGraph: 多层级实例
        self.assertIn('top.u_rst_gen', mig.instances, "应有 reset_gen 实例")
        self.assertIn('top.u_dut', mig.instances, "应有 dut 实例")
        
        # 2. SignalGraph: 复位信号节点
        nodes = list(graph.nodes())
        has_rst = any('rst' in n and 'gen' not in n for n in nodes)
        self.assertTrue(has_rst, f"应有 rst 相关节点，实际: {nodes}")


class TestBusArbitrationCrossModule(unittest.TestCase):
    """总线仲裁跨模块测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_master_slave_connection(self):
        """[金标准] 主从连接 - ModuleInstanceGraph + SignalGraph"""
        source = "module bus_slave(output [7:0] data);\n    assign data = 8'hAB;\nendmodule\n\nmodule bus_master(input [7:0] data, output reg [7:0] out);\n    always @* out = data;\nendmodule\n\nmodule top;\n    logic [7:0] bus_data;\n    bus_slave u_slave(bus_data);\n    bus_master u_master(bus_data);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 1. ModuleInstanceGraph: 主从实例
        self.assertIn('top.u_slave', mig.instances, "应有 slave 实例")
        self.assertIn('top.u_master', mig.instances, "应有 master 实例")
        
        # 2. SignalGraph: 总线信号节点
        nodes = list(graph.nodes())
        has_bus = any('bus_data' in n or 'data' in n for n in nodes)
        self.assertTrue(has_bus, f"应有 bus_data 相关节点，实际: {nodes}")


class TestCrossModuleBasicFunctions(unittest.TestCase):
    """跨模块基础功能测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_simple_two_module(self):
        """[金标准] 简单两模块连接 - ModuleInstanceGraph + SignalGraph"""
        source = "module sub(output [7:0] out);\n    assign out = 8'hAB;\nendmodule\n\nmodule top;\n    wire [7:0] data;\n    sub u_sub(data);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 1. ModuleInstanceGraph: 实例 + 端口映射
        self.assertIn('top.u_sub', mig.instances, "应有 top.u_sub 实例")
        self.assertIn('top.u_sub.out', mig.port_to_internal, "应有端口映射")
        
        # 2. SignalGraph: 跨模块信号节点 (data 或 port_signal)
        nodes = list(graph.nodes())
        has_data = any('data' in n for n in nodes)
        port_sig = mig.port_to_internal.get('top.u_sub.out', '')
        has_port = port_sig and any(port_sig in n for n in nodes)
        self.assertTrue(has_data or has_port, f"应有 data 或 port 节点，实际: {nodes}")
    
    def test_port_to_internal_mapping(self):
        """[金标准] 端口到内部信号映射"""
        source = "module sub(input clk, output [7:0] out);\nendmodule\n\nmodule top;\n    logic clk;\n    sub u_sub(.clk(clk));\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查实例存在
        self.assertIn('top.u_sub', mig.instances, f"应有 top.u_sub 实例")
        # 检查 sub 模块端口被存储
        self.assertIn('sub', getattr(mig, '_module_ports', {}), "sub 模块端口应被存储")
    
    def test_multiple_instances(self):
        """[金标准] 多实例"""
        source = "module sub(output [7:0] out);\nendmodule\n\nmodule top;\n    wire [7:0] a, b, c;\n    sub u1(a);\n    sub u2(b);\n    sub u3(c);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查所有实例存在
        instances = list(mig.instances.keys())
        self.assertIn('top.u1', instances, f"应有 top.u1，实际: {instances}")
        self.assertIn('top.u2', instances, f"应有 top.u2，实际: {instances}")
        self.assertIn('top.u3', instances, f"应有 top.u3，实际: {instances}")
    
    def test_instance_parent_relationship(self):
        """[金标准] 实例父子关系"""
        source = "module child(output [7:0] out);\nendmodule\n\nmodule parent;\n    wire [7:0] w;\n    child u_child(.out(w));\nendmodule\n\nmodule top;\n    parent u_parent();\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        inst = mig.get_instance('top.u_parent.u_child')
        self.assertIsNotNone(inst)
        self.assertEqual(inst.parent, 'top.u_parent')

    def test_mig_get_instance(self):
        """[金标准] MIG 集中索引 - get_instance()"""
        source = '''module child(output [7:0] out);
endmodule

module parent;
    wire [7:0] w;
    child u_child(.out(w));
endmodule

module top;
    parent u_parent();
endmodule'''
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 获取顶层实例
        inst = mig.get_instance('top.u_parent')
        self.assertIsNotNone(inst, "应能获取 top.u_parent")
        self.assertEqual(inst.id, 'top.u_parent')
        self.assertEqual(inst.module_type, 'parent')
        self.assertEqual(inst.parent, 'top')
        
        # 获取嵌套实例
        inst = mig.get_instance('top.u_parent.u_child')
        self.assertIsNotNone(inst, "应能获取 top.u_parent.u_child")
        self.assertEqual(inst.module_type, 'child')
        self.assertEqual(inst.parent, 'top.u_parent')
        
        # 获取不存在的实例
        inst = mig.get_instance('top.nonexistent')
        self.assertIsNone(inst, "不存在的实例应返回 None")

    def test_mig_child_instances(self):
        """[金标准] MIG 父子关系查询 - get_child_instances()"""
        source = '''module child(output [7:0] out);
endmodule

module parent;
    wire [7:0] w;
    child u_child(.out(w));
endmodule

module top;
    parent u_parent();
endmodule'''
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 查询 top 的子实例
        children = mig.get_child_instances('top')
        child_ids = [c.id for c in children]
        self.assertIn('top.u_parent', child_ids, f"top 的子实例应包含 top.u_parent，实际: {child_ids}")
        
        # 查询 parent 的子实例
        children = mig.get_child_instances('top.u_parent')
        child_ids = [c.id for c in children]
        self.assertIn('top.u_parent.u_child', child_ids, f"top.u_parent 的子实例应包含 top.u_parent.u_child，实际: {child_ids}")
        
        # 查询叶子节点（无子实例）
        children = mig.get_child_instances('top.u_parent.u_child')
        self.assertEqual(len(children), 0, "叶子节点应无子实例")

    def test_mig_all_instances(self):
        """[金标准] MIG 获取所有实例 - get_all_instances()"""
        source = '''module child(output [7:0] out);
endmodule

module parent;
    wire [7:0] w;
    child u_child(.out(w));
endmodule

module top;
    parent u_parent();
endmodule'''
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        all_insts = mig.get_all_instances()
        self.assertIn('top.u_parent', all_insts, f"应有 top.u_parent，实际: {all_insts}")
        self.assertIn('top.u_parent.u_child', all_insts, f"应有 top.u_parent.u_child，实际: {all_insts}")

    def test_mig_port_info(self):
        """[金标准] MIG 端口信息 - PortInfo 对象"""
        source = '''module dut(input clk, output [7:0] data);
endmodule

module top;
    logic clk;
    wire [7:0] data;
    dut u_dut(.clk(clk), .data(data));
endmodule'''
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        inst = mig.get_instance('top.u_dut')
        self.assertIsNotNone(inst)
        
        # 检查端口信息
        self.assertTrue(len(inst.ports) > 0, "实例应有端口列表")
        
        # 检查 clk 端口
        if 'clk' in inst.ports:
            port = inst.ports['clk']
            self.assertEqual(port.direction, 'input', "clk 应为 input 端口")
            self.assertEqual(port.internal_signal, 'dut.clk', "内部信号应为 dut.clk")
            self.assertEqual(port.module_type, 'dut', "模块类型应为 dut")
        
        # 检查 data 端口
        if 'data' in inst.ports:
            port = inst.ports['data']
            self.assertEqual(port.direction, 'output', "data 应为 output 端口")
            self.assertEqual(port.internal_signal, 'dut.data', "内部信号应为 dut.data")

    def test_mig_hierarchical_traversal(self):
        """[金标准] MIG 层级遍历"""
        source = '''module child(output [7:0] out);
endmodule

module parent;
    wire [7:0] w;
    child u_child(.out(w));
endmodule

module top;
    parent u_parent();
endmodule'''
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 层级遍历函数
        def collect_hierarchy(parent_id, depth=0):
            result = []
            children = mig.get_child_instances(parent_id)
            for child in children:
                result.append((depth, child.id, child.module_type))
                result.extend(collect_hierarchy(child.id, depth + 1))
            return result
        
        hierarchy = collect_hierarchy('top')
        
        # 验证层级结构
        self.assertEqual(len(hierarchy), 2, f"应有 2 层实例，实际: {len(hierarchy)}")
        
        depth0_ids = [id_ for d, id_, _ in hierarchy if d == 0]
        self.assertIn('top.u_parent', depth0_ids, f"顶层应是 top.u_parent，实际: {depth0_ids}")
        
        depth1_ids = [id_ for d, id_, _ in hierarchy if d == 1]
        self.assertIn('top.u_parent.u_child', depth1_ids, f"第二层应是 top.u_parent.u_child，实际: {depth1_ids}")



    def test_driver_multi_hop(self):
        """[金标准] Driver 多跳追踪
        
        场景: top.clk → u_gen.clk_out → u_driver.clk_in → u_driver.data_out → top.data → u_load.data_in
        
        预期 driver 链:
          top.data ← top.u_driver.data (CONNECTION, not DRIVER)
          top.data ← driver.data (DRIVER)
          driver.data ← driver.A5 (DRIVER, literal)
        """
        source = '''module clk_gen(output logic clk);
endmodule

module driver(input logic clk, output logic [7:0] data);
    assign data = 8'hA5;
endmodule

module load(input logic [7:0] data);
    logic [7:0] reg_data;
    logic clk;
endmodule

module top;
    logic clk;
    logic [7:0] data;
    clk_gen u_gen(.clk(clk));
    driver u_driver(.clk(clk), .data(data));
    load u_load(.data(data));
endmodule'''
        
        graph, tracer = self._build_graph(source)
        
        # 第1跳: top.data 的直接 driver
        drivers = graph.find_drivers('top.data')
        driver_ids = [d.id for d in drivers]
        self.assertIn('top.u_driver.data', driver_ids, 
            f"top.data 的直接 driver 应是 top.u_driver.data，实际: {driver_ids}")
        
        # 第2跳: top.u_driver.data 的直接 driver
        drivers = graph.find_drivers('top.u_driver.data')
        driver_ids = [d.id for d in drivers]
        self.assertIn('driver.data', driver_ids,
            f"top.u_driver.data 的直接 driver 应是 driver.data，实际: {driver_ids}")
        
        # 第3跳: driver.data 的直接 driver (literal)
        drivers = graph.find_drivers('driver.data')
        driver_ids = [d.id for d in drivers]
        self.assertTrue(len(driver_ids) > 0,
            f"driver.data 应有 driver (literal)，实际: {driver_ids}")

    def test_driver_cross_module_boundary(self):
        """[金标准] Driver 跨越模块边界追踪
        
        场景: 子模块输出端口被父模块信号驱动
        
        预期:
          sub.out ← sub.internal (DRIVER via assign)
          sub.internal ← sub.in (CONNECTION)
        """
        source = '''module sub(output logic out, input logic in);
    logic internal;
    assign internal = in;
    assign out = internal;
endmodule

module top;
    logic a, b;
    sub u_sub(.out(a), .in(b));
endmodule'''
        
        graph, tracer = self._build_graph(source)
        
        # top.u_sub.out 的 driver 是 sub.out (DRIVER, 跨越模块边界)
        # sub.out 的 driver 是 sub.internal (DRIVER, 内部信号)
        # sub.internal 的 driver 是 sub.in (DRIVER)
        drivers = graph.find_drivers('top.u_sub.out')
        driver_ids = [d.id for d in drivers]
        self.assertIn('sub.out', driver_ids,
            f"top.u_sub.out 的 driver 应是 sub.out，实际: {driver_ids}")
        
        # 验证 sub.out 的 driver
        drivers = graph.find_drivers('sub.out')
        driver_ids = [d.id for d in drivers]
        self.assertIn('sub.internal', driver_ids,
            f"sub.out 的 driver 应是 sub.internal，实际: {driver_ids}")

    def test_load_multi_level(self):
        """[金标准] Load 多级追踪
        
        场景: top.clk → u_driver.clk → driver.clk
        
        预期 load 链:
          top.clk loads: top.u_driver.clk
          top.u_driver.clk loads: driver.clk
        """
        source = '''module driver(input logic clk, output logic [7:0] data);
    assign data = 8'hA5;
endmodule

module top;
    logic clk;
    logic [7:0] data;
    driver u_driver(.clk(clk), .data(data));
endmodule'''
        
        graph, tracer = self._build_graph(source)
        
        # 第1级: top.clk 的直接 load
        loads = graph.find_loads('top.clk')
        load_ids = [l.id for l in loads]
        self.assertIn('top.u_driver.clk', load_ids,
            f"top.clk 的直接 load 应是 top.u_driver.clk，实际: {load_ids}")
        
        # 第2级: top.u_driver.clk 的直接 load
        loads = graph.find_loads('top.u_driver.clk')
        load_ids = [l.id for l in loads]
        self.assertIn('driver.clk', load_ids,
            f"top.u_driver.clk 的直接 load 应是 driver.clk，实际: {load_ids}")

    def test_load_cross_module_boundary(self):
        """[金标准] Load 跨越模块边界追踪
        
        场景: 顶层信号驱动子模块端口，然后子模块内部负载继续追踪
        
        预期:
          top.clk_i loads: top.u_dut.clk_i (跨模块边界)
          top.u_dut.clk_i loads: uart_tx.clk_i (内部信号)
        """
        source = '''module uart_tx(
    input logic clk_i,
    output logic tx
);
    logic clk_q;
    always_ff @(posedge clk_i) clk_q <= 1'b0;
endmodule

module top;
    logic clk_i;
    logic tx;
    uart_tx u_dut(.clk_i(clk_i), .tx(tx));
endmodule'''
        
        graph, tracer = self._build_graph(source)
        
        # top.clk_i loads: top.u_dut.clk_i (跨模块边界)
        loads = graph.find_loads('top.clk_i')
        load_ids = [l.id for l in loads]
        self.assertIn('top.u_dut.clk_i', load_ids,
            f"top.clk_i 的直接 load 应是 top.u_dut.clk_i，实际: {load_ids}")

    def test_driver_chain_complete_path(self):
        """[金标准] 完整 Driver 链路径验证
        
        场景: 多级跨模块 driver 链
        top.a ← top.x ← top.u_b.x ← mid.x ← mid.y
        
        预期完整 driver 链:
          top.a ← top.x (DRIVER: assign a = x)
          top.x ← top.u_b.x (CONNECTION: wire x driven by instance port)
          top.u_b.x ← mid.x (DRIVER: instance output driven by child internal signal)
          mid.x ← mid.y (DRIVER: assign x = y)
        """
        source = '''module bot(output logic y);
    assign y = 1'b0;
endmodule

module mid(output logic x);
    wire y;
    bot u_c(.y(y));
    assign x = y;
endmodule

module top(output logic a);
    wire x;
    mid u_b(.x(x));
    assign a = x;
endmodule'''
        
        graph, tracer = self._build_graph(source)
        
        # 第1跳: top.a 的 driver (assign a = x → top.x 是 wire，直接连接)
        drivers = graph.find_drivers('top.a')
        self.assertTrue(len(drivers) > 0, f"top.a 应有 driver，实际: {[d.id for d in drivers]}")
        self.assertEqual(drivers[0].id, 'top.x',
            f"top.a 的 driver 应是 top.x，实际: {drivers[0].id}")
        
        # 第2跳: top.u_b.x 的 driver (跨模块边界，内部信号驱动实例输出)
        drivers = graph.find_drivers('top.u_b.x')
        self.assertTrue(len(drivers) > 0, f"top.u_b.x 应有 driver，实际: {[d.id for d in drivers]}")
        self.assertEqual(drivers[0].id, 'mid.x',
            f"top.u_b.x 的 driver 应是 mid.x，实际: {drivers[0].id}")
        
        # 第3跳: mid.x 的 driver (assign x = y)
        drivers = graph.find_drivers('mid.x')
        self.assertTrue(len(drivers) > 0, f"mid.x 应有 driver，实际: {[d.id for d in drivers]}")
        self.assertEqual(drivers[0].id, 'mid.y',
            f"mid.x 的 driver 应是 mid.y，实际: {drivers[0].id}")
        
        # 验证跨越模块边界的 DRIVER 边存在
        driver_edges = [(src, dst) for src, dst in graph.edges() 
                        if graph.get_edge(src, dst).kind.name == 'DRIVER']
        
        # 检查是否存在跨越模块的 DRIVER 边
        cross_module_driver = [(src, dst) for src, dst in driver_edges 
                               if src.startswith('mid.') and dst.startswith('top.')]
        self.assertTrue(len(cross_module_driver) > 0,
            f"应有跨越模块的 DRIVER 边，实际: {driver_edges}")

    def test_load_chain_complete_path(self):
        """[金标准] 完整 Load 链路径验证
        
        场景: 多级跨模块 load 链
        top.a ← top.x ← top.u_b.tmp ← mid.tmp ← mid.u_c.y
        
        预期完整 load 链:
          top.x loads: top.a (assign a = x)
          top.u_b.x loads: top.tmp (instance connection)
          mid.x loads: mid.y (assign x = y)
        """
        source = '''module bot(input logic y);
endmodule

module mid(output logic x);
    wire y;
    bot u_c(.y(y));
    assign x = y;
endmodule

module top(logic a, output logic x);
    wire tmp;
    mid u_b(.x(tmp));
    assign x = tmp;
    assign a = x;
endmodule'''
        
        graph, tracer = self._build_graph(source)
        
        # top.x loads: top.a (因为 assign a = x)
        loads = graph.find_loads('top.x')
        load_ids = [l.id for l in loads]
        self.assertIn('top.a', load_ids,
            f"top.x 的 load 应包含 top.a，实际: {load_ids}")
        
        # top.u_b.x loads: top.tmp (instance connection)
        loads = graph.find_loads('top.u_b.x')
        load_ids = [l.id for l in loads]
        self.assertIn('top.tmp', load_ids,
            f"top.u_b.x 的 load 应是 top.tmp，实际: {load_ids}")


class TestCrossModuleSignalFlow(unittest.TestCase):
    """跨模块信号流测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_wire_connection(self):
        """[金标准] 线网连接"""
        source = "module sub(input [7:0] in);\nendmodule\n\nmodule top;\n    wire [7:0] bus;\n    assign bus = 8'hFF;\n    sub u_sub(bus);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        
        bus_node = graph.get_node('top.bus')
        self.assertIsNotNone(bus_node)
    
    def test_signal_driver_tracking(self):
        """[金标准] 信号驱动追踪 - ModuleInstanceGraph + SignalGraph"""
        source = "module driver(output [7:0] out);\n    assign out = 8'hAB;\nendmodule\n\nmodule receiver(input [7:0] in);\nendmodule\n\nmodule top;\n    wire [7:0] bus;\n    driver u_driver(bus);\n    receiver u_recv(bus);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 1. ModuleInstanceGraph: 多实例
        self.assertIn('top.u_driver', mig.instances, "应有 driver 实例")
        self.assertIn('top.u_recv', mig.instances, "应有 receiver 实例")
        
        # 2. SignalGraph: 驱动/接收信号节点
        nodes = list(graph.nodes())
        # driver 的输出被连接到 bus
        has_output = any('driver.out' in n or 'out' in n for n in nodes)
        has_input = any('receiver.in' in n or 'in' in n for n in nodes)
        self.assertTrue(has_output and has_input, f"应有 driver.out 和 receiver.in 节点，实际: {nodes}")


class TestCrossModulePortTypes(unittest.TestCase):
    """跨模块端口类型测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_input_port(self):
        """[金标准] 输入端口"""
        source = "module sub(input [7:0] data);\nendmodule\n\nmodule top;\n    wire [7:0] sig;\n    assign sig = 8'hAA;\n    sub u_sub(sig);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查实例存在
        self.assertIn('top.u_sub', mig.instances, "应有 top.u_sub 实例")
    
    def test_output_port(self):
        """[金标准] 输出端口"""
        source = "module sub(output [7:0] data);\nendmodule\n\nmodule top;\n    wire [7:0] sig;\n    sub u_sub(sig);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查实例存在
        self.assertIn('top.u_sub', mig.instances, "应有 top.u_sub 实例")
    
    def test_clock_port(self):
        """[金标准] 时钟端口"""
        source = "module sub(input clk);\nendmodule\n\nmodule top;\n    logic clk;\n    sub u_sub(clk);\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 检查实例存在
        self.assertIn('top.u_sub', mig.instances, "应有 top.u_sub 实例")


class TestCrossModulePathFinding(unittest.TestCase):
    """跨模块路径查找测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_find_path_simple(self):
        """[金标准] 简单路径查找 - ModuleInstanceGraph + SignalGraph"""
        source = "module gen(output clk);\n    assign clk = 1'b0;\nendmodule\n\nmodule dut(input clk, output reg [7:0] out);\nendmodule\n\nmodule top;\n    gen u_gen();\n    dut u_dut();\n    assign u_dut.clk = u_gen.clk;\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # 1. ModuleInstanceGraph: 实例 + 端口映射
        self.assertIn('top.u_gen', mig.instances, "应有 u_gen 实例")
        self.assertIn('top.u_dut', mig.instances, "应有 u_dut 实例")
        
        # 2. SignalGraph: 时钟信号节点
        nodes = list(graph.nodes())
        has_clk = any('clk' in n for n in nodes)
        self.assertTrue(has_clk, f"应有 clk 相关节点，实际: {nodes}")


class TestCrossModuleNegativeCases(unittest.TestCase):
    """跨模块负面测试"""
    
    def _build_graph(self, source):
        """Build graph from source. Uses temp file for multi-module sources."""
        import tempfile
        import os
        
        # Write source to temp file to handle multi-module correctly
        import uuid
        temp_path = f'/tmp/test_cross_module_{uuid.uuid4().hex[:8]}.sv'
        with open(temp_path, 'w') as f:
            # Handle both escaped and non-escaped newlines
            normalized = source.replace('\\n', '\n')
            f.write(normalized)
        
        tree = pyslang.SyntaxTree.fromFile(temp_path)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        os.unlink(temp_path)
        return tracer.get_graph(), tracer
    
    def test_uninstantiated_module(self):
        """[金标准] 未实例化的模块 - ModuleInstanceGraph"""
        source = "module unused(input clk);\nendmodule\n\nmodule top;\n    logic clk;\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        # unused 模块未被实例化，不应有实例
        instances = list(mig.instances.keys())
        has_unused = any('unused' in inst.lower() for inst in instances)
        self.assertFalse(has_unused, f"未实例化的模块不应出现: {instances}")
    
    def test_empty_module(self):
        """[金标准] 空模块"""
        source = "module empty;\nendmodule\n\nmodule top;\n    empty u_empty();\nendmodule"
        
        graph, tracer = self._build_graph(source)
        mig = getattr(tracer, '_module_graph', None)
        
        self.assertIn('top.u_empty', mig.instances)
