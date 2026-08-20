// orphan_12: ternary with == in condition (pa_fcnvt itof pattern)
module orphan_12(
    input [7:0] sh_src,
    input [7:0] a, b,
    output reg [7:0] y
);
    always @(*) begin
        y = (sh_src == 8'b1) ? a : b;
    end
endmodule
