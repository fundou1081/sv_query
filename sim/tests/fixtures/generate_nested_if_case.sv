module leaf #(parameter W = 4) (input [W-1:0] i, output [W-1:0] o);
  reg [W-1:0] r;
  always_comb r = i;
  assign o = r;
endmodule

module top_nested_if (input [15:0] a, output [15:0] y);
  genvar g;
  generate
    for (g = 0; g < 4; g = g + 1) begin: blk
      if (g % 2 == 0) begin: even
        leaf #(.W(g + 2)) u(.i(a[g +: 2]), .o(y[g +: 2]));
      end else begin: odd
        leaf #(.W(g + 4)) u(.i(a[g +: 2]), .o(y[g +: 2]));
      end
    end
  endgenerate
endmodule

module top_nested_case (input [15:0] a, output [15:0] y);
  genvar g;
  generate
    for (g = 0; g < 3; g = g + 1) begin: blk
      case (g)
        0: begin: c0 leaf #(.W(2)) u(.i(a[0 +: 2]), .o(y[0 +: 2])); end
        1: begin: c1 leaf #(.W(4)) u(.i(a[2 +: 2]), .o(y[2 +: 2])); end
        default: begin: cd leaf #(.W(8)) u(.i(a[4 +: 2]), .o(y[4 +: 2])); end
      endcase
    end
  endgenerate
endmodule
