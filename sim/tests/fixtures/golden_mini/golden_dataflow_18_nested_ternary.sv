// golden_dataflow_18_nested_ternary.sv — 多层嵌套三目
module nested_ternary(
    input sel_a, sel_b,
    input [7:0] a, b, c, d,
    output [7:0] y
);
    // y = sel_a ? (sel_b ? (a + b) : (a - b)) : (sel_b ? (c + d) : (c - d))
    assign y = sel_a
        ? (sel_b ? (a + b) : (a - b))
        : (sel_b ? (c + d) : (c - d));
endmodule
