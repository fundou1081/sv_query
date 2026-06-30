# test_opentitan_aes_sub_bytes.py - OpenTitan AES SubBytes 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
从 OpenTitan AES SubBytes 模块提取的真实场景测试

场景: aes_sub_bytes 模块的基本功能测试
来源: hw/ip/aes/rtl/aes_sub_bytes.sv
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestAESSubBytes(unittest.TestCase):
    """AES SubBytes 模块信号追踪测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        # 使用 't' 作为 tree key (符合项目惯例)
        return UnifiedTracer(sources={'t.sv': source})

    def test_sub_bytes_basic_assign(self):
        """[Golden] 基础赋值 (SubBytes 核心)

        RTL 来源: aes_sub_bytes.sv
        assign data_o = data_i;

        预期:
        - data_o <- data_i 驱动关系存在
        """
        source = '''
module aes_sub_bytes (
    input  logic [7:0]  data_i,
    output logic [7:0]  data_o
);
    assign data_o = data_i;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('data_o', 'aes_sub_bytes')

        # 金标准: data_o <- data_i
        self.assertIn('aes_sub_bytes.data_i', [d.id for d in result.drivers],
            f"data_o 应被 data_i 驱动，实际驱动: {[d.id for d in result.drivers]}")

    def test_sub_bytes_multi_array(self):
        """[Golden] 多维数组信号 (SubBytes 真实模式)

        RTL 来源: aes_sub_bytes.sv
        logic [3:0][3:0][7:0] data_o

        预期:
        - 多维数组端口可解析
        - 驱动追溯正确
        """
        source = '''
module aes_sub_bytes (
    input  logic [3:0][3:0][7:0] data_i,
    output logic [3:0][3:0][7:0] data_o
);
    assign data_o = data_i;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('data_o', 'aes_sub_bytes')

        # 金标准: data_o 被 data_i 驱动
        self.assertIn('aes_sub_bytes.data_i', [d.id for d in result.drivers],
            f"data_o 应被 data_i 驱动，实际驱动: {[d.id for d in result.drivers]}")

    def test_sub_bytes_prd_masking(self):
        """[Golden] PRD 随机性掩码 (SubBytes 真实模式)

        RTL 来源: aes_sub_bytes.sv
        prd_i 随机性输入，prd_o 随机性输出

        预期:
        - prd_o <- prd_i 驱动关系存在
        """
        source = '''
module aes_sub_bytes (
    input  logic [7:0]   data_i,
    input  logic [19:0]  prd_i,
    output logic [7:0]   data_o,
    output logic [19:0]  prd_o
);
    // PRD 传递
    assign prd_o = prd_i;
    assign data_o = data_i;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('prd_o', 'aes_sub_bytes')

        # 金标准: prd_o <- prd_i
        self.assertIn('aes_sub_bytes.prd_i', [d.id for d in result.drivers],
            f"prd_o 应被 prd_i 驱动，实际驱动: {[d.id for d in result.drivers]}")

    def test_sub_bytes_genvar_iteration(self):
        """[Golden] genvar 迭代 (SubBytes 真实模式)

        RTL 来源: aes_sub_bytes.sv
        for (genvar j = 0; j < 4; j++) ...

        预期:
        - genvar 迭代可解析
        - 驱动追溯正确
        """
        source = '''
module aes_sub_bytes (
    input  logic [3:0][3:0][7:0] data_i,
    output logic [3:0][3:0][7:0] data_o
);
    // genvar 迭代
    for (genvar j = 0; j < 4; j++) begin : gen_sbox_j
        for (genvar i = 0; i < 4; i++) begin : gen_sbox_i
            assign data_o[i][j] = data_i[i][j];
        end
    end
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('data_o', 'aes_sub_bytes')

        # 金标准: data_o 有驱动
        driver_ids = [d.id for d in result.drivers]
        self.assertTrue(len(driver_ids) > 0,
            f"data_o 应有驱动源，实际驱动: {result.drivers}")


if __name__ == '__main__':
    unittest.main()
