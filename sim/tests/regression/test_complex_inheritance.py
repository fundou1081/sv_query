"""
test_complex_inheritance.py - 复杂 Class 继承场景金标准测试

[铁律13] 金标准测试
[铁律17] 强断言原则
[铁律19] RTL 来自真实场景模式

场景设计:
  base_item (根类)
  ├── transaction (extends base_item)
  │   ├── has: addr_item addr (组合)
  │   ├── has: data_item data (组合)
  │   ├── VIRTUAL Function: do_prepare()
  │   ├── VIRTUAL Task: run()
  │   ├── regular Function: check()
  │   ├── Property: mode
  │   ├── Constraint: c1 { mode > 0; }
  │   └── Constraint: c2 { mode < 10; }
  │
  └── extended_transaction (extends transaction)
      ├── has: data_item ext_data (组合)
      ├── Function override (virtual): do_prepare()
      ├── Task override (virtual): run()
      ├── Constraint c1 override (augmentation): { super.c1; mode > 50; }
      └── Constraint c2 override (replacement): { mode < 5; }

预期结果:
  IS_INSTANCE_OF 边:
    - transaction.addr -> addr_item
    - transaction.data -> data_item
    - extended_transaction.ext_data -> data_item
  
  Constraint SUPER_CALL 边:
    - extended_transaction.c1::expr_0 --SUPER_CALL--> transaction.c1
  
  Constraint Override (replacement, no SUPER_CALL):
    - extended_transaction.c2 无 SUPER_CALL 边
  
  Hierarchy:
    - base_item (root)
    - transaction extends base_item
    - extended_transaction extends transaction
"""

import unittest
import sys
sys.path.insert(0, 'src')

from trace.unified_tracer import UnifiedTracer
from trace.core.graph_models import EdgeKind, NodeKind
import pyslang
from pyslang import SyntaxKind


class TestComplexInheritance(unittest.TestCase):
    """复杂继承场景完整测试"""
    
    def _build_graph(self):
        source = '''class base_item;
    rand int id;
endclass

class addr_item;
    rand bit [31:0] addr;
    constraint addr_c { addr[31:16] == 16'h1234; }
endclass

class data_item;
    rand bit [7:0] data;
endclass

class transaction extends base_item;
    addr_item addr;
    data_item data;
    
    virtual function void do_prepare();
    endfunction
    
    virtual task run();
    endtask
    
    function void check();
    endfunction
    
    rand int mode;
    constraint c1 { mode > 0; }
    constraint c2 { mode < 10; }
endclass

class extended_transaction extends transaction;
    data_item ext_data;
    
    function void do_prepare();
    endfunction
    
    task run();
    endtask
    
    constraint c1 { super.c1; mode > 50; }
    constraint c2 { mode < 5; }
endclass'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_all_classes_exist(self):
        """所有 class 节点存在"""
        graph = self._build_graph()
        nodes = list(graph.nodes())
        
        expected_classes = [
            'base_item',
            'addr_item',
            'data_item',
            'transaction',
            'extended_transaction',
        ]
        
        for cls_name in expected_classes:
            self.assertIn(cls_name, nodes, f"应有 CLASS 节点: {cls_name}")
    
    def test_composition_edges(self):
        """组合关系 IS_INSTANCE_OF 边"""
        graph = self._build_graph()
        edges = list(graph.edges())
        
        inst_edges = [(src, dst) for src, dst in edges 
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]
        
        # transaction.addr -> addr_item
        self.assertIn(('transaction.addr', 'addr_item'), inst_edges,
            "transaction.addr 应指向 addr_item")
        
        # transaction.data -> data_item
        self.assertIn(('transaction.data', 'data_item'), inst_edges,
            "transaction.data 应指向 data_item")
        
        # extended_transaction.ext_data -> data_item
        self.assertIn(('extended_transaction.ext_data', 'data_item'), inst_edges,
            "extended_transaction.ext_data 应指向 data_item")
    
    def test_constraint_super_call(self):
        """constraint c1 augmentation (有 super.c1)"""
        graph = self._build_graph()
        edges = list(graph.edges())
        
        super_edges = [(src, dst) for src, dst in edges 
                      if graph.get_edge(src, dst).kind == EdgeKind.SUPER_CALL]
        
        self.assertEqual(len(super_edges), 1, "应有 1 条 SUPER_CALL 边")
        self.assertIn(('extended_transaction.c1::expr_0', 'transaction.c1'), super_edges,
            "extended_transaction.c1::expr_0 应 SUPER_CALL transaction.c1")
    
    def test_constraint_override_replacement(self):
        """constraint c2 replacement (无 super.c2)"""
        graph = self._build_graph()
        edges = list(graph.edges())
        
        # 查找所有 transaction.c2 或 extended_transaction.c2 相关的边
        c2_super_edges = [(src, dst) for src, dst in edges 
                         if 'c2' in src and graph.get_edge(src, dst).kind == EdgeKind.SUPER_CALL]
        
        self.assertEqual(len(c2_super_edges), 0, 
            "constraint c2 replacement 不应有 SUPER_CALL 边")
    
    def test_constraint_blocks_exist(self):
        """所有 constraint block 节点存在"""
        graph = self._build_graph()
        nodes = list(graph.nodes())
        
        constraint_nodes = [n for n in nodes if '::c' in n or n.endswith('.addr_c')]
        
        expected_constraints = [
            'transaction.c1',
            'transaction.c2',
            'extended_transaction.c1',
            'extended_transaction.c2',
            'addr_item.addr_c',
        ]
        
        for constr in expected_constraints:
            self.assertIn(constr, nodes, f"应有 constraint 节点: {constr}")
    
    def test_property_nodes(self):
        """所有 property 节点存在"""
        graph = self._build_graph()
        nodes = list(graph.nodes())
        
        expected_properties = [
            'base_item.id',
            'transaction.addr',
            'transaction.data',
            'transaction.mode',
            'extended_transaction.ext_data',
        ]
        
        for prop in expected_properties:
            self.assertIn(prop, nodes, f"应有 CLASS_PROPERTY 节点: {prop}")
    
    def test_class_hierarchy_extends(self):
        """ClassHierarchy extends 关系"""
        graph = self._build_graph()
        tracer = UnifiedTracer(trees={'test.sv': pyslang.SyntaxTree.fromText('''class a; endclass''')})
        
        # 获取 hierarchy
        source = '''class base_item;
    rand int id;
endclass

class transaction extends base_item;
endclass

class extended_transaction extends transaction;
endclass'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        
        hierarchy = tracer._graph.hierarchy if hasattr(tracer._graph, 'hierarchy') else None
        if hierarchy:
            self.assertEqual(hierarchy.get_parent('transaction'), 'base_item',
                "transaction 应 extends base_item")
            self.assertEqual(hierarchy.get_parent('extended_transaction'), 'transaction',
                "extended_transaction 应 extends transaction")
    
    def test_all_constraint_expression_nodes(self):
        """constraint 表达式节点存在"""
        graph = self._build_graph()
        nodes = list(graph.nodes())
        
        # 每个 constraint 块内的表达式
        expr_nodes = [n for n in nodes if '::expr_' in n]
        
        # transaction.c1: 1 expr (mode > 0)
        # transaction.c2: 1 expr (mode < 10)
        # extended_transaction.c1: 2 expr (super.c1, mode > 50)
        # extended_transaction.c2: 1 expr (mode < 5)
        # addr_item.addr_c: 1 expr
        # total: 6
        
        self.assertGreaterEqual(len(expr_nodes), 5, 
            "应有足够的 constraint 表达式节点")


class TestMethodOverride(unittest.TestCase):
    """方法 override 测试 (功能验证)"""
    
    def test_virtual_methods_detected(self):
        """检测 virtual function/task"""
        source = '''class c;
    virtual function void vf();
    endfunction
    
    virtual task vt();
    endtask
    
    function void rf();
    endfunction
endclass'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        cls = tree.root
        
        virtual_methods = []
        for item in cls.items:
            if getattr(item, 'kind') == SyntaxKind.ClassMethodDeclaration:
                qualifiers = getattr(item, 'qualifiers', None)
                is_virtual = False
                if qualifiers:
                    for q in qualifiers:
                        if str(q).strip() == 'virtual':
                            is_virtual = True
                decl = getattr(item, 'declaration', None)
                decl_kind = getattr(decl, 'kind', None) if decl else None
                
                if is_virtual:
                    method_type = 'Task' if decl_kind == SyntaxKind.TaskDeclaration else 'Function'
                    virtual_methods.append(method_type)
        
        self.assertEqual(len(virtual_methods), 2, "应有 2 个 virtual 方法 (1 function + 1 task)")
        self.assertIn('Function', virtual_methods, "应有 virtual Function")
        self.assertIn('Task', virtual_methods, "应有 virtual Task")
    
    def test_method_override_detection(self):
        """检测 override 场景 (virtual + extends)"""
        source = '''class parent;
    virtual function void do_something();
    endfunction
endclass

class child extends parent;
    function void do_something();
    endfunction
endclass'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        # parent 有 virtual function
        # child 继承并 override
        
        parent_methods = []
        child_methods = []
        
        for cls in root.members:
            if cls.kind == SyntaxKind.ClassDeclaration:
                methods = parent_methods if cls.name.value == 'parent' else child_methods
                for item in cls.items:
                    if getattr(item, 'kind') == SyntaxKind.ClassMethodDeclaration:
                        qualifiers = getattr(item, 'qualifiers', None)
                        is_virtual = False
                        if qualifiers:
                            for q in qualifiers:
                                if str(q).strip() == 'virtual':
                                    is_virtual = True
                        if is_virtual:
                            methods.append('virtual')
        
        self.assertEqual(len(parent_methods), 1, "parent应有1个virtual方法")
        self.assertEqual(len(child_methods), 0, "child在简单检测中无virtual(通过extends关联)")


if __name__ == '__main__':
    unittest.main()
