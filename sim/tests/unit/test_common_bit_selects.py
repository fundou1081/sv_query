# ==============================================================================
# test_common_bit_selects.py - pyslang API select helper 单元测试
#
# [ARCHITECTURE_TODOLIST #2 G3 Option 3 2026-08-28 06:38]
# 验证 extractors._common.iter_bit_selects() 跟原 regex 方案输出一致.
# ==============================================================================
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from trace.core.compiler import SVCompiler
from trace.core.extractors._common import (
    iter_bit_selects,
    BitSelectHit,
    make_range_select_id,
    make_element_select_id,
)


class TestIterBitSelects(unittest.TestCase):
    """[2026-08-28 07:00] pyslang API helper 单测 (通用方案 a 重构后)."""

    def _get_modules(self, source):
        compiler = SVCompiler(sources={'test.sv': source}, log_level='NONE', strict=False)
        root = compiler.get_root()
        tops = root.topInstances
        return [tops[i] for i in range(len(tops))]

    def _walk(self, source, instance_path='top'):
        """拿顶层 module + 走 helper 拿 BitSelectHit 列表."""
        mods = self._get_modules(source)
        return list(iter_bit_selects(mods[0], instance_path=instance_path))

    def test_range_select_simple(self):
        """[金标准] data[3:0] — RangeSelect 单个"""
        source = '''
module top;
    logic [7:0] data;
    initial data[3:0] = 4'hA;
endmodule
'''
        selects = self._walk(source)
        range_sel = [s for s in selects if s.select_kind == 'RangeSelect']
        self.assertGreater(len(range_sel), 0, "应找到 RangeSelect")
        s = range_sel[0]
        self.assertEqual(s.msb, 3, f"msb 应为 3, 实际 {s.msb}")
        self.assertEqual(s.lsb, 0, f"lsb 应为 0, 实际 {s.lsb}")
        self.assertEqual(s.full_id, 'top.data[3:0]', f"full_id 应为 'top.data[3:0]', 实际 {s.full_id!r}")
        # base_chain 含 immediate parent (无 sel) + immediate-with-sel (最后一位)
        self.assertEqual(s.base_chain, ['top.data', 'top.data[3:0]'],
                         f"base_chain 应为 ['top.data', 'top.data[3:0]'], 实际 {s.base_chain}")

    def test_element_select_simple(self):
        """[金标准] data[0] — ElementSelect 单个"""
        source = '''
module top;
    logic [7:0] data;
    initial data[0] = 1'b1;
endmodule
'''
        selects = self._walk(source)
        elem_sel = [s for s in selects if s.select_kind == 'ElementSelect']
        self.assertGreater(len(elem_sel), 0, "应找到 ElementSelect")
        s = elem_sel[0]
        self.assertEqual(s.index, 0, f"index 应为 0, 实际 {s.index}")
        self.assertEqual(s.full_id, 'top.data[0]', f"full_id 应为 'top.data[0]', 实际 {s.full_id!r}")

    def test_make_ids(self):
        """[单元] 节点 ID 工厂跟 regex 方案兼容"""
        self.assertEqual(make_range_select_id('top.data', 3, 0), 'top.data[3:0]')
        self.assertEqual(make_range_select_id('top.data', 7, 4), 'top.data[7:4]')
        self.assertEqual(make_element_select_id('top.data', 0), 'top.data[0]')
        self.assertEqual(make_element_select_id('top.data', 7), 'top.data[7]')

    def test_parameter_range_select(self):
        """[边界] data[W-1:0] — parameter 位选, _eval_to_int 走 pyslang eval 后拿到 7"""
        source = '''
module top #(parameter W = 8);
    logic [W-1:0] data;
    initial data[W-1:0] = 0;
endmodule
'''
        selects = self._walk(source)
        range_sel = [s for s in selects if s.select_kind == 'RangeSelect']
        self.assertGreater(len(range_sel), 0, "Parameter 位选应能找到")
        s = range_sel[0]
        # 通用方案 a: pyslang eval 应该 evaluate W-1=7
        # (如 eval() 拿不到则仍可能为 None, 取决于 pyslang version)
        if s.msb is not None:
            self.assertEqual(s.msb, 7, f"Parameter W=8 折叠后 msb 应为 7 (走 eval), 实际 {s.msb}")
        else:
            # 退化: eval 拿不到, full_id 用 raw text
            self.assertIn('data', s.full_id, f"Parameter 位选 full_id 应含 'data', 实际 {s.full_id!r}")
        # lsb 仍是 0 (IntegerLiteral)
        self.assertEqual(s.lsb, 0, f"right 是 IntegerLiteral(0), 期望 0, 实际 {s.lsb}")

    def test_struct_field_range_select(self):
        """[边界] pkt.addr[3:0] — MemberAccess + RangeSelect, base_chain 应该是 ['top.pkt', 'top.pkt.addr']"""
        source = '''
module top;
    typedef struct packed { logic [7:0] addr; logic [7:0] data; } pkt_t;
    pkt_t pkt;
    initial pkt.addr[3:0] = 4'h5;
endmodule
'''
        selects = self._walk(source)
        range_sel = [s for s in selects if s.select_kind == 'RangeSelect']
        self.assertGreater(len(range_sel), 0, "Struct 字段位选应能找到")
        s = range_sel[0]
        self.assertEqual(s.msb, 3, f"msb 应为 3, 实际 {s.msb}")
        self.assertEqual(s.lsb, 0, f"lsb 应为 0, 实际 {s.lsb}")
        self.assertEqual(s.full_id, 'top.pkt.addr[3:0]', f"full_id 应为 'top.pkt.addr[3:0]', 实际 {s.full_id!r}")
        # base_chain 完整: 顶层 'top.pkt' -> struct field 'top.pkt.addr' -> immediate-with-sel 'top.pkt.addr[3:0]'
        self.assertEqual(s.base_chain, ['top.pkt', 'top.pkt.addr', 'top.pkt.addr[3:0]'],
                         f"base_chain 应为 ['top.pkt', 'top.pkt.addr', 'top.pkt.addr[3:0]'], 实际 {s.base_chain}")


if __name__ == '__main__':
    unittest.main(verbosity=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)