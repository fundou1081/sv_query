`timescale 1ns/1ps
module synchronizer #(parameter WIDTH = 1) (
    input  wire             clk_i,
    input  wire             rst_ni,
    input  wire [WIDTH-1:0] async_i,
    output logic[WIDTH-1:0] sync0_o
);
    logic [WIDTH-1:0] sync1;
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            sync1     <= '0;
            sync0_o   <= '0;
        end
        else begin
            sync1   <= async_i;
            sync0_o <= sync1;
        end
    end
endmodule
