// golden_dataflow_3_slice.sv — 含截断/切片
module with_trunc(
    input [15:0] a, b,
    output [7:0] y_trunc,
    output [7:0] y_slice
);
    wire [15:0] sum = a + b;
    assign y_trunc = sum[7:0];   // 截断: 16b→8b
    assign y_slice = a[15:8];    // 切片: 高8位
endmodule
