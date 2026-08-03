// golden_dataflow_2_const.sv — 含常量运算
module with_const(
    input [7:0] a,
    output [7:0] y_add,
    output [7:0] y_shift
);
    assign y_add   = a + 8'd128;
    assign y_shift = a >> 2;
endmodule
