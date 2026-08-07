// golden_dataflow_21_if_case_function.sv — if + case + function 三层混合
module if_case_function(
    input clk, rst_n,
    input [1:0] mode,
    input [7:0] a, b, c,
    output reg [7:0] y
);
    function [7:0] mul2(input [7:0] x);
        mul2 = x << 1;
    endfunction

    function [7:0] div2(input [7:0] x);
        div2 = x >> 1;
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            y <= 8'd0;
        end else begin
            case (mode)
                2'b00: y <= mul2(a);
                2'b01: y <= div2(b);
                2'b10: y <= (a > b) ? mul2(a) : div2(b);
                default: y <= mul2(div2(c));
            endcase
        end
    end
endmodule
