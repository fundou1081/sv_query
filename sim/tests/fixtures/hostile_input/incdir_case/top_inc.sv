`include "defs.svh"
module top_inc (input logic clk, input logic [`WIDTH-1:0] d, output logic [`WIDTH-1:0] q);
  `MAKE_REG(data)
  always_ff @(posedge clk) data_q <= d;
  assign q = data_q;
endmodule
