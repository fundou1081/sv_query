// sync_fifo.sv — sync FIFO with 2 stages
// (test_dataflow_latency_open_source.py)
// 
// Test expects:
// - p1: push_data_i → pop_data_o, 2 cycle, sync
// - p5: stage_breakdown with 2 segments
// - golden_latency_sync_fifo: 2 cycle stable
// 
// Keys:
// - pop_data_o is a wire alias of data_out
// - Stage breakdown collapses reg → output_port

module sync_fifo(
    input  wire        clk, rst_n,
    input  wire        push_data_i,
    input  wire        wr_en, rd_en,
    output wire        full, empty,
    output wire        pop_data_o,
    output reg  [7:0]  data_out
);
    reg [7:0] reg_stage1;
    
    assign full = 1'b0;
    assign empty = 1'b0;
    assign pop_data_o = data_out;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_stage1 <= 8'd0;
            data_out  <= 8'd0;
        end else begin
            if (wr_en) reg_stage1 <= push_data_i;
            if (rd_en) data_out <= reg_stage1;
        end
    end
endmodule
