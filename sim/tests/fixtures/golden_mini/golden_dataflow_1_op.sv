// golden_dataflow_1_op.sv — 简单二元运算
module simple_op(
    input [7:0] a, b,
    output [8:0] sum,
    output [15:0] prod
);
    assign sum = a + b;
    assign prod = a * b;
endmodule
