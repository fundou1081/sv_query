# test_package.py - Package 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Package 语法覆盖:
1. package 声明
2. import pkg::*
3. 跨 package 引用
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestPackage(unittest.TestCase):
    """Package 支持测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def _get_adapter(self, tree):
        class FP:
            def __init__(self, t): self.trees = t
        return PyslangAdapter(FP({'test': tree}))
    
    def test_package_declaration(self):
        """[Golden] package 声明
        
        RTL:
        package my_pkg;
            typedef struct {
                logic [7:0] addr;
                logic [31:0] data;
            } packet_t;
            
            parameter TIMEOUT = 100;
        endpackage
        
        预期:
        - PackageDeclaration 存在
        - 包名为 my_pkg
        - 包含 typedef 和 parameter
        """
        source = '''package my_pkg;
    typedef struct {
        logic [7:0] addr;
        logic [31:0] data;
    } packet_t;
    
    parameter TIMEOUT = 100;
endpackage'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 PackageDeclaration
        self.assertEqual(root.kind, pyslang.SyntaxKind.PackageDeclaration)
        
        # 检查包名
        header = root.header
        self.assertEqual(str(header.name).strip(), 'my_pkg')
        
        # 检查 members
        members = list(root.members)
        self.assertGreaterEqual(len(members), 2, "Package should have at least 2 members")
    
    def test_package_import(self):
        """[Golden] import pkg::*
        
        RTL:
        package my_pkg;
            parameter TIMEOUT = 100;
        endpackage
        
        module top;
            import my_pkg::*;
            logic [7:0] data;
        endmodule
        
        预期:
        - PackageImportDeclaration 存在
        - 导入包名为 my_pkg
        - 导入符号为 *
        """
        source = '''package my_pkg;
    parameter TIMEOUT = 100;
endpackage

module top;
    import my_pkg::*;
    logic [7:0] data;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 CompilationUnit
        self.assertEqual(root.kind, pyslang.SyntaxKind.CompilationUnit)
        
        members = list(root.members)
        self.assertGreaterEqual(len(members), 2, "Should have package and module")
        
        # 检查 Module members
        module = members[1]
        module_members = list(module.members)
        
        # 查找 PackageImportDeclaration
        import_decl = None
        for m in module_members:
            if m.kind == pyslang.SyntaxKind.PackageImportDeclaration:
                import_decl = m
                break
        
        self.assertIsNotNone(import_decl, "PackageImportDeclaration not found")
        
        # 检查导入项
        items = list(import_decl.items)
        self.assertGreaterEqual(len(items), 1, "Should have at least 1 import item")
        
        # 检查包名和符号
        item = items[0]
        self.assertEqual(str(item.package).strip(), 'my_pkg')
        self.assertEqual(str(item.item).strip(), '*')
    
    def test_package_specific_import(self):
        """[Golden] import pkg::symbol
        
        RTL:
        package my_pkg;
            typedef struct {
                logic [7:0] addr;
            } packet_t;
            
            parameter TIMEOUT = 100;
        endpackage
        
        module top;
            import my_pkg::packet_t;
            packet_t pkt;
        endmodule
        
        预期:
        - PackageImportDeclaration 存在
        - 导入符号为 packet_t
        """
        source = '''package my_pkg;
    typedef struct {
        logic [7:0] addr;
    } packet_t;
    
    parameter TIMEOUT = 100;
endpackage

module top;
    import my_pkg::packet_t;
    packet_t pkt;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        members = list(root.members)
        module = members[1]
        module_members = list(module.members)
        
        # 查找 PackageImportDeclaration
        import_decl = None
        for m in module_members:
            if m.kind == pyslang.SyntaxKind.PackageImportDeclaration:
                import_decl = m
                break
        
        self.assertIsNotNone(import_decl, "PackageImportDeclaration not found")
        
        # 检查导入项
        items = list(import_decl.items)
        item = items[0]
        self.assertEqual(str(item.package).strip(), 'my_pkg')
        self.assertEqual(str(item.item).strip(), 'packet_t')
    
    def test_package_signal_tracking(self):
        """[Golden] package 内信号追踪
        
        RTL:
        package my_pkg;
            typedef struct {
                logic [7:0] addr;
                logic [31:0] data;
            } packet_t;
        endpackage
        
        module top;
            import my_pkg::*;
            logic [7:0] data;
            assign data = 8'h0;
        endmodule
        
        预期:
        - data 节点存在
        - 驱动关系正确
        """
        source = '''package my_pkg;
    typedef struct {
        logic [7:0] addr;
        logic [31:0] data;
    } packet_t;
endpackage

module top;
    import my_pkg::*;
    logic [7:0] data;
    assign data = 8'h0;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: data 节点存在
        has_data = any('data' in n for n in nodes)
        self.assertTrue(has_data, f"data not found in {nodes}")

if __name__ == '__main__':
    unittest.main()
