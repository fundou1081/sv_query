`timescale 1ns/1ps
// Top module: aggregates sub_aggregator (multi-level hierarchy pattern)
module top_minimal(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_i,
    output wire        ready_o,
    output wire [7:0]  data_o
);
    // Pipeline chain through 3 modules: top → sub → leaf
    sub_aggregator sa1 (
        .clk(clk),
        .rst_n(rst_n),
        .valid_i(valid_i),
        .ready_o(ready_o),
        .data_i(8'hAB),
        .sum_o(data_o)
    );
endmodule


// [FIX 2026-07-17] Synchronizer module for NaplesPU-style multi-CDC testing.
// Pattern extracted from NaplesPU/NaplesPU/src/deploy/uart/synchronizer.sv.
// - 2-flop synchronizer with async input (as recommended for multi-clock CDC)
// - pyslang-compiles cleanly (no partial AST issues)
module synchronizer(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        async_i,
    output reg         sync0,        // First flop (metastability capture)
    output reg         sync1,        // Second flop (stable)
    output reg  [7:0]  data_o        // 8-bit synchronized data
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync0 <= 0;
            sync1 <= 0;
            data_o <= 0;
        end else begin
            sync0 <= async_i;
            sync1 <= sync0;
            data_o <= {sync0, sync1, async_i, async_i, async_i, 3'b0};  // demonstrates CDC pattern
        end
    end
endmodule
