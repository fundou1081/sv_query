# test_generate_case.py - Generate Case 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Generate Case 语法:
1. generate case 语句
2. case 内信号追踪
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


class TestGenerateCase(unittest.TestCase):
    """Generate Case 测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_generate_case_declaration(self):
        """[Golden] generate case 声明

        RTL:
        module top(input [1:0] sel, input a, b, c, output y);
            generate
                case (1'b1)
                    2'b00: begin : gen_a
                        assign y = a;
                    end
                    2'b01: begin : gen_b
                        assign y = b;
                    end
                    default: begin : gen_c
                        assign y = c;
                    end
                endcase
            endgenerate
        endmodule

        预期:
        - GenerateRegion 存在
        - CaseGenerate 存在
        """
        source = '''module top(input [1:0] sel, input a, b, c, output logic y);
    generate
        case (1'b1)
            2'b00: begin : gen_a
                assign y = a;
            end
            2'b01: begin : gen_b
                assign y = b;
            end
            default: begin : gen_c
                assign y = c;
            end
        endcase
    endgenerate
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 GenerateRegion
        gen_region = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.GenerateRegion:
                gen_region = m
                break

        self.assertIsNotNone(gen_region, "GenerateRegion not found")

        # 查找 CaseGenerate
        # v10: gen_region children 是 [SyntaxList(CaseGenerate, ...)]
        # v11: gen_region children 直接是 CaseGenerate
        case_generate = None
        for child in gen_region:
            kind = getattr(child, 'kind', None)
            kind_str = str(kind) if kind else ''
            # v11: 直接是 CaseGenerate
            if 'CaseGenerate' in kind_str:
                case_generate = child
                break
            # v10: SyntaxList 包装, 里面是 CaseGenerate
            is_list = (isinstance(child, list) or
                       ('SyntaxList' in kind_str or 'SeparatedList' in kind_str))
            if is_list:
                for item in child:
                    if str(getattr(item, 'kind', '')) == str(pyslang.SyntaxKind.CaseGenerate):
                        case_generate = item
                        break
                if case_generate:
                    break

        self.assertIsNotNone(case_generate, "CaseGenerate not found")

        # 检查 case items
        items = list(case_generate.items)
        self.assertGreaterEqual(len(items), 3, "Should have at least 3 case items")

    def test_generate_case_signal_tracking(self):
        """[Golden] generate case 信号追踪 (Plan F1.6 2026-08-13 修复)

        RTL with runtime parameter:
        module top #(parameter SEL = 0) (input a, b, c, output y);
            generate
                case (SEL)
                    0: begin : gen_a
                        assign y = a;
                    end
                    1: begin : gen_b
                        assign y = b;
                    end
                    default: begin : gen_c
                        assign y = c;
                    end
                endcase
            endgenerate
        endmodule

        预期:
        - SEL=0 → 只 gen_a active: a -> y 存在, b -> y / c -> y 不存在
        - SEL=1 → 只 gen_b active: b -> y 存在, a -> y / c -> y 不存在
        - SEL=2 (default) → 只 gen_c active: c -> y 存在, a -> y / b -> y 不存在

        之前错误源码用 `case (1'b1)` (编译期常量), pyslang 正确 instantiate 只
        gen_a, gen_b/gen_c.isUninstantiated=True. Plan F1 加 isUninstantiated
        filter 后, 只有一个分支的 driver 边会留在图里 — 暴露了测试源码的逻辑错误.
        与 commit 78610ac (test_generate_if_else_signal_tracking) 同模式修复.
        """
        source_template = '''module top #(parameter SEL = 0) (input a, b, c, output logic y);
    generate
        case (SEL)
            0: begin : gen_a
                assign y = a;
            end
            1: begin : gen_b
                assign y = b;
            end
            default: begin : gen_c
                assign y = c;
            end
        endcase
    endgenerate
endmodule'''

        def _check_sel(sel_value: int, active_letter: str):
            """编译 SEL=sel_value, 断言 active 分支 driver 边在, 其它不在."""
            source = source_template.replace(
                'parameter SEL = 0', f'parameter SEL = {sel_value}'
            )
            tracer = self._make_tracer(source)
            tracer.build_graph()
            edges = list(tracer.get_graph().edges())

            for letter in ('a', 'b', 'c'):
                present = any(letter in e[0] and 'y' in e[1] for e in edges)
                if letter == active_letter:
                    self.assertTrue(
                        present,
                        f"SEL={sel_value}: expected {letter} -> y in {edges}",
                    )
                else:
                    self.assertFalse(
                        present,
                        f"SEL={sel_value}: {letter} -> y should NOT appear "
                        f"(not active branch), got {edges}",
                    )

        # --- SEL=0 → gen_a active ---
        _check_sel(0, 'a')

        # --- SEL=1 → gen_b active ---
        _check_sel(1, 'b')

        # --- SEL=2 (matches default branch) → gen_c active ---
        _check_sel(2, 'c')

if __name__ == '__main__':
    unittest.main()
