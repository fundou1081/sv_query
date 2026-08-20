// orphan_30: ternary with arithmetic in both branches
module orphan_30(
    input sel,
    input [7:0] a, b, c, d,
    output [7:0] y
);
    assign y = sel ? (a + b) : (c - d);
endmodule
