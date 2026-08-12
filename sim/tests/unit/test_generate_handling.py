"""
test_generate_handling.py - SemanticAdapter generate block 处理单元测试

[Plan F1 2026-08-12] 覆盖 generate for / generate if / generate case 的核心行为:
  1. generate for: 每个 iteration 的 assign 都收, 每个的 genvar_ctx 正确
  2. generate for: genvar 表达式 (i+1) 在 selector 里被 substitute + constant fold
  3. generate if: 编译期 instantiate 单分支, false branch 的 assign 被 filter
  4. generate case: 编译期 case 匹配, 非匹配分支 (含 default) 被 filter
  5. generate nested: 多 generate 块串联, ctx 独立

[铁律13] 金标准测试
[铁律17] 强断言原则
[铁律22] 断言验证具体行为 (节点数, 边数, ctx 值, 等)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestGenerateForHandling(unittest.TestCase):
    """generate for (生成块循环) 行为测试"""

    def _make_adapter(self, source, target_module=None):
        """辅助: 创建 adapter"""
        compiler = SVCompiler({'test.sv': source})
        root = compiler.get_root()
        return SemanticAdapter(root, compiler=compiler, target_module=target_module)

    def _find_target(self, adapter, target_module):
        """找 target module InstanceSymbol"""
        return adapter._find_target_top(target_module)

    def test_generate_for_collects_all_iterations(self):
        """generate for: 4 个 iteration → 4 个 assign 收上来"""
        source = '''
module gen_for_demo #(parameter N = 4) (
    input  [7:0] data,
    output [7:0] acc [0:N]
);
    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen_stage
            assign acc[i] = data + i;
        end
    endgenerate
endmodule
'''
        adapter = self._make_adapter(source, target_module='gen_for_demo')
        target = self._find_target(adapter, 'gen_for_demo')

        assigns = adapter.get_assignments(target)

        # 期望: 4 个 generate iteration 各产 1 个 assign
        self.assertEqual(len(assigns), 4, f"expected 4 assigns, got {len(assigns)}")

    def test_generate_for_genvar_context_per_entry(self):
        """generate for: 每个 iteration 的 genvar_ctx 正确 (i=0,1,2,3)"""
        source = '''
module gen_for_ctx #(
    parameter N = 4
) (
    input  [7:0] data,
    output [7:0] acc [0:N-1]
);
    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen_stage
            assign acc[i] = data + i;
        end
    endgenerate
endmodule
'''
        adapter = self._make_adapter(source, target_module='gen_for_ctx')
        target = self._find_target(adapter, 'gen_for_ctx')

        assigns = adapter.get_assignments(target)
        ctxs = [adapter.get_genvar_context(a) for a in assigns]

        # 期望: 4 个 ctx, 每个都是 {'i': 0/1/2/3}
        i_values = sorted([c.get('i') for c in ctxs])
        self.assertEqual(i_values, [0, 1, 2, 3],
                         f"expected genvar values [0,1,2,3], got {i_values}")

    def test_generate_for_uninstantiated_entries_filtered(self):
        """generate for: isUninstantiated entry (空 range) 被 filter"""
        source = '''
module gen_for_uninst #(
    parameter N = 4
) (
    input  [7:0] data,
    output [7:0] out
);
    // 故意 0 < 0 永远循环, 全部 entry 应该 uninstantiated
    genvar i;
    generate
        for (i = 0; i < 0; i = i + 1) begin : gen_empty
            assign out = data;
        end
    endgenerate
endmodule
'''
        adapter = self._make_adapter(source, target_module='gen_for_uninst')
        target = self._find_target(adapter, 'gen_for_uninst')

        assigns = adapter.get_assignments(target)
        # 期望: 0 assigns (空 range 全部 uninstantiated)
        self.assertEqual(len(assigns), 0,
                         f"expected 0 assigns (empty range), got {len(assigns)}")


class TestGenerateIfHandling(unittest.TestCase):
    """generate if (编译期条件分支) 行为测试"""

    def _make_adapter(self, source, target_module=None):
        compiler = SVCompiler({'test.sv': source})
        root = compiler.get_root()
        return SemanticAdapter(root, compiler=compiler, target_module=target_module)

    def _find_target(self, adapter, target_module):
        return adapter._find_target_top(target_module)

    def test_generate_if_true_branch_collected(self):
        """generate if: MODE=1 → gen_adder 的 assign 收上来"""
        source = '''
module gen_if_true #(
    parameter MODE = 1
) (
    input  [7:0] a, b,
    output [7:0] result
);
    wire [7:0] op1;
    wire [7:0] op2;
    assign op1 = a + b;
    assign op2 = a - b;

    generate
        if (MODE == 1) begin : gen_adder
            assign result = op1 + a;
        end else begin : gen_subtractor
            assign result = op2 - a;
        end
    endgenerate
endmodule
'''
        adapter = self._make_adapter(source, target_module='gen_if_true')
        target = self._find_target(adapter, 'gen_if_true')

        assigns = adapter.get_assignments(target)

        # 期望: 3 assigns (op1, op2, gen_adder.result)
        # gen_subtractor.result 应被 filter
        self.assertEqual(len(assigns), 3,
                         f"expected 3 assigns (op1+op2+gen_adder), got {len(assigns)}")

        # 验证: 不存在 gen_subtractor 的 assign
        for a in assigns:
            hp = getattr(a, 'hierarchicalPath', '')
            self.assertNotIn('gen_subtractor', hp,
                             f"gen_subtractor should be filtered: {hp}")

    def test_generate_if_false_branch_collected(self):
        """generate if: MODE=0 → gen_subtractor 的 assign 收上来"""
        source = '''
module gen_if_false #(
    parameter MODE = 0
) (
    input  [7:0] a, b,
    output [7:0] result
);
    wire [7:0] op1;
    wire [7:0] op2;
    assign op1 = a + b;
    assign op2 = a - b;

    generate
        if (MODE == 1) begin : gen_adder
            assign result = op1 + a;
        end else begin : gen_subtractor
            assign result = op2 - a;
        end
    endgenerate
endmodule
'''
        adapter = self._make_adapter(source, target_module='gen_if_false')
        target = self._find_target(adapter, 'gen_if_false')

        assigns = adapter.get_assignments(target)

        # 期望: 3 assigns (op1, op2, gen_subtractor.result)
        self.assertEqual(len(assigns), 3,
                         f"expected 3 assigns (op1+op2+gen_subtractor), got {len(assigns)}")

        for a in assigns:
            hp = getattr(a, 'hierarchicalPath', '')
            self.assertNotIn('gen_adder', hp,
                             f"gen_adder should be filtered: {hp}")


class TestGenerateCaseHandling(unittest.TestCase):
    """generate case (编译期 case 匹配) 行为测试"""

    def _make_adapter(self, source, target_module=None):
        compiler = SVCompiler({'test.sv': source})
        root = compiler.get_root()
        return SemanticAdapter(root, compiler=compiler, target_module=target_module)

    def _find_target(self, adapter, target_module):
        return adapter._find_target_top(target_module)

    def test_generate_case_specific_value(self):
        """generate case: SEL=2 → gen_subtractor 收, 其他被 filter"""
        source = '''
module gen_case_specific #(
    parameter SEL = 2
) (
    input  [7:0] data_in,
    output [7:0] result
);
    wire [7:0] op1;
    wire [7:0] op2;
    assign op1 = data_in + 1;
    assign op2 = data_in - 1;

    generate
        case (SEL)
            1: begin : gen_adder
                assign result = op1 + data_in;
            end
            2: begin : gen_subtractor
                assign result = op2 - data_in;
            end
            default: begin : gen_default
                assign result = data_in;
            end
        endcase
    endgenerate
endmodule
'''
        adapter = self._make_adapter(source, target_module='gen_case_specific')
        target = self._find_target(adapter, 'gen_case_specific')

        assigns = adapter.get_assignments(target)

        # 期望: 3 assigns (op1, op2, gen_subtractor.result)
        self.assertEqual(len(assigns), 3,
                         f"expected 3 assigns (op1+op2+gen_subtractor), got {len(assigns)}")

        # 验证: gen_adder 和 gen_default 都被 filter
        for a in assigns:
            hp = getattr(a, 'hierarchicalPath', '')
            self.assertNotIn('gen_adder', hp,
                             f"gen_adder should be filtered: {hp}")
            self.assertNotIn('gen_default', hp,
                             f"gen_default should be filtered: {hp}")

    def test_generate_case_default_branch(self):
        """generate case: SEL=99 (no match) → default branch 收"""
        source = '''
module gen_case_default #(
    parameter SEL = 99
) (
    input  [7:0] data_in,
    output [7:0] result
);
    generate
        case (SEL)
            1: begin : gen_adder
                assign result = data_in + 1;
            end
            2: begin : gen_subtractor
                assign result = data_in - 1;
            end
            default: begin : gen_default
                assign result = data_in;
            end
        endcase
    endgenerate
endmodule
'''
        adapter = self._make_adapter(source, target_module='gen_case_default')
        target = self._find_target(adapter, 'gen_case_default')

        assigns = adapter.get_assignments(target)

        # 期望: 1 assign (gen_default.result)
        self.assertEqual(len(assigns), 1,
                         f"expected 1 assign (gen_default only), got {len(assigns)}")

        a = assigns[0]
        hp = getattr(a, 'hierarchicalPath', '')
        self.assertIn('gen_default', hp,
                      f"gen_default should be active: {hp}")


class TestGenerateNestedHandling(unittest.TestCase):
    """generate 嵌套 / 多 generate 块独立 scope 行为测试"""

    def _make_adapter(self, source, target_module=None):
        compiler = SVCompiler({'test.sv': source})
        root = compiler.get_root()
        return SemanticAdapter(root, compiler=compiler, target_module=target_module)

    def _find_target(self, adapter, target_module):
        return adapter._find_target_top(target_module)

    def test_two_generate_for_blocks_independent(self):
        """两个 generate for 块: 各自 scope 独立, 共 6 个 iteration"""
        source = '''
module gen_two_blocks #(
    parameter N = 3
) (
    input  [7:0] data,
    output [7:0] buf1 [0:N-1],
    output [7:0] buf2 [0:N-1]
);
    assign buf1[0] = data;
    assign buf2[0] = data;

    genvar i;
    generate
        for (i = 0; i < N - 1; i = i + 1) begin : gen_stage1
            assign buf1[i+1] = buf1[i] + 1;
        end
        for (i = 0; i < N - 1; i = i + 1) begin : gen_stage2
            assign buf2[i+1] = buf2[i] + 2;
        end
    endgenerate
endmodule
'''
        adapter = self._make_adapter(source, target_module='gen_two_blocks')
        target = self._find_target(adapter, 'gen_two_blocks')

        assigns = adapter.get_assignments(target)

        # 期望: 4 个 assigns
        # 2 顶层 (buf1[0], buf2[0]) + 2 generate blocks × (N-1)=2 iterations = 4+2=6
        self.assertEqual(len(assigns), 6,
                         f"expected 6 assigns (2 top + 2*2 gen), got {len(assigns)}")

        # 验证: 4 个 generate ctx 都正确
        gen_ctxs = []
        for a in assigns:
            ctx = adapter.get_genvar_context(a)
            if ctx:
                gen_ctxs.append(ctx.get('i'))

        # 期望: 4 个 generate ctx, 每个 stage 各 2 个 (i=0, 1)
        # 但 stage1 和 stage2 共用 i, 所以 i=0,1 各 produce 2 ctx
        self.assertEqual(sorted(gen_ctxs), [0, 0, 1, 1],
                         f"expected i values [0,0,1,1] (2 stages × 2 iter), got {sorted(gen_ctxs)}")


if __name__ == '__main__':
    unittest.main()
