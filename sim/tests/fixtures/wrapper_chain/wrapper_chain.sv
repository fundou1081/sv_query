`timescale 1ns/1ps
// Minimal wrapper chain pattern extracted from openofdm_tx:
// - Top wrapper module with AXI-like IO ports + a simple assign passthrough
// - Inner submodule with 3-stage pipeline (data_i → stage1 → stage2 → stage3 → data_o)
// - chain command can trace:
//   1. Simple assign passthrough (s_axi_arvalid_i → s_axi_rlast_o) — direct
//   2. Multi-hop pipeline path (data_i → ... → data_o) — through inner_proc

module wrapper_chain(
    input  wire        clk,
    input  wire        rst_n,
    // External AXI-like ports (with valid/ready)
    input  wire        s_axi_awvalid_i,
    input  wire        s_axi_wvalid_i,
    input  wire        s_axi_bready_i,
    input  wire        s_axi_arvalid_i,
    input  wire        s_axi_rready_i,
    output wire        s_axi_awready_o,
    output wire        s_axi_wready_o,
    output wire        s_axi_bvalid_o,
    output wire        s_axi_arready_o,
    output wire        s_axi_rvalid_o,
    output wire        s_axi_rlast_o,
    output wire [1:0]  s_axi_bresp_o,
    output wire [1:0]  s_axi_rresp_o,
    input  wire        phy_tx_start_i,
    output wire        phy_tx_done_o,
    input  wire [63:0] bram_din_i,
    output wire [63:0] bram_dout_o,        // data_o output
    output wire [9:0]  bram_addr_o,        // also has addr path
    output wire        result_iq_valid_o
);
    // Inner module data path: bram_din_i → stage1_data → stage2_data → stage3_data → bram_dout_o
    // + bram_addr_o comes from counter
    inner_proc inner_proc_dut (
        .clk(clk),
        .rst_n(rst_n),
        .data_i(bram_din_i),
        .data_o(bram_dout_o),
        .addr_o(bram_addr_o),
        .phy_tx_start(phy_tx_start_i)
    );

    // Pass-through ports (assign) - simple wrapper passthrough, creates direct chain paths
    assign s_axi_rvalid_o = s_axi_bready_i;
    assign s_axi_rlast_o  = s_axi_arvalid_i;
    assign s_axi_bresp_o  = 2'b00;
    assign s_axi_rresp_o  = 2'b00;

    // Other outputs unused but kept for valid module signature
    assign s_axi_awready_o = s_axi_arvalid_i;
    assign s_axi_wready_o  = s_axi_wvalid_i;
    assign s_axi_bvalid_o  = s_axi_awvalid_i;
    assign s_axi_arready_o = s_axi_rready_i;
    assign phy_tx_done_o   = result_iq_valid_o;
    assign result_iq_valid_o = s_axi_rready_i;

endmodule


// Inner submodule: 3-stage pipeline with data_o chain
module inner_proc(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [63:0] data_i,
    output wire [63:0] data_o,
    output wire [9:0]  addr_o,
    input  wire        phy_tx_start
);
    // Pipeline registers (3 stages, data path drives data_o)
    reg [63:0] stage1_data;
    reg [63:0] stage2_data;
    reg [63:0] stage3_data;

    // Address counter (drives addr_o)
    reg [9:0] addr_counter;

    assign data_o = stage3_data;
    assign addr_o = addr_counter;

    // Pipeline logic — data_i flows through 3 stages
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage1_data <= 0;
            stage2_data <= 0;
            stage3_data <= 0;
            addr_counter <= 0;
        end else begin
            stage1_data <= data_i;
            stage2_data <= stage1_data;
            stage3_data <= stage2_data;
            if (phy_tx_start) addr_counter <= addr_counter + 1;
        end
    end
endmodule
