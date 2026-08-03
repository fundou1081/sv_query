// golden_dataflow_7_ternary.sv — 三目运算符 (带嵌套)
module with_ternary(
    input [7:0] a, b, c,
    input sel_a, sel_b,
    output [7:0] y,
    output [7:0] z
);
    // 嵌套三目: sel_a 外层, (sel_b ? a : b) 内层
    assign y = sel_a ? (sel_b ? a : b) : c;
    // 简单三目, 对比
    assign z = sel_a ? a : b;
endmodule
