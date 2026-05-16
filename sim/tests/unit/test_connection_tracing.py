#==============================================================================
# test_connection_tracing.py - 连接追踪测试
#==============================================================================
# 测试目的: 验证 sv_query 正确提取实例端口连接
#
# 金标准测试原则 (铁律13-20):
# - 先推导金标准，从 RTL 人工推导预期结果
# - RTL 必须来自真实场景
# - 使用 Verilator 验证语法正确
# - 强断言验证具体行为

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.core.base import PyslangAdapter


class TestConnectionTracing(unittest.TestCase):
    """连接追踪测试"""
    
    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        return FakeParser(tree)
    
    def _verify_rtl(self, source, name="RTL"):
        """验证 RTL 语法正确"""
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sv', delete=False) as f:
            f.write(source)
            f.flush()
            tmp = f.name
        try:
            result = subprocess.run(
                ["verilator", "--lint-only", "-sv", tmp],
                capture_output=True, text=True, timeout=30
            )
            errors = [l for l in result.stderr.split('\n') if '%Error' in l]
            self.assertEqual(len(errors), 0, f"{name} - Verilator errors: {errors}")
        finally:
            os.unlink(tmp)
    
    #============================================================================
    # 测试场景 1: 基本命名连接
    #============================================================================
    def test_named_connection(self):
        """测试: 命名端口连接
        
        金标准:
        - 实例有 4 个连接: (.clk(clk), .rst(rst), .data_in(data), .out(out))
        """
        source = '''
module top(input wire clk, input wire rst, input [7:0] data, output [7:0] out);
    sub inst(.clk(clk), .rst(rst), .data_in(data), .out(out));
endmodule

module sub(input clk, input rst, input [7:0] data_in, output [7:0] out);
    assign out = data_in;
endmodule
'''
        self._verify_rtl(source, "named_connection")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        # 获取所有实例
        all_instances = adapter.get_module_instances(parser.trees)
        self.assertEqual(len(all_instances), 1, f"应有 1 个实例，实际有 {len(all_instances)}")
        
        # 获取连接
        conns = adapter.get_instance_connection(all_instances[0])
        
        # 金标准: 4 个连接
        self.assertEqual(len(conns), 4, f"应有 4 个连接，实际有 {len(conns)}")
        
        # 金标准: 连接内容
        conn_dict = dict(conns)
        self.assertEqual(conn_dict['clk'], 'clk')
        self.assertEqual(conn_dict['rst'], 'rst')
        self.assertEqual(conn_dict['data_in'], 'data')
        self.assertEqual(conn_dict['out'], 'out')
    
    #============================================================================
    # 测试场景 2: 顺序连接 (positional)
    #============================================================================
    def test_positional_connection(self):
        """测试: 顺序端口连接
        
        金标准:
        - 实例有 4 个顺序连接
        """
        source = '''
module top(input wire clk, input wire rst, input [7:0] data, output [7:0] out);
    sub inst(clk, rst, data, out);
endmodule

module sub(input clk, input rst, input [7:0] data_in, output [7:0] out);
    assign out = data_in;
endmodule
'''
        self._verify_rtl(source, "positional_connection")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        all_instances = adapter.get_module_instances(parser.trees)
        conns = adapter.get_instance_connection(all_instances[0])
        
        # 金标准: 4 个连接
        self.assertEqual(len(conns), 4, f"应有 4 个连接，实际有 {len(conns)}")
        
        # 金标准: 顺序连接用 _pos_ 前缀
        conn_dict = dict(conns)
        self.assertEqual(conn_dict['_pos_0'], 'clk')
        self.assertEqual(conn_dict['_pos_1'], 'rst')
        self.assertEqual(conn_dict['_pos_2'], 'data')
        self.assertEqual(conn_dict['_pos_3'], 'out')
    
    #============================================================================
    # 测试场景 3: 仅命名连接 (不允许混用)
    #============================================================================
    def test_named_only_connection(self):
        """测试: 仅命名端口连接
        
        金标准:
        - 实例有 3 个命名连接
        
        注: SystemVerilog 不允许混用命名和顺序连接
        """
        source = '''
module top(input wire clk, input [7:0] data, output [7:0] out);
    sub inst(.clk(clk), .data_in(data), .out(out));
endmodule

module sub(input clk, input [7:0] data_in, output [7:0] out);
endmodule
'''
        self._verify_rtl(source, "named_only_connection")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        all_instances = adapter.get_module_instances(parser.trees)
        conns = adapter.get_instance_connection(all_instances[0])
        
        # 金标准: 3 个连接
        self.assertEqual(len(conns), 3, f"应有 3 个连接，实际有 {len(conns)}")
        
        conn_dict = dict(conns)
        self.assertEqual(conn_dict['clk'], 'clk')
        self.assertEqual(conn_dict['data_in'], 'data')
        self.assertEqual(conn_dict['out'], 'out')
    
    #============================================================================
    # 测试场景 4: 无连接
    #============================================================================
    def test_no_connection(self):
        """测试: 无端口连接的实例
        
        金标准:
        - 实例有 0 个连接
        """
        source = '''
module top();
    sub inst();
endmodule

module sub();
endmodule
'''
        self._verify_rtl(source, "no_connection")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        all_instances = adapter.get_module_instances(parser.trees)
        conns = adapter.get_instance_connection(all_instances[0])
        
        # 金标准: 0 个连接
        self.assertEqual(len(conns), 0, f"应有 0 个连接，实际有 {len(conns)}")
    
    #============================================================================
    # 测试场景 5: 多实例
    #============================================================================
    def test_multiple_instances(self):
        """测试: 多个实例的连接
        
        金标准:
        - 模块 top 有 2 个实例
        """
        source = '''
module top(input wire clk);
    sub inst1(.clk(clk));
    sub inst2(.clk(clk));
endmodule

module sub(input clk);
endmodule
'''
        self._verify_rtl(source, "multiple_instances")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        # 获取 top 模块的实例 (parent is ModuleDeclaration with name 'top')
        all_instances = adapter.get_module_instances(parser.trees)
        
        # 过滤 top 模块的实例
        top_instances = []
        for inst in all_instances:
            parent = inst.parent
            while parent:
                if hasattr(parent, 'kind') and parent.kind == pyslang.SyntaxKind.ModuleDeclaration:
                    if hasattr(parent, 'header') and parent.header and hasattr(parent.header, 'name'):
                        name = parent.header.name
                        mn = name.value if hasattr(name, 'value') else str(name)
                        if mn == 'top':
                            top_instances.append(inst)
                    break
                parent = getattr(parent, 'parent', None)
        
        self.assertEqual(len(top_instances), 2, f"top 模块应有 2 个实例，实际有 {len(top_instances)}")
        
        # 验证第一个实例的连接
        conns = adapter.get_instance_connection(top_instances[0])
        self.assertEqual(len(conns), 1, f"inst1 应有 1 个连接，实际有 {len(conns)}")
        self.assertEqual(conns[0][0], 'clk')
        self.assertEqual(conns[0][1], 'clk')


if __name__ == '__main__':
    unittest.main()