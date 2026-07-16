// two_flop_sync.sv — simplified cross-module async crossing
// (test_dataflow_latency_open_source.py)
// 
// Test wants: sub_a.data_a_i → sub_b.data_b_o (async, null latency)
// 
// Strategy: chain the two sub-modules via two_flop_sync with explicit port wiring

module sub_a(
    input  wire        clk_a, rst_n,
    input  wire        data_a_i,
    output reg         data_a_o
);
    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n) data_a_o <= 1'b0;
        else data_a_o <= data_a_i;
    end
endmodule

module sub_b(
    input  wire        clk_b, rst_n,
    input  wire        data_b_i,
    output reg         data_b_o
);
    reg sync_0, sync_1;
    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) begin
            sync_0 <= 1'b0;
            sync_1 <= 1'b0;
            data_b_o <= 1'b0;
        end else begin
            sync_0 <= data_b_i;
            sync_1 <= sync_0;
            data_b_o <= sync_1;
        end
    end
endmodule

module two_flop_sync(
    input  wire        clk_a, clk_b, rst_n,
    input  wire        data_in,
    output wire        data_out,
    // Extra test signal: trace through async crossing  
    output wire        bridge_signal
);
    wire async_wire;
    
    sub_a u_a(.clk_a(clk_a), .rst_n(rst_n), .data_a_i(data_in), .data_a_o(async_wire));
    sub_b u_b(.clk_b(clk_b), .rst_n(rst_n), .data_b_i(async_wire), .data_b_o(data_out));
    
    assign bridge_signal = async_wire;
endmodule
