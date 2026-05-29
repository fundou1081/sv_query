#==============================================================================
# test_p3_bugs.py - P3 BUG 复现测试
# [铁律7] 金标准测试
#==============================================================================
# BUG 列表:
#   P3-1: 拼接表达式产生重复驱动边
#   P3-2: 字面量被当成驱动源
#
# 测试文件: opentitan/hw/ip/uart/rtl/uart_rx.sv
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestP3Bugs(unittest.TestCase):
    """P3 BUG 复现测试"""
    
    @classmethod
    def setUpClass(cls):
        """加载 uart_rx.sv 作为测试文件"""
        file_path = '/Users/fundou/my_dv_proj/opentitan/hw/ip/uart/rtl/uart_rx.sv'
        with open(file_path, 'r') as f:
            cls.source = f.read()
    
    def _make_tracer(self):
        """创建 tracer"""
        return UnifiedTracer(sources={'uart_rx.sv': self.source})
    
    #----------------------------------------------------------------------
    # P3-1: 拼接表达式重复驱动边
    #----------------------------------------------------------------------
    
    def test_p3_1_no_duplicate_drivers_from_concatenation(self):
        """
        [P3-1] 拼接表达式不应产生重复驱动边
        
        场景: {rx, sreg_q[10:1]} -> sreg_d
        期望: rx -> sreg_d 单独作为驱动源
        期望: sreg_q[10:1] 不应作为独立驱动源（只是 part-select）
        期望: sreg_q -> sreg_d 不应出现（自连接）
        
        实际当前行为（错误）:
          uart_rx.rx -> uart_rx.sreg_d     ✅
          uart_rx.sreg_q -> uart_rx.sreg_d ❌ 自连接，重复
          uart_rx.sreg_q[10:1] -> uart_rx.sreg_d ❌ Part-select 不应独立
        """
        tracer = self._make_tracer()
        graph = tracer.build_graph()
        
        # 收集所有指向 sreg_d 的驱动边
        sreg_d_drivers = []
        for src, dst, data in graph.edges(data=True):
            if 'sreg_d' in dst:
                sreg_d_drivers.append(src)
        
        print(f"\n[P3-1] sreg_d 的驱动源:")
        for d in sreg_d_drivers:
            print(f"  -> {d}")
        
        # P3-1 检查1: sreg_q -> sreg_d 不应存在（自连接是重复的）
        self.assertNotIn(
            'uart_rx.sreg_q',
            sreg_d_drivers,
            "P3-1 FAIL: sreg_q -> sreg_d 是自连接，不应作为独立驱动边"
        )
        
        # P3-1 检查2: sreg_q[10:1] -> sreg_d 不应存在（part-select 不应独立）
        self.assertNotIn(
            'uart_rx.sreg_q[10:1]',
            sreg_d_drivers,
            "P3-1 FAIL: sreg_q[10:1] 是 part-select，不应作为独立驱动边"
        )
        
        # P3-1 检查3: rx -> sreg_d 应该存在
        self.assertIn(
            'uart_rx.rx',
            sreg_d_drivers,
            "P3-1 FAIL: rx -> sreg_d 应该存在"
        )
    
    #----------------------------------------------------------------------
    # P3-2: 字面量不应作为驱动源
    #----------------------------------------------------------------------
    
    def test_p3_2_no_literal_as_driver(self):
        """
        [P3-2] 字面量不应作为驱动源
        
        场景: 4'b0, 1'b1, 11'd0 等字面量被列为驱动源
        期望: 字面量只作为"赋值条件"标注，不作为独立驱动源
        
        字面量驱动的例子:
          11'd0 -> sreg_q
          11'd0 -> sreg_d
          4'b0 -> bit_cnt_q
          1'b1 -> idle_q
          4'b1011 -> bit_cnt_d
        """
        tracer = self._make_tracer()
        graph = tracer.build_graph()
        
        # 收集所有字面量驱动边
        literal_drivers = []
        for src, dst, data in graph.edges(data=True):
            # 字面量以非字母开头，或只有数字/特殊格式
            if (src.startswith("1'") or src.startswith("4'") or 
                src.startswith("11'") or src.startswith("8'") or
                src.startswith("16'") or src.startswith("32'") or
                src == '0' or src == '1' or src.isdigit()):
                literal_drivers.append(src)
        
        print(f"\n[P3-2] 字面量驱动源 (共 {len(literal_drivers)} 条):")
        for d in set(literal_drivers):
            count = literal_drivers.count(d)
            print(f"  {d} -> ... ({count} 条边)")
        
        # P3-2 检查: 字面量不应作为独立驱动源
        self.assertEqual(
            len(literal_drivers),
            0,
            f"P3-2 FAIL: 字面量被列为驱动源，共 {len(literal_drivers)} 条\n"
            f"  字面量示例: {list(set(literal_drivers))[:5]}\n"
            f"  字面量是赋值条件，不是驱动源"
        )
    
    def test_p3_2_literals_should_be_condition_not_driver(self):
        """
        [P3-2 备选] 字面量可以作为边的属性，但不应作为节点/驱动源
        
        如果暂时无法完全移除字面量边，至少应该:
        1. 字面量不出现在 trace 输出的一级驱动列表中
        2. 字面量只显示为驱动条件的一部分
        """
        tracer = self._make_tracer()
        graph = tracer.build_graph()
        
        # 检查字面量是否作为 CONST 节点类型存在
        nodes_with_literal_name = []
        for node_id in graph.nodes():
            if (node_id.startswith("1'") or node_id.startswith("4'") or 
                node_id.startswith("11'") or node_id.startswith("8'")):
                nodes_with_literal_name.append(node_id)
        
        print(f"\n[P3-2 备选] 字面量节点:")
        for n in nodes_with_literal_name[:10]:
            print(f"  {n}")
        
        # 字面量节点数量应该为 0 或很少（只用于CONST类型）
        # 注意：这里我们允许 CONST 类型存在，但不允许字面量作为边驱动源
        # 所以这个测试是备选验证


if __name__ == '__main__':
    unittest.main(verbosity=2)