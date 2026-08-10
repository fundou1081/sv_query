// golden_dataflow_25_array_index.sv — 数组索引 + indexed part-select + 嵌套三目
// 检测目标: array indexing (multi-bit slice with constant indices), indexed
// part-select [base +: width], 嵌套 ternary mux. case26-28 没覆盖的 SV 数据流
// 模式 (case3 只测了单 bit slice [15:8], case28 是 function+bitop+mux, 没 array).
module array_index(
    input clk, rst_n,
    input [31:0] bus,
    input [1:0]   sel,
    input [7:0]   a, b,
    output [7:0] y_lo,    // 低字节处理结果
    output [7:0] y_mid,   // 中字节处理结果
    output [7:0] y_hi     // 高字节 mux 结果
);
    // [array indexing] 4 个 byte-slice, 跟 byte addressing 一样
    wire [7:0] byte0 = bus[7:0];
    wire [7:0] byte1 = bus[15:8];
    wire [7:0] byte2 = bus[23:16];
    wire [7:0] byte3 = bus[31:24];

    // [indexed part-select] 跟 [base +: width] 等价的写法
    wire [7:0] part = bus[{sel, 3'b000} +: 8];   // sel 决定取哪 8 位

    // 低字节: byte0+byte1, 截断
    wire [8:0] sum_lo = byte0 + byte1;

    // 中字节: byte2 跟 a,b 复合运算
    wire [7:0] mix_mid = byte2 ^ (a + b);

    // 高字节: 嵌套三目 mux
    wire [7:0] mux_hi = (sel == 2'd0) ? byte3 :
                        (sel == 2'd1) ? part  :
                        (sel == 2'd2) ? byte0 : byte1;

    assign y_lo  = sum_lo[7:0];
    assign y_mid = mix_mid;
    assign y_hi  = mux_hi;
endmodule