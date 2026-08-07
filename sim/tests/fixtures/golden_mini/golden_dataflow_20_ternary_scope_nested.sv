// golden_dataflow_20_ternary_scope_nested.sv — 三目嵌套作用域 + 中间信号
module ternary_scope_nested(
    input [7:0] a, b, c, d,
    input [1:0] sel,
    output [7:0] y
);
    wire [7:0] t1 = (sel[0]) ? a : b;        // 中间三目结果
    wire [7:0] t2 = (sel[1]) ? c : d;        // 中间三目结果
    wire [7:0] sum = t1 + t2;                // 中间三目结果相加
    assign y = (sum > 8'd200) ? 8'd200 : sum;
endmodule
