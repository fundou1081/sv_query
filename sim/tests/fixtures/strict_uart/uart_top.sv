`timescale 1ns/1ps
module uart_top (
    input  wire clk_i,
    input  wire rst_ni,
    input  wire rx_i,
    input  wire [7:0] tx_data_i,
    output wire tx_o,
    output logic [7:0] rx_data_o,
    output logic       rx_ready_o
);
    sync_fifo #(.WIDTH(8), .SIZE(16)) rx_fifo (
        .clk_i(clk_i), .rst_ni(rst_ni),
        .push_i(1'b1), .pop_i(1'b0),
        .push_data_i(8'h0),
        .pop_data_o(rx_data_o),
        .full_o(), .empty_o(rx_ready_o)
    );
endmodule
