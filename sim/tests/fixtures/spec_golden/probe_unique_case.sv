module probe_unique(input wire [1:0] sel, input wire [3:0] a, b, c, output reg [3:0] q);
  always_comb begin
    unique case (sel)
      2'd0: q = a;
      2'd1: q = b;
      default: q = c;
    endcase
  end
endmodule
