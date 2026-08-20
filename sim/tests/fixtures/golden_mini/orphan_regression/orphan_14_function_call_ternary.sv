// orphan_14: ternary with function calls in branches
module orphan_14(
    input sel,
    input [7:0] a, b,
    output [7:0] y, z
);
    function [7:0] add1(input [7:0] x);
        return x + 1;
    endfunction
    assign y = sel ? add1(a) : b;
    assign z = sel ? (a + b) : 8'd0;
endmodule
