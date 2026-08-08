// case28: 函数多级返回 + 位反转/拼接/掩码/奇偶校验混合
// golden_func_bitmix 测试:
//   - bit_rev (function): 位反转
//   - parity_func (function): 奇偶校验 (a&b)+(a|b)
//   - sat_mul (function): 饱和乘法 (a*b > 8'hff ? 8'hff : a*b)
//   - 顶层: mask & bit_rev(a) | sat_mul(a,b); parity = parity_func(a)^parity_func(b)
//   - wide_out: {4'd0, a[3:0]} if !flag else (b^c) (sel: flag)
//   - y: (mask & bit_rev(a)) | sat_mul(a,b)

module golden_func_bitmix (
    input  [7:0] mask,
    input  [7:0] a,
    input  [7:0] b,
    input  [7:0] c,
    input        flag,
    output [7:0] y,
    output       parity,
    output [7:0] wide_out
);

    function [7:0] bit_rev;
        input [7:0] x;
        begin
            bit_rev = {x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7]};
        end
    endfunction

    function parity_func;
        input [7:0] x;
        input [7:0] y;
        begin
            parity_func = ((x & y) | (x ^ y)) != 8'h00;
        end
    endfunction

    function [7:0] sat_mul;
        input [7:0] x;
        input [7:0] y;
        reg [15:0] product;
        begin
            product = x * y;
            sat_mul = (product > 16'h00ff) ? 8'hff : product[7:0];
        end
    endfunction

    wire [7:0] br_a;
    wire [7:0] sm_ab;
    wire [7:0] b_xor_c;

    assign br_a = bit_rev(a);
    assign sm_ab = sat_mul(a, b);
    assign y = (mask & br_a) | sm_ab;
    assign parity = parity_func(a, b) ^ parity_func(b, a);
    assign b_xor_c = b ^ c;
    assign wide_out = flag ? {4'd0, a[3:0]} : b_xor_c;

endmodule