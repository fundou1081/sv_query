// golden_dataflow_12_ternary_mixed.sv — 三目+数据流复杂混合
module ternary_mixed(
    input [7:0] a, b, c, d, e,
    input sel, mode,
    output [7:0] y,
    output [7:0] z
);
    wire [7:0] sum_ab = a + b;        // 共用加法
    wire [7:0] sub_cd = c - d;        // 共用减法
    wire [7:0] prod_e  = e * 8'd3;    // 共用乘法+常量

    // 三目选择器: 分支内含运算
    assign y = sel ? (sum_ab + 8'd10) : (sub_cd >> 2);

    // 嵌套三目: mode 控制用哪个中间结果
    assign z = mode ? (sel ? sum_ab : prod_e) : sub_cd;
endmodule
