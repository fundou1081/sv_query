// nested_not2.sv — else-if with negation nesting (test_dataflow_else_if_typo.py)
// 
// Test expectations:
//   in_a: !rst_n && !sel_a   (when else if !sel_a branch is hit)
//   in_b: !rst_n && sel_a && sel_b  (when sel_a negated THEN else if sel_b)
//   in_c: ??
//
// So in_a, in_b, in_c each appears in their own else-if branch.
module nested_not2(
    input  wire        rst_n, sel_a, sel_b, sel_c,
    input  wire [7:0]  in_a, in_b, in_c,
    output reg  [7:0]  out_o
);
    always @* begin
        if (!rst_n)
            out_o = 8'd0;
        else if (!sel_a)
            out_o = in_a;
        else if (sel_b)
            out_o = in_b;
        else
            out_o = in_c;
    end
endmodule
