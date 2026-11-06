// Complex mux neighborhood: nested selects, shared conditions, register sink.
module mux_tree(
  input  logic [7:0] a, b, c, d,
  input  logic [1:0] sel,
  output logic [7:0] y
);
  logic [7:0] lo, hi;
  assign lo = sel[0] ? a : b;
  assign hi = sel[0] ? c : d;
  assign y  = sel[1] ? hi : lo;
endmodule

module top(
  input  logic [7:0] a, b, c, d,
  input  logic [1:0] sel,
  input  logic clk,
  output logic [7:0] q
);
  logic [7:0] y;
  mux_tree u(.a(a), .b(b), .c(c), .d(d), .sel(sel), .y(y));
  always_ff @(posedge clk) q <= y;
endmodule
