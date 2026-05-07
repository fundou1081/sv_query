# test_typedef.py - Typedef 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Typedef 语法覆盖:
1. typedef enum
2. typedef struct
3. typedef union
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestTypedef(unittest.TestCase):
    """Typedef 支持测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def _get_adapter(self, tree):
        class FP:
            def __init__(self, t): self.trees = t
        return PyslangAdapter(FP({'test': tree}))
    
    def test_typedef_enum(self):
        """[Golden] typedef enum
        
        RTL:
        typedef enum {IDLE, RUN, STOP} state_t;
        
        预期:
        - TypedefDeclaration 存在
        - 名称为 state_t
        - 类型为 EnumType
        """
        source = '''module top;
    typedef enum {IDLE, RUN, STOP} state_t;
    state_t state;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 TypedefDeclaration
        typedef_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.TypedefDeclaration:
                typedef_decl = m
                break
        
        self.assertIsNotNone(typedef_decl, "TypedefDeclaration not found")
        self.assertEqual(str(typedef_decl.name).strip(), 'state_t')
        
        # 检查类型
        self.assertEqual(typedef_decl.type.kind, pyslang.SyntaxKind.EnumType)
    
    def test_typedef_struct(self):
        """[Golden] typedef struct
        
        RTL:
        typedef struct {
            logic [7:0] addr;
            logic [31:0] data;
        } packet_t;
        
        预期:
        - TypedefDeclaration 存在
        - 名称为 packet_t
        - 类型为 StructType
        """
        source = '''module top;
    typedef struct {
        logic [7:0] addr;
        logic [31:0] data;
    } packet_t;
    packet_t pkt;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 TypedefDeclaration
        typedef_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.TypedefDeclaration:
                typedef_decl = m
                break
        
        self.assertIsNotNone(typedef_decl, "TypedefDeclaration not found")
        self.assertEqual(str(typedef_decl.name).strip(), 'packet_t')
        
        # 检查类型
        self.assertEqual(typedef_decl.type.kind, pyslang.SyntaxKind.StructType)
    
    def test_typedef_union(self):
        """[Golden] typedef union
        
        RTL:
        typedef union {
            logic [31:0] word;
            logic [7:0] bytes[4];
        } mem_t;
        
        预期:
        - TypedefDeclaration 存在
        - 名称为 mem_t
        - 类型为 UnionType
        """
        source = '''module top;
    typedef union {
        logic [31:0] word;
        logic [7:0] bytes[4];
    } mem_t;
    mem_t mem;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # 检查 Module members
        members = list(root.members)
        
        # 查找 TypedefDeclaration
        typedef_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.TypedefDeclaration:
                typedef_decl = m
                break
        
        self.assertIsNotNone(typedef_decl, "TypedefDeclaration not found")
        self.assertEqual(str(typedef_decl.name).strip(), 'mem_t')
        
        # 检查类型
        self.assertEqual(typedef_decl.type.kind, pyslang.SyntaxKind.UnionType)
    
    def test_typedef_signal_tracking(self):
        """[Golden] typedef 信号追踪
        
        RTL:
        typedef struct {
            logic [7:0] addr;
            logic [31:0] data;
        } packet_t;
        
        module top;
            packet_t pkt;
            assign pkt.addr = 8'h0;
        endmodule
        
        预期:
        - pkt.addr 节点存在
        """
        source = '''typedef struct {
    logic [7:0] addr;
    logic [31:0] data;
} packet_t;

module top;
    packet_t pkt;
    assign pkt.addr = 8'h0;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        
        # 验证: pkt.addr 节点存在
        has_pkt_addr = any('pkt.addr' in n for n in nodes)
        self.assertTrue(has_pkt_addr, f"pkt.addr not found in {nodes}")

if __name__ == '__main__':
    unittest.main()
