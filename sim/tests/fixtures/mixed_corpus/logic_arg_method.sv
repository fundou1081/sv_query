// mixed_corpus/06: logic 实参 → bit 形参 (Conversion 壳) 类方法展开 (iter_164 P1)
class packet;
  bit [7:0] addr;
  covergroup cg;
    cp: coverpoint addr;
  endgroup
  function new(); cg = new(); endfunction
  function void set(input bit [7:0] d);
    addr = d;
  endfunction
endclass

module top(input bit clk, input logic [7:0] din);
  packet p = new();
  always_ff @(posedge clk) begin
    p.set(din);
  end
endmodule
