module probe_casex(input wire [1:0] sel, input wire [3:0] a, b, c, output reg [3:0] q);
  always_comb begin
    casex (sel)
      2'b1?: q = a;
      2'b?1: q = b;
      default: q = c;
    endcase
  end
endmodule
