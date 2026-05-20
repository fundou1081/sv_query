# test_dpi.py - DPI 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
DPI 语法覆盖:
1. import \"DPI-C\" function
2. import \"DPI-C\" task
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestDPI(unittest.TestCase):
    """DPI 支持测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def _get_adapter(self, tree):
        class FP:
            def __init__(self, t): self.trees = t
        return PyslangAdapter(FP({'test.sv': source}))
    
    def test_dpi_function_import(self):
        """[Golden] import \"DPI-C\" function
        
        RTL:
        module top;
            import \"DPI-C\" function int add(input int a, input int b);
        endmodule
        
        预期:
        - DPIImport 存在
        - 方法名为 add
        """
        source = '''module top;
    import \"DPI-C\" function int add(input int a, input int b);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 DPIImport
        dpi_import = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.DPIImport:
                dpi_import = m
                break
        
        self.assertIsNotNone(dpi_import, "DPIImport not found")
        
        # 检查方法名
        method = dpi_import.method
        self.assertEqual(str(method.name).strip(), 'add')
    
    def test_dpi_task_import(self):
        """[Golden] import \"DPI-C\" task
        
        RTL:
        module top;
            import \"DPI-C\" task reset();
        endmodule
        
        预期:
        - DPIImport 存在
        - 方法名为 reset
        """
        source = '''module top;
    import \"DPI-C\" task reset();
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 DPIImport
        dpi_import = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.DPIImport:
                dpi_import = m
                break
        
        self.assertIsNotNone(dpi_import, "DPIImport not found")
        
        # 检查方法名
        method = dpi_import.method
        self.assertEqual(str(method.name).strip(), 'reset')
    
    def test_dpi_signal_tracking(self):
        """[Golden] DPI 信号追踪
        
        RTL:
        module top;
            import \"DPI-C\" function int add(input int a, input int b);
            
            int result;
            assign result = add(1, 2);
        endmodule
        
        预期:
        - result 节点存在
        """
        source = '''module top;
    import \"DPI-C\" function int add(input int a, input int b);
    
    int result;
    assign result = add(1, 2);
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        
        # 验证: result 节点存在
        has_result = any('result' in n for n in nodes)
        self.assertTrue(has_result, f"result not found in {nodes}")

if __name__ == '__main__':
    unittest.main()
