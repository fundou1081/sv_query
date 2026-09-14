`define DECL_FF(name, width) logic [width-1:0] name``_q;
`define FF_BODY(name) always_ff @(posedge clk) name``_q <= name``_d;
module macro_top (input logic clk, input logic [3:0] a_d, output logic [3:0] a_q);
  `DECL_FF(a, 4)
  `FF_BODY(a)
  assign a_q = a_q;
endmodule
