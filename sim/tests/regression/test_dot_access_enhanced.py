# test_dot_access_enhanced.py - 增强 dot access 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
增强 dot access 场景:
1. interface 多信号访问
2. struct 成员访问
3. 数组元素访问
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestDotAccessEnhanced(unittest.TestCase):
    """增强 dot access 测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_multiple_signals(self):
        """[Golden] interface 多信号访问
        
        RTL:
        interface bus_if;
            logic [7:0] data;
            logic valid;
        endinterface
        
        module top(bus_if.master ifc);
            assign ifc.data = 8'h0;
            assign ifc.valid = 1'b1;
        endmodule
        
        预期:
        - ifc.data 节点存在
        - ifc.valid 节点存在
        - 8'h0 -> ifc.data 驱动关系
        - 1'b1 -> ifc.valid 驱动关系
        """
        source = '''interface bus_if;
    logic [7:0] data;
    logic valid;
endinterface

module top(bus_if.master ifc);
    assign ifc.data = 8'h0;
    assign ifc.valid = 1'b1;
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
        
        # 验证: ifc.valid 节点存在
        has_ifc_valid = any('ifc.valid' in n for n in nodes)
        self.assertTrue(has_ifc_valid, f"ifc.valid not found in {nodes}")
        
        # 验证: 8'h0 -> ifc.data
        has_data_driver = any("8'h0" in edge[0] and 'ifc.data' in edge[1] for edge in edges)
        self.assertTrue(has_data_driver, f"8'h0 -> ifc.data not found in {edges}")
        
        # 验证: 1'b1 -> ifc.valid
        has_valid_driver = any("1'b1" in edge[0] and 'ifc.valid' in edge[1] for edge in edges)
        self.assertTrue(has_valid_driver, f"1'b1 -> ifc.valid not found in {edges}")
    
    def test_struct_member_access(self):
        """[Golden] struct 成员访问
        
        RTL:
        typedef struct {
            logic [7:0] addr;
            logic [31:0] data;
        } packet_t;
        
        module top;
            packet_t pkt;
            assign pkt.addr = 8'h0;
            assign pkt.data = 32'h0;
        endmodule
        
        预期:
        - pkt.addr 节点存在
        - pkt.data 节点存在
        """
        source = '''module top;
    typedef struct {
        logic [7:0] addr;
        logic [31:0] data;
    } packet_t;
    
    packet_t pkt;
    assign pkt.addr = 8'h0;
    assign pkt.data = 32'h0;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: pkt.addr 节点存在
        has_pkt_addr = any('pkt.addr' in n for n in nodes)
        self.assertTrue(has_pkt_addr, f"pkt.addr not found in {nodes}")
        
        # 验证: pkt.data 节点存在
        has_pkt_data = any('pkt.data' in n for n in nodes)
        self.assertTrue(has_pkt_data, f"pkt.data not found in {nodes}")
        
        # 验证: 8'h0 -> pkt.addr
        has_addr_driver = any("8'h0" in edge[0] and 'pkt.addr' in edge[1] for edge in edges)
        self.assertTrue(has_addr_driver, f"8'h0 -> pkt.addr not found in {edges}")
        
        # 验证: 32'h0 -> pkt.data
        has_data_driver = any("32'h0" in edge[0] and 'pkt.data' in edge[1] for edge in edges)
        self.assertTrue(has_data_driver, f"32'h0 -> pkt.data not found in {edges}")
    
    def test_array_element_access(self):
        """[Golden] 数组元素访问
        
        RTL:
        module top;
            logic [7:0] mem [0:255];
            assign mem[0] = 8'hAA;
            assign mem[1] = 8'hBB;
        endmodule
        
        预期:
        - mem[0] 节点存在
        - mem[1] 节点存在
        """
        source = '''module top;
    logic [7:0] mem [0:255];
    assign mem[0] = 8'hAA;
    assign mem[1] = 8'hBB;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: mem 节点存在
        has_mem = any('mem' in n for n in nodes)
        self.assertTrue(has_mem, f"mem not found in {nodes}")
        
        # 验证: 8'hAA -> mem
        has_aa_driver = any("8'hAA" in edge[0] and 'mem' in edge[1] for edge in edges)
        self.assertTrue(has_aa_driver, f"8'hAA -> mem not found in {edges}")
        
        # 验证: 8'hBB -> mem
        has_bb_driver = any("8'hBB" in edge[0] and 'mem' in edge[1] for edge in edges)
        self.assertTrue(has_bb_driver, f"8'hBB -> mem not found in {edges}")

if __name__ == '__main__':
    unittest.main()
