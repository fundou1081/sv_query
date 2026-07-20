`timescale 1ns/1ps
// [V6 Golden Test 2026-07-20] Multi-stage calc chain
// - Multiple intermediate signals
// - Deep fan-out and fan-in for downstream BFS
// - Exercises use case B (--focus) at varied depths
module calc_chain(
    input  clk,
    input  [7:0] a, b, c,
    output [7:0] y,
    output [7:0] z,
    output [7:0] w
);
    reg [7:0] s1, s2, s3, s4, s5;

    always @(posedge clk) begin
        s1 <= a + b;
        s2 <= s1 + 1;
        s3 <= s2 * 2;
        s4 <= s3 - c;
        s5 <= s4 & 8'hff;
    end

    // 多个 outputs 从 s3/s4/s5 拉出
    assign y = s3;
    assign z = s4;
    assign w = s5;
endmodule
