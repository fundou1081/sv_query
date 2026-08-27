module probe_gen_if_wire #(parameter USE = 1) (input wire [3:0] a, b, output wire [3:0] y);
  generate
    if (USE == 1) begin : g_use1
      wire prod1 = a * b;
    end
    else begin : g_use0
      wire prod0 = a + b;
    end
  endgenerate
  assign y = (USE == 1) ? g_use1.prod1 : g_use0.prod0;
endmodule
