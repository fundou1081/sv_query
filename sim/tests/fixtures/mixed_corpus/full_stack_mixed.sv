// mixed_corpus/03: module assign + submodule 端口 + class 方法 + 双域 cg (iter_168 M3)
class packet;
  rand bit [7:0] acc;
  covergroup cg_acc;
    cp: coverpoint acc;
  endgroup
  function new(); cg_acc = new(); endfunction
  function void accumulate(input bit [7:0] v);
    acc = acc + v;
  endfunction
endclass

module sub(input bit clk, input logic [7:0] a, input logic [7:0] b,
           output logic [7:0] s);
  assign s = a ^ b;
endmodule

module top(input bit clk, input logic [7:0] din, input logic [7:0] din2);
  logic [7:0] xored;
  logic [7:0] w;
  assign w = din & din2;
  sub u_sub(.clk(clk), .a(din), .b(w), .s(xored));
  packet p = new();
  covergroup cg_mod @(posedge clk);
    cp_x: coverpoint xored;
    cp_w: coverpoint {w, din};
  endgroup
  always_ff @(posedge clk) begin
    p.accumulate(xored);
  end
endmodule
