#==============================================================================
# test_comment_handling.py - 注释处理测试
#==============================================================================
# 测试目的: 验证 sv_query 正确处理 SV 中的注释干扰
#
# 问题场景:
# 1. 端口前的注释被当作端口名/方向的一部分
# 2. 实例名前的注释导致实例名解析为 "?"
#
# 金标准测试原则 (铁律13-20):
# - 先推导金标准，从 RTL 人工推导预期结果
# - RTL 必须来自真实场景
# - 使用 Verilator + Verible 双重验证
# - 强断言验证具体行为

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.core.base import PyslangAdapter


class TestCommentHandling(unittest.TestCase):
    """注释处理测试"""
    
    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        return PyslangAdapter(FakeParser(tree))
    
    def _verify_rtl(self, source, name="RTL"):
        """验证 RTL 语法正确"""
        import subprocess
        import tempfile
        
        # Verilator 验证
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
        
        # Verible 验证
        verible_bin = os.path.expanduser("~/my_daily_proj/verible-v0.0-4053-g89d4d98a-macOS/bin/verible-verilog-lint")
        if os.path.exists(verible_bin):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sv', delete=False) as f:
                f.write(source)
                f.flush()
                tmp = f.name
            try:
                result = subprocess.run([verible_bin, tmp], capture_output=True, text=True, timeout=30)
                output = result.stderr + result.stdout
                syntax_errors = [l for l in output.split('\n') if 'syntax error' in l.lower()]
                self.assertEqual(len(syntax_errors), 0, f"{name} - Verible syntax errors: {syntax_errors}")
            finally:
                os.unlink(tmp)
    
    #============================================================================
    # 测试场景 1: 端口前的行注释干扰 direction
    #============================================================================
    def test_port_direction_with_leading_comment(self):
        """测试: 行注释在端口前，direction 应正确提取
        
        金标准:
        - 模块有 3 个端口: clk (input), rst (input), data (output)
        - clk 的 direction 应为 'input'，不应包含注释
        """
        source = '''
module test_top(
    // clock signal
    input wire clk,
    input wire rst,
    // data output
    output reg [7:0] data
);
endmodule
'''
        self._verify_rtl(source, "port_direction_with_leading_comment")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        self.assertEqual(len(modules), 1)
        
        module = modules[0]
        ports = adapter.get_port_declarations(module)
        
        # 金标准: 3 个端口
        self.assertEqual(len(ports), 3, f"应有 3 个端口，实际有 {len(ports)} 个")
        
        # 金标准: 每个端口的 direction 不应包含注释
        for port in ports:
            name, direction = adapter.get_port_name_and_direction(port)
            self.assertIsNotNone(name, f"端口 {port} 的 name 为 None")
            
            # 强断言: direction 不应包含 "//" 注释
            self.assertNotIn('//', direction, 
                f"端口 {name} 的 direction 包含注释: '{direction}'")
            
            # 强断言: direction 应该是 'input' 或 'output'
            direction_clean = direction.strip()
            self.assertIn(direction_clean, ['input', 'output'],
                f"端口 {name} 的 direction 应为 input/output，实际: '{direction_clean}'")
    
    def test_port_direction_with_trailing_comment(self):
        """测试: 行注释在端口后 (同一行)，direction 应正确
        
        金标准:
        - 模块有 2 个端口: clk 和 rst
        - rst 同行有 "reset signal" 注释，direction 应为 'input'
        """
        source = '''
module test_top(
    input wire clk,
    input wire rst // reset signal
);
endmodule
'''
        self._verify_rtl(source, "port_direction_with_trailing_comment")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        ports = adapter.get_port_declarations(modules[0])
        
        self.assertEqual(len(ports), 2)
        
        # 验证每个端口的 direction 正确
        for port in ports:
            name, direction = adapter.get_port_name_and_direction(port)
            direction_clean = direction.strip()
            self.assertIn(direction_clean, ['input', 'output', 'inout'],
                f"端口 {name} 的 direction '{direction_clean}' 应为 input/output/inout")
    
    #============================================================================
    # 测试场景 2: 端口前有多行注释
    #============================================================================
    def test_port_direction_with_multiline_comment(self):
        """测试: 多行注释在端口前
        
        金标准:
        - 模块有 1 个端口: clk (input)
        - direction 应为 'input'，不含任何注释内容
        """
        source = '''
module test_top(
    /* 
     * Multi-line comment
     * spanning multiple lines
     */
    input wire clk
);
endmodule
'''
        self._verify_rtl(source, "port_direction_with_multiline_comment")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        ports = adapter.get_port_declarations(modules[0])
        
        self.assertEqual(len(ports), 1, f"应有 1 个端口，实际有 {len(ports)} 个")
        
        name, direction = adapter.get_port_name_and_direction(ports[0])
        
        # 强断言: name 应为 'clk'
        self.assertEqual(name, 'clk', f"端口名应为 'clk'，实际为 '{name}'")
        
        # 强断言: direction 应为 'input'
        self.assertEqual(direction.strip(), 'input',
            f"direction 应为 'input'，实际为 '{direction}'")
    
    #============================================================================
    # 测试场景 3: 实例名前有注释
    #============================================================================
    def test_instance_name_with_single_line_comment(self):
        """测试: 单行注释在实例名前
        
        金标准:
        - 模块实例化了 1 个模块: inst_fsm
        - 实例名称应为 'inst_fsm'，不应为 '?'
        """
        source = '''
module test_top(input wire clk);
    // FSM instance
    state_machine inst_fsm (.clk(clk));
endmodule

module state_machine(input wire clk);
endmodule
'''
        self._verify_rtl(source, "instance_name_with_single_line_comment")
        
        adapter = self._make_adapter(source)
        
        # 使用 adapter.get_module_instances (需要 parser.trees)
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        parser = FakeParser(tree)
        
        # 获取所有实例
        all_instances = adapter.get_module_instances(parser.trees)
        
        # 过滤出 test_top 模块中的实例 (instances 在 members 中)
        instances = []
        for inst in all_instances:
            # 检查 instance 是否在 test_top 中
            parent = inst.parent
            while parent:
                if hasattr(parent, 'kind') and str(parent.kind) == 'SyntaxKind.ModuleDeclaration':
                    if hasattr(parent, 'header') and parent.header and hasattr(parent.header, 'name'):
                        name = parent.header.name
                        module_name = name.value if hasattr(name, 'value') else str(name)
                        if module_name == 'test_top':
                            instances.append(inst)
                    break
                parent = getattr(parent, 'parent', None)
        
        # 金标准: 1 个实例
        self.assertEqual(len(instances), 1, f"应有 1 个实例，实际有 {len(instances)} 个")
        
        # 金标准: 实例名称应为 'inst_fsm'
        inst = instances[0]
        inst_name = self._extract_instance_name(inst)
        
        self.assertEqual(inst_name, 'inst_fsm',
            f"实例名称应为 'inst_fsm'，实际为 '{inst_name}'")
    
    def _extract_instance_name(self, inst):
        """从 HierarchyInstantiation 提取实例名称"""
        if hasattr(inst, 'instances') and inst.instances:
            decl = inst.instances[0].decl if hasattr(inst.instances[0], 'decl') else None
            if decl and hasattr(decl, 'name') and decl.name:
                return decl.name.value if hasattr(decl.name, 'value') else str(decl.name)
        return None
    
    def test_instance_name_with_block_comment(self):
        """测试: 块注释在实例名前
        
        金标准:
        - 模块实例化了 1 个 fifo: u_fifo
        - 实例名称应为 'u_fifo'，不应为 '?'
        """
        source = '''
module test_top(input wire clk);
    /* ping-pong FIFO for data buffering */
    dual_clock_fifo u_fifo (.clk(clk));
endmodule

module dual_clock_fifo(input wire clk);
endmodule
'''
        self._verify_rtl(source, "instance_name_with_block_comment")
        
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        parser = FakeParser(tree)
        adapter = PyslangAdapter(parser)
        all_instances = adapter.get_module_instances(parser.trees)
        
        # 过滤 test_top 的实例
        test_top_instances = self._filter_instances_for_module(all_instances, 'test_top')
        
        self.assertEqual(len(test_top_instances), 1, 
            f"test_top 应有 1 个实例，实际有 {len(test_top_instances)} 个")
        
        inst_name = self._extract_instance_name(test_top_instances[0])
        
        self.assertEqual(inst_name, 'u_fifo',
            f"实例名称应为 'u_fifo'，实际为 '{inst_name}'")
    
    def _filter_instances_for_module(self, all_instances, module_name):
        """过滤出指定模块中的实例"""
        instances = []
        for inst in all_instances:
            parent = inst.parent
            while parent:
                if hasattr(parent, 'kind') and str(parent.kind) == 'SyntaxKind.ModuleDeclaration':
                    if hasattr(parent, 'header') and parent.header and hasattr(parent.header, 'name'):
                        name = parent.header.name
                        mn = name.value if hasattr(name, 'value') else str(name)
                        if mn == module_name:
                            instances.append(inst)
                    break
                parent = getattr(parent, 'parent', None)
        return instances
    
    def test_instance_name_with_psum_comment(self):
        """测试: 真实场景 - 行注释在实例前
        
        金标准:
        - 模块实例化了 dual_clock_fifo，实例名为 'I2'
        - 行注释 "// psum" 在实例名前，不应干扰实例名提取
        """
        source = '''
module pe(
    input wire clk_noc,
    input wire clk_pe
);
    // psum
    dual_clock_fifo I2 (
        .clk(clk_pe)
    );
endmodule

module dual_clock_fifo(input wire clk);
endmodule
'''
        # 跳过 Verilator 验证 (简化 RTL)
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        parser = FakeParser(tree)
        adapter = PyslangAdapter(parser)
        all_instances = adapter.get_module_instances(parser.trees)
        
        # 过滤 pe 的实例
        pe_instances = self._filter_instances_for_module(all_instances, 'pe')
        
        self.assertEqual(len(pe_instances), 1, 
            f"pe 应有 1 个实例，实际有 {len(pe_instances)} 个")
        
        inst_name = self._extract_instance_name(pe_instances[0])
        
        # 金标准: 实例名为 'I2'
        self.assertEqual(inst_name, 'I2',
            f"实例名称应为 'I2'，实际为 '{inst_name}'")
        self._verify_rtl(source, "instance_name_with_psum_comment")
        
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        parser = FakeParser(tree)
        adapter = PyslangAdapter(parser)
        all_instances = adapter.get_module_instances(parser.trees)
        
        # 过滤 pe 的实例
        pe_instances = self._filter_instances_for_module(all_instances, 'pe')
        
        self.assertEqual(len(pe_instances), 1, 
            f"pe 应有 1 个实例，实际有 {len(pe_instances)} 个")
        
        inst_name = self._extract_instance_name(pe_instances[0])
        
        # 金标准: 实例名为 'I2'
        self.assertEqual(inst_name, 'I2',
            f"psum 实例名称应为 'I2'，实际为 '{inst_name}'")
    
    #============================================================================
    # 测试场景 4: 真实 NVDLA 场景 - &Forget 注释
    #============================================================================
    def test_instance_name_with_dangle_comment(self):
        """测试: NVDLA 真实场景 - // &Forget dangle .*; 注释
        
        金标准:
        - top 模块实例化了 NV_NVDLA_BDMA_csb
        - 实例名应为 'u_csb'，不应为 '?'
        """
        source = '''
module top();
    // &Forget dangle .*;
    NV_NVDLA_BDMA_csb u_csb ();
endmodule

module NV_NVDLA_BDMA_csb();
endmodule
'''
        self._verify_rtl(source, "instance_name_with_dangle_comment")
        
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        parser = FakeParser(tree)
        adapter = PyslangAdapter(parser)
        all_instances = adapter.get_module_instances(parser.trees)
        
        # 过滤 top 的实例
        top_instances = self._filter_instances_for_module(all_instances, 'top')
        
        self.assertEqual(len(top_instances), 1, 
            f"top 应有 1 个实例，实际有 {len(top_instances)} 个")
        
        inst_name = self._extract_instance_name(top_instances[0])
        
        # 金标准: 实例名为 'u_csb'
        self.assertEqual(inst_name, 'u_csb',
            f"实例名称应为 'u_csb'，实际为 '{inst_name}'")
    
    #============================================================================
    # 测试场景 5: 多个实例，部分有注释
    #============================================================================
    def test_multiple_instances_mixed_comments(self):
        """测试: 多个实例，混合注释
        
        金标准:
        - 4 个实例: inst_a, inst_b, inst_c, inst_d
        - 所有实例名都应正确提取
        """
        source = '''
module test_top(input wire clk);
    // first instance
    mod_a inst_a (.clk(clk));
    /* second instance */ mod_b inst_b (.clk(clk));
    mod_c inst_c (.clk(clk));
    // fourth
    mod_d inst_d (.clk(clk));
endmodule

module mod_a(input wire clk); endmodule
module mod_b(input wire clk); endmodule
module mod_c(input wire clk); endmodule
module mod_d(input wire clk); endmodule
'''
        self._verify_rtl(source, "multiple_instances_mixed_comments")
        
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        parser = FakeParser(tree)
        adapter = PyslangAdapter(parser)
        all_instances = adapter.get_module_instances(parser.trees)
        
        # 过滤 test_top 的实例
        test_top_instances = self._filter_instances_for_module(all_instances, 'test_top')
        
        # 金标准: 4 个实例
        self.assertEqual(len(test_top_instances), 4, 
            f"test_top 应有 4 个实例，实际有 {len(test_top_instances)} 个")
        
        # 金标准: 所有实例名称正确
        inst_names = [self._extract_instance_name(inst) for inst in test_top_instances]
        expected_names = ['inst_a', 'inst_b', 'inst_c', 'inst_d']
        
        for expected, actual in zip(expected_names, inst_names):
            self.assertEqual(actual, expected,
                f"实例名称应为 '{expected}'，实际为 '{actual}'")


if __name__ == '__main__':
    unittest.main()