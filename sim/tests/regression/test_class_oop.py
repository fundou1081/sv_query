# test_class_oop.py - Class OOP 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestClassOOP(unittest.TestCase):
    """Class OOP 信号追踪测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_class_basic(self):
        """[Golden] Class 定义与实例化
        
        RTL:
        class my_cls;
            logic [7:0] data;
        endclass
        
        module top;
            my_cls obj = new();
        endmodule
        
        预期:
        - Class 节点可识别
        - obj 实例存在
        """
        source = '''class my_cls;
    logic [7:0] data;
endclass

module top;
    my_cls obj = new();
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # [铁律13] 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        
        # 验证: obj 节点存在
        self.assertTrue(any('obj' in n for n in nodes), 
            f"obj not found in {nodes}")
    
    def test_class_member_access(self):
        """[Golden] Class 成员访问
        
        RTL:
        class packet;
            logic [31:0] addr;
        endclass
        
        module top;
            packet p = new();
            assign out = p.addr;
        endmodule
        
        预期:
        - p.addr 节点存在
        """
        source = '''class packet;
    logic [31:0] addr;
endclass

module top;
    packet p = new();
    logic [31:0] out;
    assign out = p.addr;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # [铁律13] 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        
        # 验证: p.addr 或 addr 节点存在
        has_addr = any('addr' in n or 'p.addr' in n for n in nodes)
        self.assertTrue(has_addr, 
            f"p.addr not found in {nodes}")

if __name__ == '__main__':
    unittest.main()
