// golden_dataflow_23_ternary_deep_chain.sv — 深链三目 + 位宽截断 + 常量比较
module ternary_deep_chain(
    input [7:0] a, b, c,
    input sel1, sel2, sel3,
    output [7:0] y,
    output overflow
);
    wire [15:0] sum = a + b;                       // 宽中间信号
    wire [15:0] prod = a * c;                      // 宽乘积
    wire [7:0] s1 = sel1 ? sum[7:0] : prod[7:0];   // 三目 + bit slice
    wire [7:0] s2 = sel2 ? s1 : (a - b);           // 链式三目
    assign y = sel3 ? s2 : (prod > 16'd3000 ? 8'd255 : s2);
    assign overflow = (sum > 16'd255) | (prod > 16'd65500);
endmodule
