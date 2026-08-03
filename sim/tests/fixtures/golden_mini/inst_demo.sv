// inst_demo.sv — 包含实例化的测试文件 (用于 structure 图)
// 一个顶层模块实例化两个子模块
module sub_adder(
    input [7:0] a, b,
    output [8:0] sum
);
    assign sum = a + b;
endmodule

module sub_mult(
    input [7:0] x, y,
    output [15:0] prod
);
    assign prod = x * y;
endmodule

module inst_demo(
    input clk, rst_n,
    input [7:0] in_a, in_b, in_c,
    output [15:0] result
);
    wire [8:0] add_out;
    wire [15:0] mult_out;

    sub_adder u_adder (
        .a(in_a),
        .b(in_b),
        .sum(add_out)
    );

    sub_mult u_mult (
        .x(in_c),
        .y(add_out[7:0]),
        .prod(mult_out)
    );

    assign result = mult_out;
endmodule
