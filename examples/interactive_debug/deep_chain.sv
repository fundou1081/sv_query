// Interactive debug scenario 1: deep drive chain across 4 hierarchy levels.
module leaf #(parameter W = 8) (
  input  logic clk,
  input  logic [W-1:0] d,
  output logic [W-1:0] q
);
  always_ff @(posedge clk) q <= d;
endmodule

module stage2 (
  input  logic clk,
  input  logic [7:0] d,
  input  logic sel,
  output logic [7:0] q
);
  logic [7:0] leaf_q;
  logic [7:0] mixed;
  leaf u_leaf(.clk(clk), .d(sel ? d : ~d), .q(leaf_q));
  assign mixed = leaf_q ^ 8'hA5;
  assign q = mixed;
endmodule

module mid (
  input  logic clk,
  input  logic [7:0] d,
  input  logic sel,
  output logic [7:0] q
);
  stage2 u_stage(.clk(clk), .d(d), .sel(sel), .q(q));
endmodule

module top (
  input  logic clk,
  input  logic [7:0] din,
  input  logic sel,
  output logic [7:0] dout
);
  logic [7:0] mid_q;
  mid u_mid(.clk(clk), .d(din), .sel(sel), .q(mid_q));
  assign dout = mid_q;
endmodule
