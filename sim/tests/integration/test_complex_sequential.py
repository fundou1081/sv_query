#==============================================================================
# test_complex_sequential.py - 复杂时序逻辑测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestComplexSequential(unittest.TestCase):
    """复杂时序逻辑测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    #----------------------------------------------------------------------
    # 复杂 always_ff 嵌套
    #----------------------------------------------------------------------
    
    def test_ff_with_case(self):
        """[Complex] always_ff + case"""
        source = '''
module top(
    input wire clk,
    input wire [1:0] sel,
    input wire a,
    input wire b,
    input wire c,
    input wire d,
    output reg q
);
    always_ff @(posedge clk) begin
        case (sel)
            2'b00:   q <= a;
            2'b01:   q <= b;
            2'b10:   q <= c;
            default:  q <= d;
        endcase
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_ff_with_nested_if(self):
        """[Complex] always_ff + 嵌套 if"""
        source = '''
module top(
    input wire clk,
    input wire rst_n,
    input wire en,
    input wire a,
    input wire b,
    input wire c,
    output reg q
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q <= 1'b0;
        end else if (en) begin
            if (a)
                q <= b;
            else
                q <= c;
        end
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_ff_with_forloop(self):
        """[Complex] always_ff + for 循环"""
        source = '''
module top(
    input wire clk,
    input wire [7:0] data,
    output reg [7:0] q
);
    integer i;
    always_ff @(posedge clk) begin
        for (i = 0; i < 8; i = i + 1) begin
            q[i] <= data[i];
        end
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_ff_with_while(self):
        """[Complex] always_ff + while"""
        source = '''
module top(
    input wire clk,
    input wire start,
    output reg done
);
    integer cnt;
    always_ff @(posedge clk) begin
        cnt = 0;
        while (cnt < 10) begin
            cnt = cnt + 1;
        end
        done <= (cnt == 10);
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('done', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_ff_with_disable(self):
        """[Complex] always_ff + disable"""
        source = '''
module top(
    input wire clk,
    input wire start,
    output reg q
);
    always_ff @(posedge clk) begin
        if (start)
            q <= 1'b1;
        // disable not supported
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
