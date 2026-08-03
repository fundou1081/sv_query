// golden_dataflow_6_signed.sv — $signed 系统函数
module with_signed(
    input signed [7:0] a,
    input signed [7:0] b,
    output signed [15:0] y
);
    assign y = $signed(a) * $signed(b);   // 有符号乘法
endmodule
