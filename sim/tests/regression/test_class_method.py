# test_class_method.py - Class 方法金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Class 方法语法:
1. function 函数定义
2. task 任务定义
3. extern function 原型声明
4. static function 静态方法
5. pure function 纯函数
6. const function 常量方法
7. virtual function 虚函数
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

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

    def test_class_task(self):
        """[Golden] Class task 定义

        RTL:
        class packet;
            task reset();
                addr = 0;
            endtask
        endclass

        预期:
        - ClassMethodDeclaration (task) 存在
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

    def test_class_new_constructor(self):
        """[Golden] Class new 构造函数

        RTL:
        class packet;
            function new();
                addr = 8'h0;
            endfunction
        endclass

        预期:
        - new 构造函数存在
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

    def test_class_extern_function(self):
        """[Golden] extern function 原型声明

        RTL:
        class packet;
            extern function void print();
        endclass

        预期:
        - ClassMethodPrototype 存在
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

    def test_class_static_function(self):
        """[Golden] static function 静态方法

        RTL:
        class packet;
            static function void init();
        endclass

        预期:
        - ClassMethodDeclaration 存在
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

if __name__ == '__main__':
    unittest.main()
