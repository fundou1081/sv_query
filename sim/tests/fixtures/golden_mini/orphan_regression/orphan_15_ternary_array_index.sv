// orphan_15: ternary with array index access
module orphan_15(
    input sel,
    input [7:0] lut [0:3],
    input [1:0] idx,
    output [7:0] y
);
    assign y = sel ? lut[idx] : 8'd0;
endmodule
