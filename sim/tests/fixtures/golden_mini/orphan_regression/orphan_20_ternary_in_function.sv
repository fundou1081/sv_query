// orphan_20: ternary inside function definition
module orphan_20(
    input [7:0] a, b, c,
    input sel,
    output [7:0] y
);
    function [7:0] mux3(input sel, input [7:0] a, b, c);
        mux3 = sel ? a : b;
    endfunction
    assign y = mux3(sel, a, b, c);
endmodule
