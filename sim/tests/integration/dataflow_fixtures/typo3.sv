// typo3.sv — 3 else-if chain (test_dataflow_else_if_typo.py)
module typo3(
    input  wire        sel_a, sel_b, sel_c,
    input  wire [7:0]  in_a, in_b, in_c,
    output reg  [7:0]  out_o
);
    always @* begin
        if (sel_a)
            out_o = in_a;
        else if (sel_b)
            out_o = in_b;
        else if (sel_c)
            out_o = in_c;
        else
            out_o = 8'd0;
    end
endmodule
