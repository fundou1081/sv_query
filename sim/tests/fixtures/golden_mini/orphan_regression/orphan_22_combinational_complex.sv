// orphan_22: complex combinational with nested ternary + arithmetic
module orphan_22(
    input sel1, sel2,
    input [7:0] a, b, c, d, e, f,
    output [7:0] y
);
    wire [7:0] sum1 = a + b;
    wire [7:0] sum2 = c + d;
    wire [7:0] sum3 = e + f;
    assign y = sel1 ? (sel2 ? sum1 + sum2 : sum2 + sum3) : (sum1 + sum3);
endmodule
