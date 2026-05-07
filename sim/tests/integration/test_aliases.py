#==============================================================================
# test_aliases.py - 别名和覆盖测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestAliases(unittest.TestCase):
    """别名和覆盖测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_alias(self):
        """[Alias] alias 语句"""
        source = '''
module top(input a, output b);
    alias b = a;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('b', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_typedef_struct(self):
        """[Typedef] struct"""
        source = '''
module top;
    typedef struct packed {
        logic a;
        logic b;
    } my_struct;
    
    my_struct s;
    assign s.a = 1'b0;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())
    
    def test_typedef_enum(self):
        """[Typedef] enum"""
        source = '''
module top;
    typedef enum logic [1:0] {IDLE, RUN, STOP} state_t;
    state_t state;
    assign state = IDLE;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())
    
    def test_covergroup(self):
        """[Cover] covergroup"""
        source = '''
module top(input clk, input a);
    covergroup cg @(posedge clk);
        option.per_instance = 1;
        coverpoint a;
    endgroup
    
    cg cg_inst = new();
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())


if __name__ == '__main__':
    unittest.main()
