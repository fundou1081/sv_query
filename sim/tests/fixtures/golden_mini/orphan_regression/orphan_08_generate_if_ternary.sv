// orphan_08: ternary inside generate_if
module orphan_08 #(parameter MODE = 1) (
    input [7:0] a, b,
    output [7:0] y
);
    generate
        if (MODE == 1)
            assign y = (a > b) ? a : b;
        else
            assign y = (a < b) ? a : b;
    endgenerate
endmodule
