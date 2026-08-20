// orphan_21: case with default + ternary in always_ff
module orphan_21(
    input clk, rst_n,
    input [1:0] opcode,
    input sel_a, sel_b,
    input [7:0] a, b, c, d,
    output reg [7:0] y
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            y <= 8'd0;
        else
            case (opcode)
                2'b00: y <= sel_a ? a : b;
                2'b01: y <= sel_b ? c : d;
                default: y <= 8'hFF;
            endcase
    end
endmodule