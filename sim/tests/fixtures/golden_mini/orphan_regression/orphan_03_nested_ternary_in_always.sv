// orphan_03: nested ternary inside always_ff
module orphan_03(
    input clk, rst_n,
    input [7:0] a, b, c,
    input sel_a, sel_b,
    output reg [7:0] y
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            y <= 8'd0;
        else
            y <= sel_a ? (sel_b ? a : b) : c;
    end
endmodule
