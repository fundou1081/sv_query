// orphan_11: case inside always_ff with ternary pattern
module orphan_11(
    input clk, rst_n,
    input [1:0] opcode,
    input [7:0] a, b, c, d,
    output reg [7:0] y
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            y <= 8'd0;
        else
            case (opcode)
                2'b00: y <= a + b;
                2'b01: y <= (a > b) ? a : b;
                2'b10: y <= c - d;
                default: y <= 8'd0;
            endcase
    end
endmodule
