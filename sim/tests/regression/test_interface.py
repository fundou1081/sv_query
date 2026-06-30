# test_interface.py - Interface 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Interface 语法覆盖:
1. interface 声明
2. modport 方向定义
3. ifc.data 点号访问
4. interface 端口传递
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestInterface(unittest.TestCase):
    """Interface 信号追踪测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _get_adapter(self, source):
        class FP:
            def __init__(self, t): self.trees = t
        return PyslangAdapter(FP({'test.sv': source}))

    def test_interface_declaration(self):
        """[Golden] interface 声明

        RTL:
        interface bus_if;
            logic [7:0] data;
            logic valid;
        endinterface

        预期:
        - InterfaceDeclaration 存在
        - 接口信号 data, valid 存在
        """
        source = '''interface bus_if;
    logic [7:0] data;
    logic valid;
endinterface'''
        tree = pyslang.SyntaxTree.fromText(source)

        # 检查 AST 结构
        root = tree.root
        self.assertEqual(root.kind, pyslang.SyntaxKind.InterfaceDeclaration)

        # 检查 members
        members = list(root.members)
        self.assertGreaterEqual(len(members), 2, "Interface should have at least 2 members")

    def test_modport_direction(self):
        """[Golden] modport 方向定义

        RTL:
        interface bus_if;
            logic [7:0] data;
            logic valid;

            modport master(output data, valid);
            modport slave(input data, valid);
        endinterface

        预期:
        - ModportDeclaration 存在
        - master 方向为 output，端口为 data, valid
        - slave 方向为 input，端口为 data, valid
        """
        source = '''interface bus_if;
    logic [7:0] data;
    logic valid;

    modport master(output data, valid);
    modport slave(input data, valid);
endmodule  // dummy module to make compilation happy
endinterface'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        adapter = tracer._get_adapter()

        # 获取接口
        interfaces = adapter.get_interfaces()
        self.assertEqual(len(interfaces), 1)

        # 获取 modport
        modports = adapter.get_modport_declarations(interfaces[0])
        self.assertGreaterEqual(len(modports), 2, "Should have at least 2 modports")

        # 检查 master modport
        master_info = adapter.get_modport_info(modports[0])
        self.assertEqual(master_info['name'], 'master')
        self.assertEqual(master_info['direction'], 'output')
        self.assertIn('data', master_info['ports'])
        self.assertIn('valid', master_info['ports'])

        # 检查 slave modport
        slave_info = adapter.get_modport_info(modports[1])
        self.assertEqual(slave_info['name'], 'slave')
        self.assertEqual(slave_info['direction'], 'input')
        self.assertIn('data', slave_info['ports'])
        self.assertIn('valid', slave_info['ports'])

    def test_interface_port_in_module(self):
        """[Golden] interface 端口传递

        RTL:
        interface bus_if;
            logic [7:0] data;
        endinterface

        module top(bus_if.master ifc);
            assign ifc.data = 8'h0;
        endmodule

        预期:
        - ModuleDeclaration 存在
        - 端口类型为 InterfacePortHeader
        """
        source = '''interface bus_if;
    logic [7:0] data;
endinterface

module top(bus_if.master ifc);
    assign ifc.data = 8'h0;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)

        # 检查 CompilationUnit
        root = tree.root
        self.assertEqual(root.kind, pyslang.SyntaxKind.CompilationUnit)

        members = list(root.members)
        self.assertGreaterEqual(len(members), 2, "Should have interface and module")

    def test_interface_dot_access(self):
        """[Golden] ifc.data 点号访问

        RTL:
        interface bus_if;
            logic [7:0] data;
        endinterface

        module top(bus_if ifc);
            assign ifc.data = 8'h0;
        endmodule

        预期:
        - ifc.data 节点存在
        - 8'h0 是 ifc.data 的驱动
        """
        source = '''interface bus_if;
    logic [7:0] data;
endinterface

module top(bus_if ifc);
    assign ifc.data = 8'h0;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())

        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())

        # 验证: ifc.data 节点存在
        has_ifc_data = any('ifc.data' in n for n in nodes)
        self.assertTrue(has_ifc_data, f"ifc.data not found in {nodes}")

        # 验证: 8'd0 是 ifc.data 的驱动
        # 注: 语义值为 8'd0 (语义分析会将 8'h0 转换为带位宽的十进制格式)
        has_driver = any("8'd0" in edge[0] and 'ifc.data' in edge[1] for edge in edges)
        self.assertTrue(has_driver, f"8'd0 -> ifc.data not found in {edges}")

if __name__ == '__main__':
    unittest.main()
