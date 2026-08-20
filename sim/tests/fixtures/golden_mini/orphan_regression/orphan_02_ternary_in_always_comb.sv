// orphan_02: ternary inside always_comb + case
module orphan_02(
    input [1:0] mode,
    input sel_a, sel_b,
    input [7:0] a, b, c, d,
    output reg [7:0] y
);
    always @(*) begin
        case (mode)
            2'b00: y = sel_a ? a : b;
            2'b01: y = sel_b ? c : d;
            default: y = 8'd0;
        endcase
    end
endmodule