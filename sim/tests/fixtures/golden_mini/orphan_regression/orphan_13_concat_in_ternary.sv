// orphan_13: ternary with concat {} in branches
module orphan_13(
    input sel,
    input [3:0] hi, lo,
    output [7:0] y
);
    assign y = sel ? {hi, lo} : 8'd0;
endmodule
