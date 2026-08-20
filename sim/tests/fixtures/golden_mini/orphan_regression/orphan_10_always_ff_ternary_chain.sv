// orphan_10: chained ternary in always_ff
module orphan_10(
    input clk, rst_n,
    input [1:0] sel,
    input [7:0] a, b, c, d,
    output reg [7:0] y
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            y <= 8'd0;
        else
            y <= sel[1] ? (sel[0] ? d : c) : (sel[0] ? b : a);
    end
endmodule
