#==============================================================================
# test_query_load.py - Load 追溯单元测试
#==============================================================================
"""
[铁律13] 金标准测试
[铁律17] 强断言原则
[铁律22] 断言必须验证具体行为
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.query.load import LoadTracer, LoadChain
from trace.core.graph.models import EdgeKind, NodeKind


class TestLoadTracer(unittest.TestCase):
    """Load 追溯测试"""
    
    def _build_graph(self, source):
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_simple_chain(self):
        """[金标准] 简单链: d -> tmp -> q
        
        金标准:
        RTL:
          tmp <= d;  // d 驱动 tmp
          q <= tmp;  // tmp 驱动 q
        
        期望:
        - d 的 loads: [tmp, q]
        - tmp 的 loads: [q]
        """
        source = '''
module top(input clk, input d, output logic q);
    logic tmp;
    always_ff @(posedge clk) begin
        tmp <= d;
        q <= tmp;
    end
endmodule'''
        graph = self._build_graph(source)
        tracer = LoadTracer(graph)
        
        # 强断言1: d 的 loads 包含 tmp
        chain = tracer.trace('d', 'top')
        self.assertGreater(len(chain.loads), 0, "d应有后继")
        load_ids = [l.id for l in chain.loads]
        self.assertIn('top.tmp', load_ids, "d的loads应包含tmp")
        
        # 强断言2: d 的 loads 也包含 q（通过 tmp 追溯）
        self.assertIn('top.q', load_ids, "d的loads应通过tmp追溯到q")
        
        # 强断言3: tmp 的 loads 包含 q
        chain_tmp = tracer.trace('tmp', 'top')
        tmp_load_ids = [l.id for l in chain_tmp.loads]
        self.assertIn('top.q', tmp_load_ids, "tmp的loads应包含q")
    
    def test_no_load(self):
        """[金标准] 无负载 - output 没有后继
        
        金标准:
        RTL:
          q <= d;  // q 是终点
        
        期望:
        - q 的 loads 为空
        - confidence: no_load
        """
        source = '''
module top(input clk, input d, output logic q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        graph = self._build_graph(source)
        tracer = LoadTracer(graph)
        
        chain = tracer.trace('q', 'top')
        self.assertEqual(len(chain.loads), 0, "output应无后继")
        self.assertEqual(chain.confidence, "no_load")
    
    def test_multi_load(self):
        """[金标准] 多负载 - 一个信号驱动多个
        
        金标准:
        RTL:
          q1 <= d;
          q2 <= d;
          q3 <= d;
        
        期望:
        - d 的 loads: [q1, q2, q3]
        - confidence: medium
        """
        source = '''
module top(input clk, input d, output logic q1, q2, q3);
    always_ff @(posedge clk) begin
        q1 <= d;
        q2 <= d;
        q3 <= d;
    end
endmodule'''
        graph = self._build_graph(source)
        tracer = LoadTracer(graph)
        
        chain = tracer.trace('d', 'top')
        self.assertEqual(len(chain.loads), 3, "d应有3个后继")
        load_ids = [l.id for l in chain.loads]
        self.assertIn('top.q1', load_ids)
        self.assertIn('top.q2', load_ids)
        self.assertIn('top.q3', load_ids)
        self.assertEqual(chain.confidence, "medium")
    
    def test_get_loads_api(self):
        """[金标准] get_loads 简化 API
        
        期望:
        - 返回节点 ID 列表
        """
        source = '''
module top(input clk, input d, output logic q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        graph = self._build_graph(source)
        tracer = LoadTracer(graph)
        
        loads = tracer.get_loads('top.d')
        self.assertIsInstance(loads, list)
        self.assertIn('top.q', loads)


if __name__ == '__main__':
    unittest.main()
