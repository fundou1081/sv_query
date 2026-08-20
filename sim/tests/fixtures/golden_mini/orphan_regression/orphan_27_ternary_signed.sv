// orphan_27: ternary with $signed
module orphan_27(
    input sel,
    input signed [7:0] a, b,
    output signed [7:0] y
);
    assign y = sel ? $signed(a) : $signed(b);
endmodule
