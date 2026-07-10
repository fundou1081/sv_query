`timescale 1ns/1ps
// [Golden Testcase 3] DANGLING — reg 'unused_reg' is written but never read
// Expected: 1 DANGLING anomaly for 'unused_reg'
module dangling (
    input  wire clk_i,
    input  wire rst_ni,
    input  wire [7:0] data_i,
    output wire [7:0] data_o
);
    reg [7:0] data_reg;
    reg [7:0] unused_reg;  // DANGLING: written but never read

    always @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            data_reg  <= 8'h0;
            unused_reg <= 8'h0;
        end else begin
            data_reg   <= data_i;
            unused_reg <= data_i;  // written every cycle
        end
    end

    assign data_o = data_reg;  // data_reg is read; unused_reg is NOT
endmodule
