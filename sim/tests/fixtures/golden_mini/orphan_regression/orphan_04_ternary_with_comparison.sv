// orphan_04: ternary where cond has == comparison (pa_fcnvt pattern)
module orphan_04(
    input [31:0] ff1_sh_src,
    input [31:0] a, b,
    output reg [31:0] y
);
    always @(*) begin
        y = (ff1_sh_src[31:0] == 32'b1) ? a : b;
    end
endmodule
