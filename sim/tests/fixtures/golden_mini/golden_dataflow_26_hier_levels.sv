// case26: 层级模块数据流 — 子模块实例折叠
// golden_hier_top 包含 4 个子模块实例:
//   u_scale (level2_scale) — 乘法
//   u_off   (level2_offset) — 加法
//   u_clamp_u / u_clamp (level2_clamp × 2) — 限幅
// 期望: collapse_instances=True 后只显示模块 box + 跨模块端口连接

module level2_scale (
    input  [7:0] din,
    input  [7:0] gain,
    output [7:0] dout
);
    assign dout = din * gain;
endmodule

module level2_offset (
    input  [7:0] din,
    input  [7:0] offset,
    output [7:0] dout
);
    assign dout = din + offset;
endmodule

module level2_clamp (
    input  [10:0] din,
    output [7:0]  dout
);
    assign dout = (din > 11'd255) ? 8'd255 : din[7:0];
endmodule

module golden_hier_top (
    input  [7:0] data_in,
    input  [7:0] gain,
    input  [7:0] offset,
    input        sel,
    output [7:0] result
);
    wire [7:0] scaled;
    wire [7:0] offsetted;
    wire [7:0] clamped_w;
    wire [7:0] clamped;

    level2_scale u_scale (.din(data_in), .gain(gain), .dout(scaled));
    level2_offset u_off (.din(scaled), .offset(offset), .dout(offsetted));
    level2_clamp u_clamp_u (.din({3'b0, offsetted}), .dout(clamped_w));
    level2_clamp u_clamp   (.din({3'b0, offsetted}), .dout(clamped));

    assign result = sel ? clamped : data_in;
endmodule
