// golden_dataflow_11_ternary_scope.sv — 三目 scope 测试
module ternary_scope(
    input cond,
    input [7:0] a, b,
    output [7:0] y,
    output [7:0] z
);
    assign y = cond ? a : b;              // 简单三目
    assign z = (a > b) ? (a - b) : 8'd0;  // 条件运算三目
endmodule
