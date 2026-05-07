# test_clocking.py - Clocking Block 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Clocking Block 语法覆盖:
1. clocking 声明
2. clocking 方向 (input/output)
3. clocking 信号列表
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestClocking(unittest.TestCase):
    """Clocking Block 支持测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def _get_adapter(self, tree):
        class FP:
            def __init__(self, t): self.trees = t
        return PyslangAdapter(FP({'test': tree}))
    
    def test_clocking_declaration(self):
        """[Golden] clocking 声明
        
        RTL:
        module top(input clk, logic data, output logic valid);
            clocking cb @(posedge clk);
                input data;
                output valid;
            endclocking
        endmodule
        
        预期:
        - ClockingDeclaration 存在
        - 包含 2 个 ClockingItem
        """
        source = '''module top(input clk, logic data, output logic valid);
    clocking cb @(posedge clk);
        input data;
        output valid;
    endclocking
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 ClockingDeclaration
        clocking_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.ClockingDeclaration:
                clocking_decl = m
                break
        
        self.assertIsNotNone(clocking_decl, "ClockingDeclaration not found")
        
        # 检查 items
        items = list(clocking_decl.items)
        self.assertGreaterEqual(len(items), 2, "Should have at least 2 items")
    
    def test_clocking_direction(self):
        """[Golden] clocking 方向
        
        RTL:
        clocking cb @(posedge clk);
            input data;
            output valid;
        endclocking
        
        预期:
        - ClockingItem 有 input 方向
        - ClockingItem 有 output 方向
        """
        source = '''module top(input clk, logic data, output logic valid);
    clocking cb @(posedge clk);
        input data;
        output valid;
    endclocking
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        members = list(root.members)
        clocking_decl = members[0]
        
        items = list(clocking_decl.items)
        
        # 检查方向
        directions = []
        for item in items:
            for child in item:
                kind = getattr(child, 'kind', None)
                if kind == pyslang.SyntaxKind.ClockingDirection:
                    directions.append(str(child).strip())
        
        self.assertTrue(any('input' in d for d in directions), "input direction not found")
        self.assertTrue(any('output' in d for d in directions), "output direction not found")
    
    def test_clocking_signal_tracking(self):
        """[Golden] clocking 信号追踪
        
        RTL:
        module top(input clk, logic data, output logic valid);
            clocking cb @(posedge clk);
                input data;
                output valid;
            endclocking
            
            assign valid = data;
        endmodule
        
        预期:
        - data -> valid 驱动关系
        """
        source = '''module top(input clk, logic data, output logic valid);
    clocking cb @(posedge clk);
        input data;
        output valid;
    endclocking
    
    assign valid = data;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: data -> valid
        has_edge = any('data' in edge[0] and 'valid' in edge[1] for edge in edges)
        self.assertTrue(has_edge, f"data -> valid not found in {edges}")

if __name__ == '__main__':
    unittest.main()
