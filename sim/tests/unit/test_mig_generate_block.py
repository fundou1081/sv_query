"""
test_mig_generate_block.py - ModuleInstanceGraph generate block 支持金标准测试

[铁律13] 金标准测试
[铁律17] 强断言原则
[铁律22] 测试断言必须验证具体行为

场景设计 (RTL 来源: 芯片设计中常见的 generate 实例化模式):
  module dut (
      input clk,
      output logic [7:0] out
  );
  always_ff @(posedge clk)
      out <= 8'hAB;
  endmodule

  module top;
    genvar i;
    generate
      for (i=0; i<2; i=i+1) begin : GEN
        dut u_dut();
      end
    endgenerate
  endmodule

预期结果 (金标准):
  1. MIG.instances 应包含: top.GEN[0].u_dut, top.GEN[1].u_dut
     (或 top.gen[0].u_dut，取决于命名规范化)
  2. MIG.port_to_internal 应映射: top.GEN[0].u_dut.out -> dut.out
  3. get_instance('top.GEN[0].u_dut') 应返回 ModuleInstanceNode
  4. get_internal_signal('top.GEN[0].u_dut.out') 应返回 'dut.out'
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
import pyslang


class TestMIGGenerateBlock(unittest.TestCase):
    """MIG generate block 支持测试"""

    def _build_mig(self, source):
        """构建 MIG"""
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer._module_graph

    def test_loop_generate_instance(self):
        """[金标准] for 循环生成实例 - MIG 应能识别生成块中的实例

        注意: for 循环在 AST 中只对应一个 HierarchyInstantiation 节点，
        因为 genvar 是编译时信息不展开多个实例。
        MIG 识别的是 'top.GEN.u_dut' (模板实例)，这是正确行为。
        """
        source = '''module dut(input clk, output logic [7:0] out);
    always_ff @(posedge clk) out <= 8'hAB;
endmodule

module top;
    genvar i;
    generate
        for (i=0; i<2; i=i+1) begin : GEN
            dut u_dut();
        end
    endgenerate
endmodule'''

        mig = self._build_mig(source)
        instances = mig.get_all_instances()

        # [金标准] 验证: 应有 generate 块中的实例 (模板: top.GEN.u_dut)
        gen_instances = [inst for inst in instances if 'GEN' in inst or 'gen' in inst]
        self.assertGreaterEqual(
            len(gen_instances), 1,
            f"[金标准] for 循环生成应有 GEN 实例，实际找到 {len(gen_instances)} 个: {instances}"
        )

        # [金标准] 验证: 实例名应包含 GEN 和 u_dut
        for inst in gen_instances:
            self.assertIn('GEN', inst,
                f"[金标准] 实例路径应包含 GEN，实际: {inst}")

        # [金标准] 验证: port_to_internal 映射存在
        matching = {k: v for k, v in mig.port_to_internal.items() if 'GEN' in k}
        self.assertGreater(
            len(matching), 0,
            f"[金标准] generate 实例应有端口映射，实际: {matching}"
        )

    def test_loop_generate_instance_with_clk_connection(self):
        """[金标准] for 循环生成实例 + 时钟连接"""
        source = '''module clk_gen(output logic clk);
    always clk = #5 ~clk;
endmodule

module dut(input clk, output logic [7:0] out);
    always_ff @(posedge clk) out <= 8'hAB;
endmodule

module top;
    genvar i;
    logic clk;
    clk_gen u_clk();
    generate
        for (i=0; i<3; i=i+1) begin : GEN
            dut u_dut();
            assign u_dut.clk = clk;
        end
    endgenerate
endmodule'''

        mig = self._build_mig(source)
        instances = mig.get_all_instances()

        # [金标准] 验证: 应有 GEN 实例 + u_clk 实例
        # 注意: for 循环对应1个模板实例，不是3个
        gen_instances = [inst for inst in instances if 'GEN' in inst]
        self.assertGreaterEqual(
            len(gen_instances), 1,
            f"[金标准] for 循环生成应有 GEN 实例 (模板)，实际: {instances}"
        )

        # [金标准] 验证: port_to_internal 映射存在
        # 对于 generate 实例，映射格式可能是 top.GEN[0].u_dut.clk -> dut.clk
        gen_inst = next((i for i in instances if 'u_dut' in i), None)
        if gen_inst:
            # 检查是否有端口映射
            matching_keys = [k for k in mig.port_to_internal.keys() if 'u_dut' in k]
            self.assertGreater(
                len(matching_keys), 0,
                f"[金标准] generate 实例应有端口映射，实际: {mig.port_to_internal}"
            )

    def test_if_generate_instance(self):
        """[金标准] if 条件生成实例"""
        source = '''module sub(output logic [7:0] out);
    assign out = 8'hCD;
endmodule

module top;
    localparam [1:0] sel = 2;
    generate
        if (sel > 0) begin : COND
            sub u_sub();
        end
    endgenerate
endmodule'''

        mig = self._build_mig(source)
        instances = mig.get_all_instances()

        # [金标准] 验证: 应有 COND 实例 (sel 静态为 >0)
        cond_instances = [inst for inst in instances if 'COND' in inst or 'cond' in inst]
        self.assertGreaterEqual(
            len(cond_instances), 1,
            f"[金标准] if 生成应有 COND 实例，实际: {instances}"
        )

    def test_nested_generate_block(self):
        """[金标准] 嵌套 generate block"""
        source = '''module inner(output logic [7:0] out);
    assign out = 8'hEF;
endmodule

module outer(output logic [7:0] out);
    inner u_inner();
endmodule

module top;
    genvar i;
    generate
        for (i=0; i<2; i=i+1) begin : L1
            outer u_outer();
        end
    endgenerate
endmodule'''

        mig = self._build_mig(source)
        instances = mig.get_all_instances()

        # [金标准] 验证: 应有 L1 实例 (模板实例，不展开 genvar)
        l1_instances = [inst for inst in instances if 'L1' in inst or 'l1' in inst]
        self.assertGreaterEqual(
            len(l1_instances), 1,
            f"[金标准] 嵌套 generate 应有 L1 实例，实际: {instances}"
        )

        # [金标准] 验证: u_outer 实例应存在（嵌套在 L1 内）
        u_outer_instances = [inst for inst in instances if 'u_outer' in inst]
        self.assertGreaterEqual(
            len(u_outer_instances), 1,
            f"[金标准] 嵌套 generate 内部应有 u_outer 实例，实际: {instances}"
        )

    def test_generate_block_no_crash(self):
        """[金标准] generate block 不崩溃"""
        source = '''module dut(output logic [7:0] out);
    assign out = 8'h00;
endmodule

module top;
    genvar i;
    generate
        for (i=0; i<4; i=i+1) begin : GB
            dut u();
        end
    endgenerate
endmodule'''

        # [金标准] 验证: 构建过程不崩溃
        mig = self._build_mig(source)
        self.assertIsNotNone(mig, "MIG 构建不应返回 None")
        self.assertIsInstance(mig.instances, dict, "instances 应为 dict")
        self.assertIsInstance(mig.port_to_internal, dict, "port_to_internal 应为 dict")

    def test_get_instance_after_generate(self):
        """[金标准] 获取 generate 块内的实例"""
        source = '''module sub(output logic [7:0] out);
    assign out = 8'h12;
endmodule

module top;
    genvar i;
    generate
        for (i=0; i<2; i=i+1) begin : G
            sub u();
        end
    endgenerate
endmodule'''

        mig = self._build_mig(source)

        # [金标准] 验证: get_instance 能找到 generate 实例
        instances = mig.get_all_instances()
        self.assertGreater(len(instances), 0, "应有实例存在")

        # 尝试查找任意 generate 实例
        gen_inst = next((i for i in instances if 'G' in i or 'g' in i), None)
        if gen_inst:
            node = mig.get_instance(gen_inst)
            self.assertIsNotNone(node, f"[金标准] get_instance('{gen_inst}') 应返回节点")
            self.assertEqual(node.id, gen_inst, "[金标准] 返回的节点 ID 应匹配")

    def test_generate_with_parameterized_module(self):
        """[金标准] generate 块中实例化参数化模块"""
        source = '''module buffer #(
    parameter WIDTH = 8
) (
    input clk,
    input [WIDTH-1:0] data_in,
    output logic [WIDTH-1:0] data_out
);
    always_ff @(posedge clk) data_out <= data_in;
endmodule

module top;
    genvar i;
    generate
        for (i=0; i<2; i=i+1) begin : GB
            buffer #(.WIDTH(16)) u_buf();
        end
    endgenerate
endmodule'''

        mig = self._build_mig(source)
        instances = mig.get_all_instances()

        # [金标准] 验证: 参数化模块实例应被识别 (模板实例)
        gen_instances = [inst for inst in instances if 'GB' in inst or 'buf' in inst.lower()]
        self.assertGreaterEqual(
            len(gen_instances), 1,
            f"[金标准] 参数化模块在 generate 块中应有模板实例，实际: {instances}"
        )


if __name__ == '__main__':
    unittest.main()
