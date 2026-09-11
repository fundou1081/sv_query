// mixed_corpus/04: 参数化 class 内嵌参数化 class + 方法链 (iter_170/178 P5)
class inner #(int W = 8);
  bit [W-1:0] val;
  function void set(input bit [W-1:0] v);
    val = v;
  endfunction
endclass

class packet #(int W = 8);
  inner #(W) i;
  rand bit [W-1:0] data;
  covergroup cg;
    cp: coverpoint data;
  endgroup
  function new();
    i = new();
    cg = new();
  endfunction
  function void drive(input bit [W-1:0] v);
    i.set(v);
  endfunction
endclass

module top(input bit clk, input bit [7:0] din);
  packet #(8) p = new();
  always_ff @(posedge clk) p.drive(din);
endmodule
