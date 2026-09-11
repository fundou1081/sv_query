// mixed_corpus/07: generate-for 实例 + 类实例 + module cg (混合形态)
class packet;
  rand bit [7:0] data;
  function void set(input bit [7:0] d);
    data = d;
  endfunction
endclass

module leaf(input logic [7:0] a, output logic [7:0] y);
  assign y = a;
endmodule

module top(input bit clk, input logic [7:0] din);
  logic [7:0] chain [0:3];
  assign chain[0] = din;
  generate for (genvar i = 0; i < 3; i++) begin : G
    leaf u_leaf(.a(chain[i]), .y(chain[i+1]));
  end endgenerate
  packet p = new();
  covergroup cg @(posedge clk);
    cp: coverpoint chain[3];
  endgroup
  always_ff @(posedge clk) begin
    p.set(din);
  end
endmodule
