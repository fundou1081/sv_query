// orphan_32: complex chained ternary with arithmetic and bit-select
module orphan_32(
    input [1:0] sel,
    input [7:0] a, b, c, d, e, f, g, h,
    output [7:0] y
);
    wire [7:0] ab = a + b;
    wire [7:0] cd = c - d;
    wire [7:0] ef = e & f;
    wire [7:0] gh = g | h;
    assign y = sel[1] ?
               (sel[0] ? (ab + cd) : (ef - gh)) :
               (sel[0] ? (ab - gh) : (ef + cd));
endmodule
