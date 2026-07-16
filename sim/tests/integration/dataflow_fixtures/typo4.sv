// typo4.sv — 4 else-if chain (test_dataflow_else_if_typo.py)
// 
// Test expects (NO rst_n - just sel_* chain):
//   in_a: sel_a
//   in_b: !sel_a && sel_b
//   in_c: !sel_a && !sel_b && sel_c
//   in_d: !sel_a && !sel_b && !sel_c && sel_d
module typo4(
    input  wire        sel_a, sel_b, sel_c, sel_d,
    input  wire [7:0]  in_a, in_b, in_c, in_d,
    output reg  [7:0]  out_o
);
    always @* begin
        if (sel_a)
            out_o = in_a;
        else if (sel_b)
            out_o = in_b;
        else if (sel_c)
            out_o = in_c;
        else if (sel_d)
            out_o = in_d;
        else
            out_o = 8'd0;
    end
endmodule
