# test_sva.py - SVA 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
SVA 语法覆盖:
1. sequence 声明
2. property 声明
3. assert property
4. assume property
5. cover property
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestSVA(unittest.TestCase):
    """SVA 支持测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def _get_adapter(self, tree):
        class FP:
            def __init__(self, t): self.trees = t
        return PyslangAdapter(FP({'test.sv': source}))
    
    def test_sequence_declaration(self):
        """[Golden] sequence 声明
        
        RTL:
        module top(input clk, logic a, b);
            sequence s1;
                @(posedge clk) a ##1 b;
            endsequence
        endmodule
        
        预期:
        - SequenceDeclaration 存在
        - 名称为 s1
        """
        source = '''module top(input clk, logic a, b);
    sequence s1;
        @(posedge clk) a ##1 b;
    endsequence
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 SequenceDeclaration
        seq_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.SequenceDeclaration:
                seq_decl = m
                break
        
        self.assertIsNotNone(seq_decl, "SequenceDeclaration not found")
        self.assertEqual(str(seq_decl.name).strip(), 's1')
    
    def test_property_declaration(self):
        """[Golden] property 声明
        
        RTL:
        module top(input clk, logic a, b);
            property p1;
                @(posedge clk) disable iff (1'b0) a |-> b;
            endproperty
        endmodule
        
        预期:
        - PropertyDeclaration 存在
        - 名称为 p1
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) disable iff (1'b0) a |-> b;
    endproperty
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 PropertyDeclaration
        prop_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.PropertyDeclaration:
                prop_decl = m
                break
        
        self.assertIsNotNone(prop_decl, "PropertyDeclaration not found")
        self.assertEqual(str(prop_decl.name).strip(), 'p1')
    
    def test_assert_property(self):
        """[Golden] assert property
        
        RTL:
        module top(input clk, logic a, b);
            property p1;
                @(posedge clk) a |-> b;
            endproperty
            
            assert property (p1) else $error("fail");
        endmodule
        
        预期:
        - ConcurrentAssertionMember 存在
        - AssertPropertyStatement 存在
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    
    assert property (p1) else $error(\"fail\");
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 ConcurrentAssertionMember
        assertion = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.ConcurrentAssertionMember:
                assertion = m
                break
        
        self.assertIsNotNone(assertion, "ConcurrentAssertionMember not found")
        
        # 检查 statement
        stmt = assertion.statement
        self.assertEqual(stmt.kind, pyslang.SyntaxKind.AssertPropertyStatement)
    
    def test_assume_property(self):
        """[Golden] assume property
        
        RTL:
        module top(input clk, logic a, b);
            property p1;
                @(posedge clk) a |-> b;
            endproperty
            
            assume property (p1);
        endmodule
        
        预期:
        - AssumePropertyStatement 存在
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    
    assume property (p1);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 ConcurrentAssertionMember
        assertion = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.ConcurrentAssertionMember:
                assertion = m
                break
        
        self.assertIsNotNone(assertion, "ConcurrentAssertionMember not found")
        
        # 检查 statement
        stmt = assertion.statement
        self.assertEqual(stmt.kind, pyslang.SyntaxKind.AssumePropertyStatement)
    
    def test_cover_property(self):
        """[Golden] cover property
        
        RTL:
        module top(input clk, logic a, b);
            property p1;
                @(posedge clk) a |-> b;
            endproperty
            
            cover property (p1);
        endmodule
        
        预期:
        - CoverPropertyStatement 存在
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    
    cover property (p1);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 ConcurrentAssertionMember
        assertion = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.ConcurrentAssertionMember:
                assertion = m
                break
        
        self.assertIsNotNone(assertion, "ConcurrentAssertionMember not found")
        
        # 检查 statement
        stmt = assertion.statement
        self.assertEqual(stmt.kind, pyslang.SyntaxKind.CoverPropertyStatement)

if __name__ == '__main__':
    unittest.main()
