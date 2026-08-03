// golden_dataflow_12_ternary_complex.sv — 三目与数据流混合
module ternary_mixed(
    input clk,
    input [7:0] a, b, c, d,
    input sel,
    output [7:0] y
);
    wire [7:0] sum_ab = a + b;        // 共用加法（也参与三目）
    wire [7:0] sub_cd = c - d;        // 共用减法（也参与三目）

    // 三目选择器，分支内还有运算
    assign y = sel ? (sum_ab + 8'd10) : (sub_cd >> 2);
endmodule
