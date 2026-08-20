// orphan_01: ternary inside always_ff (procedural) — render_ternary bug
module orphan_01(
    input clk, rst_n,
    input [7:0] a, b,
    input sel,
    output reg [7:0] y
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            y <= 8'd0;
        else
            y <= sel ? a : b;
    end
endmodule
