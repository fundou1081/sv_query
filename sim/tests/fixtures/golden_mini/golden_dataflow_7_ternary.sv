// golden_dataflow_7_ternary.sv — 三目运算符
module with_ternary(
    input [7:0] a, b,
    input cond,
    output [7:0] y,
    output [7:0] z
);
    assign y = cond ? a : b;           // 三目选择
    assign z = (a > b) ? (a - b) : 0;  // 条件减法
endmodule
