// fixed_point_patterns.sv — 定点数截断/饱和/舍入 模式识别测试
//
// 涵盖 6 大类定点数精度控制模式:
//   1. 截断 (truncation): 高位丢掉, 低位保留
//   2. 饱和 (saturation): 超出范围 clamp
//   3. 舍入 (rounding): +0.5 后截断 / RNE
//   4. 符号扩展 (sign extension)
//   5. 位拼接重排 (bit reordering)
//   6. 条件选择 (MUX/sel-based precision)

`timescale 1ns/1ps
module fixed_point_patterns(
    input  clk, rst_n,
    input  [15:0] a, b, c,
    input  [7:0]  coeff,
    output [7:0]  y_trunc_direct,    // 截断: 直接取低 8 位
    output [7:0]  y_trunc_implicit,   // 截断: 隐式 (16→8 赋值)
    output [7:0]  y_saturate_hi,      // 饱和: positive overflow → max
    output [7:0]  y_saturate_lo,      // 饱和: negative overflow → 0
    output [7:0]  y_round_half_up,    // 舍入: +0.5 → 进位
    output [7:0]  y_round_rne,        // 舍入: round-to-nearest-even
    output [7:0]  y_sign_extend,      // 符号扩展: {{8{a[7]}}, a[7:0]}
    output [7:0]  y_clamp,            // clamp: 三元条件限定范围
    output [7:0]  y_shift_round,      // 移位舍入: (a + (1<<(shift-1))) >>> shift
    output [15:0] y_mul_trunc,        // 乘法截断: 32→16
    output [15:0] y_mac               // MAC: 乘累加 → 截断
);

    // ========== 1. 截断 (Truncation) ==========

    // 1a: 直接 bit-select 截断
    assign y_trunc_direct = a[7:0];

    // 1b: 隐式截断 — 16bit 表达式赋给 8bit output
    wire [15:0] sum_16 = a + b;
    assign y_trunc_implicit = sum_16;


    // ========== 2. 饱和 (Saturation) ==========

    // 2a: 上饱和 — overflow → MAX
    wire [15:0] sum_ab = a + b;
    assign y_saturate_hi = (sum_ab > 16'd255) ? 8'd255 : sum_ab[7:0];

    // 2b: 下饱和 — underflow → 0 (unsigned)
    assign y_saturate_lo = (a < b) ? 8'd0 : (a - b);


    // ========== 3. 舍入 (Rounding) ==========

    // 3a: Round-half-up: (val + 0.5*LSB_bit) 然后截断
    // 等价于: (val + (1 << (shift-1))) >>> shift
    wire [15:0] sum_ac = a + c;
    assign y_round_half_up = (sum_ac + 16'd128) >>> 8;

    // 3b: Round-to-nearest-even (RNE)
    // prod[23:8] + prod[7] — tie-breaking to even
    wire [23:0] mul_prod = a * b;
    assign y_round_rne = mul_prod[15:8] + mul_prod[7];


    // ========== 4. 符号扩展 ==========

    // 4a: 显式符号扩展复制
    assign y_sign_extend = {{8{a[7]}}, a[7:0]};


    // ========== 5. Clamp / 范围限定 ==========

    // 5a: 三元 clamp
    wire [15:0] diff = a - b;
    assign y_clamp = (diff > 16'd200) ? 8'd200 :
                     (diff < 16'd10)  ? 8'd10  :
                      diff[7:0];


    // ========== 6. 移位舍入 ==========

    // 6a: 通用移位舍入公式
    wire [15:0] half = 16'd1 << (coeff - 1);
    assign y_shift_round = (a + half) >>> coeff;


    // ========== 7. 乘累加 (MAC) ==========

    // 7a: MAC = a*b + c, 32bit 截断到 16bit
    wire [31:0] mac_full = a * b + c;
    assign y_mac = mac_full[15:0];


    // ========== 8. 乘法截断 ==========

    assign y_mul_trunc = a * b;

endmodule
