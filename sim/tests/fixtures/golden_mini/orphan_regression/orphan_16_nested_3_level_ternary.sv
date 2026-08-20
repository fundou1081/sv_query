// orphan_16: 3-level nested ternary in always_ff
module orphan_16(
    input clk, rst_n,
    input [1:0] sel1, sel2,
    input [7:0] a, b, c, d,
    output reg [7:0] y
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            y <= 8'd0;
        else
            y <= sel1[1] ? (sel1[0] ? (sel2[0] ? a : b) : (sel2[0] ? c : d)) : 8'd0;
    end
endmodule
