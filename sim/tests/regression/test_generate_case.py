# test_generate_case.py - Generate Case 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Generate Case 语法:
1. generate case 语句
2. case 内信号追踪
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestGenerateCase(unittest.TestCase):
    """Generate Case 测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
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
        """[Golden] generate case 信号追踪

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
        - a -> y 驱动关系
        - b -> y 驱动关系
        - c -> y 驱动关系
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
        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())

        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())

        # 验证: a -> y
        has_a_y = any('a' in edge[0] and 'y' in edge[1] for edge in edges)
        self.assertTrue(has_a_y, f"a -> y not found in {edges}")

        # 验证: b -> y
        has_b_y = any('b' in edge[0] and 'y' in edge[1] for edge in edges)
        self.assertTrue(has_b_y, f"b -> y not found in {edges}")

        # 验证: c -> y
        has_c_y = any('c' in edge[0] and 'y' in edge[1] for edge in edges)
        self.assertTrue(has_c_y, f"c -> y not found in {edges}")

if __name__ == '__main__':
    unittest.main()
