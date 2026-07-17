`timescale 1ns/1ps
// Minimal scheduler: extracted pattern from ventus Scheduler
// - Top module Scheduler with 7 sub-instances (SourceA, sourceD, sinkA, sinkD, banked_store, Listbuffer, directory_test)
// - Pipeline registers (20+) to test stage detection
// - Control signals (valid/ready) for chain features
// - Sub-module wrapper pattern (instance + port mapping)

module Scheduler_minimal(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        phy_tx_start,
    input  wire        bram_din,
    input  wire        result_iq_hold,
    output wire        phy_tx_done,
    output wire        phy_tx_started,
    output wire        bram_addr,
    output wire        result_iq_valid
);
    // Internal pipeline registers (simulating 20-stage pipeline)
    reg [7:0] s0_reg, s1_reg, s2_reg, s3_reg, s4_reg;
    reg [7:0] s5_reg, s6_reg, s7_reg, s8_reg, s9_reg;
    reg [7:0] s10_reg, s11_reg, s12_reg, s13_reg, s14_reg;
    reg [7:0] s15_reg, s16_reg, s17_reg, s18_reg, s19_reg;
    reg [7:0] state_q;

    // Forward declarations (must be before sub-instance usage)
    wire [7:0] s_final;

    // Sub-instances (mirror Scheduler pattern)
    SourceA  SourceA_dut (.clk(clk), .rst_n(rst_n), .phy_tx_start(phy_tx_start), .data_o(s0_reg));
    sourceD  sourceD_dut (.clk(clk), .rst_n(rst_n), .s_final_req(s_final), .data_o(s5_reg));
    sinkA    sinkA_dut   (.clk(clk), .rst_n(rst_n), .data_i(s10_reg), .phy_tx_done(phy_tx_done));
    sinkD    sinkD_dut   (.clk(clk), .rst_n(rst_n), .data_i(s15_reg), .result_q(s19_reg));
    banked_store banked_store_dut (.clk(clk), .rst_n(rst_n), .bram_addr(bram_addr));
    Listbuffer Listbuffer_dut (.clk(clk), .rst_n(rst_n), .data_in(s1_reg));
    directory_test directory_test_dut (.clk(clk), .rst_n(rst_n), .is_invalidate_reg(state_q));

    // Valid/ready control signals
    wire valid_in, ready_in;
    wire valid_out, ready_out;

    assign valid_in = phy_tx_start;
    assign ready_out = ready_in;

    // Internal pipeline logic
    wire [7:0] s_final;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s0_reg <= 0; s1_reg <= 0; s2_reg <= 0; s3_reg <= 0; s4_reg <= 0;
            s5_reg <= 0; s6_reg <= 0; s7_reg <= 0; s8_reg <= 0; s9_reg <= 0;
            s10_reg <= 0; s11_reg <= 0; s12_reg <= 0; s13_reg <= 0; s14_reg <= 0;
            s15_reg <= 0; s16_reg <= 0; s17_reg <= 0; s18_reg <= 0; s19_reg <= 0;
            state_q <= 0;
        end else begin
            s0_reg <= bram_din;
            s1_reg <= s0_reg;
            s2_reg <= s1_reg;
            s3_reg <= s2_reg;
            s4_reg <= s3_reg;
            s5_reg <= s4_reg;
            s6_reg <= s5_reg;
            s7_reg <= s6_reg;
            s8_reg <= s7_reg;
            s9_reg <= s8_reg;
            s10_reg <= s9_reg;
            s11_reg <= s10_reg;
            s12_reg <= s11_reg;
            s13_reg <= s12_reg;
            s14_reg <= s13_reg;
            s15_reg <= s14_reg;
            s16_reg <= s15_reg;
            s17_reg <= s16_reg;
            s18_reg <= s17_reg;
            s19_reg <= s18_reg;
            state_q <= state_q + 1;
        end
    end

    assign phy_tx_started = s0_reg[0];
    assign result_iq_valid = valid_out && ready_out;
    assign s_final = s19_reg;

endmodule

// Sub-module stubs (minimal compilable definitions)
module SourceA(
    input  wire clk,
    input  wire rst_n,
    input  wire phy_tx_start,
    output reg  [7:0] data_o
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) data_o <= 0;
        else data_o <= phy_tx_start ? 8'hAB : data_o;
    end
endmodule

module sourceD(
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] s_final_req,
    output reg  [7:0] data_o
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) data_o <= 0;
        else data_o <= s_final_req;
    end
endmodule

module sinkA(
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] data_i,
    output wire phy_tx_done
);
    reg done_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) done_q <= 0;
        else done_q <= |data_i;
    end
    assign phy_tx_done = done_q;
endmodule

module sinkD(
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] data_i,
    output wire [7:0] result_q
);
    assign result_q = data_i;
endmodule

module banked_store(
    input  wire clk,
    input  wire rst_n,
    output reg  [9:0] bram_addr
);
    reg [9:0] addr_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) addr_q <= 0;
        else addr_q <= addr_q + 1;
    end
    assign bram_addr = addr_q;
endmodule

module Listbuffer(
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] data_in
);
    reg [7:0] buf [0:3];
    always @(posedge clk) buf[0] <= data_in;
endmodule

module directory_test(
    input  wire clk,
    input  wire rst_n,
    output reg  [1:0] is_invalidate_reg
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) is_invalidate_reg <= 0;
        else is_invalidate_reg <= is_invalidate_reg + 1;
    end
endmodule
