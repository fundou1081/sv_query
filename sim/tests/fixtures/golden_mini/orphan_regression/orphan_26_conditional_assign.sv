// orphan_26: ternary in assign with deep bit-select
module orphan_26(
    input sel,
    input [31:0] data,
    output [7:0] y
);
    assign y = sel ? data[7:0] : data[15:8];
endmodule
