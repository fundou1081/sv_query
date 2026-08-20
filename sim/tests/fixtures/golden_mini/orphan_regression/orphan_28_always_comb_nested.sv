// orphan_28: deeply nested ternary in always_comb (icache pattern)
module orphan_28(
    input [1:0] mode,
    input sel_a, sel_b, sel_c, sel_d,
    input [7:0] a, b, c, d,
    output reg [7:0] y
);
    always @(*) begin
        case (mode)
            2'b00: y = sel_a ? a : b;
            2'b01: y = sel_b ? (sel_c ? c : d) : 8'd0;
            2'b10: y = sel_d ? a : (sel_c ? b : c);
            default: y = 8'hFF;
        endcase
    end
endmodule