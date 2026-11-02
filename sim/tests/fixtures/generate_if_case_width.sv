module gen_leaf #(parameter W = 4) (input [W-1:0] i, output [W-1:0] o);
  reg [W-1:0] r;
  always_comb r = i;
  assign o = r;
endmodule

module top_if0 #(parameter MODE = 0) (input [15:0] a, output [15:0] y);
  localparam W = (MODE == 0) ? 8 : 4;
  generate
    if (MODE == 0) begin: g
      gen_leaf #(.W(W)) u(.i(a[W-1:0]), .o(y[W-1:0]));
    end else begin: other
      gen_leaf #(.W(W)) u(.i(a[W-1:0]), .o(y[W-1:0]));
    end
  endgenerate
endmodule

module top_case1 #(parameter MODE = 1) (input [15:0] a, output [15:0] y);
  localparam W = (MODE == 0) ? 2 : (MODE == 1) ? 4 : 8;
  generate
    case (MODE)
      0: begin: g0 gen_leaf #(.W(W)) u(.i(a[W-1:0]), .o(y[W-1:0])); end
      1: begin: g1 gen_leaf #(.W(W)) u(.i(a[W-1:0]), .o(y[W-1:0])); end
      default: begin: gd gen_leaf #(.W(W)) u(.i(a[W-1:0]), .o(y[W-1:0])); end
    endcase
  endgenerate
endmodule
