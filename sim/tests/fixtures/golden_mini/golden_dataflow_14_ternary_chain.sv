// golden_dataflow_14_ternary_chain.sv — 三目输出作为下游运算输入
module ternary_chain(
    input [7:0] c, d, f,
    input b,
    output [7:0] h
);
    wire [7:0] a;
    assign a = b ? c : d;   // 三目选择
    assign h = a + f;        // 三目的输出 a 作为下游加法输入
endmodule
