# test_class_method.py - Class 方法金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
# [iter_064 2026-08-29] 行为断言加强: 保留原有 AST 断言 (ClassMethodDeclaration/
# Prototype 节点提取), 补充 CLASS_PROPERTY 节点 + CONSTRAINS/类成员边断言 —
# 这是 class 方法域的真正行为金标准 (铁律13: 类→成员的语义约束).
"""
Class 方法语法:
1. function 函数定义
2. task 任务定义
3. extern function 原型声明
4. static function 静态方法
5. pure function 纯函数
6. const function 常量方法
7. virtual function 虚函数

工具缺口注意 (iter_064 探测):
- class 方法体内赋值 (task reset() 中 addr = 0; / function new() 中 addr = 8'h0;)
  当前实现**不生成内部 DRIVER 边** (方法体语句级提取限制, 类似 EXTRACTION_COVERAGE #20).
  但类作为整体与其成员间的 CONSTRAINS 边 (CLASS_PROPERTY 节点表征) 一定存在 —
  这是 class 域唯一可稳定断言的行为金标准.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.core.base import PyslangAdapter
from trace.unified_tracer import UnifiedTracer


def _build_graph(source):
    """构建 graph 的统一 helper"""
    tracer = UnifiedTracer(sources={'test.sv': source})
    tracer.build_graph()
    return tracer.get_graph()


class TestClassMethod(unittest.TestCase):
    """Class 方法测试"""

    def _get_classes(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        class FP:
            def __init__(self, t): self.trees = t
        adapter = PyslangAdapter(FP({'test.sv': tree}))
        return adapter.get_classes()

    def _get_class_methods(self, cls):
        """获取类方法 (ClassMethodDeclaration + ClassMethodPrototype)"""
        methods = []
        if cls is None:
            return methods

        if hasattr(cls, 'items'):
            items = cls.items
            if items and hasattr(items, '__iter__'):
                for item in items:
                    try:
                        kind = getattr(item, 'kind', None)
                        # ClassMethodDeclaration (function/task 定义)
                        # ClassMethodPrototype (extern/pure 声明)
                        if kind and ('ClassMethod' in str(kind)):
                            methods.append(item)
                    except (ValueError, AttributeError):
                        pass
        return methods

    def test_class_function(self):
        """[Golden] Class function 定义

        RTL:
        class packet;
            function bit [7:0] get_id();
                return 8'h0;
            endfunction
        endclass

        预期:
        - ClassMethodDeclaration 存在
        - 方法名为 get_id
        - class 节点自身存在
        """
        source = '''class packet;
    function bit [7:0] get_id();
        return 8'h0;
    endfunction
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)
        methods = self._get_class_methods(classes[0])
        self.assertGreaterEqual(len(methods), 1, "No methods found")

        # 检查方法名
        method = methods[0]
        decl = getattr(method, 'declaration', None)
        if decl:
            proto = getattr(decl, 'prototype', None)
            if proto:
                name = getattr(proto, 'name', None)
                name_str = name.value.strip() if hasattr(name, 'value') else str(name).strip()
                self.assertEqual(name_str, 'get_id')

        # [iter_064] 行为断言: class 节点 packet 在 graph 中存在
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet', nodes, "Class 定义节点 packet 应在 graph 中存在")

    def test_class_task(self):
        """[Golden] Class task 定义

        RTL:
        class packet;
            bit [7:0] addr;
            task reset();
                addr = 0;
            endtask
        endclass

        预期:
        - ClassMethodDeclaration (task) 存在
        - 行为金标准: class 节点 packet + 成员变量节点 packet.addr 存在;
          packet → packet.addr 边存在 (类管控其成员).
          (方法体内部 addr = 0 不生成 DRIVER 边 — 工具缺口, 见文件头注释.)
        """
        source = '''class packet;
    bit [7:0] addr;
    task reset();
        addr = 0;
    endtask
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)
        methods = self._get_class_methods(classes[0])
        self.assertGreaterEqual(len(methods), 1, "No methods found")

        # [iter_064] 行为断言: class + 成员变量节点 + 类成员边
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet', nodes, "class 节点 packet 应存在")
        self.assertIn('packet.addr', nodes,
                      "Class 成员变量 addr 应作为 CLASS_PROPERTY 节点存在")
        # 类管控其成员的边 (CONTAINS_MEMBER 或 CONSTRAINS, 实际是 CONSTRAINS)
        edge = graph.get_edge('packet', 'packet.addr')
        self.assertIsNotNone(edge, "class → 成员 应生成 CONSTRAINS/CONTAINS_MEMBER 边")

    def test_class_new_constructor(self):
        """[Golden] Class new 构造函数

        RTL:
        class packet;
            bit [7:0] addr;
            function new();
                addr = 8'h0;
            endfunction
        endclass

        预期:
        - new 构造函数存在
        - 行为金标准: 构造函数体的 addr = 8'h0 不生成内部 DRIVER
          边 (工具缺口), 但 class → addr 成员边总存在.
        """
        source = '''class packet;
    bit [7:0] addr;
    function new();
        addr = 8'h0;
    endfunction
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)
        methods = self._get_class_methods(classes[0])
        self.assertGreaterEqual(len(methods), 1, "No methods found")

        # [iter_064] 行为断言: class + 成员节点 + 类成员边
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet', nodes)
        self.assertIn('packet.addr', nodes,
                      "new() 函数体内的 addr 应作为 class 成员属性被提取")
        edge = graph.get_edge('packet', 'packet.addr')
        self.assertIsNotNone(edge, "new() 构造的成员变量应有 class → addr 边")

    def test_class_extern_function(self):
        """[Golden] extern function 原型声明

        RTL:
        class packet;
            extern function void print();
        endclass

        预期:
        - ClassMethodPrototype 存在
        - 行为金标准: class 节点 packet 存在; extern 原型本身不引入新成员
          属性节点 (没成员变量声明).
        """
        source = '''class packet;
    extern function void print();
endclass
module top();
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        class FP:
            def __init__(self, t): self.trees = t
        adapter = PyslangAdapter(FP({'test.sv': tree}))
        classes = adapter.get_classes()

        self.assertEqual(len(classes), 1)
        members = adapter.get_class_members(classes[0])
        # extern 方法是 ClassMethodPrototype，也包含在 members 中
        self.assertGreaterEqual(len(members), 1,
            f"No members found, got {len(members)}")

        # [iter_064] 行为断言: class 节点存在
        # extern 原型声明**不**生成内部行为边 (只是声明, 不像 class 成员变量
        # 那样存在 CONTAINS_MEMBER 关系). 保留此断言以锁定现状.
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet', nodes, "extern function 原型声明的 class 节点应存在")

    def test_class_static_function(self):
        """[Golden] static function 静态方法

        RTL:
        class packet;
            static function void init();
        endclass

        预期:
        - ClassMethodDeclaration 存在
        - 行为金标准: class 节点 packet 存在.
          (pyslang 对 static 声明有 MemberImplNotFound 警告, 但 class 节点
          仍被提取.)
        """
        source = '''class packet;
    static function void init();
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)
        methods = self._get_class_methods(classes[0])
        self.assertGreaterEqual(len(methods), 1)

        # [iter_064] 行为断言: class 节点存在
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet', nodes, "static function 声明的 class 节点应存在")


if __name__ == '__main__':
    unittest.main()
