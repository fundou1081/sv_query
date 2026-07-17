`timescale 1ns/1ps
// Minimal arbiter fixture (extracted pattern from ventus sm2cluster_arb).
// Round-robin arbiter with 4 clients. Compiles cleanly in pyslang.

module arbiter_4client(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [3:0]  req_i,
    output reg  [3:0]  grant_o,
    output reg  [1:0]  grant_idx_o
);
    reg [1:0] ptr;  // Round-robin pointer

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            grant_o <= 0;
            grant_idx_o <= 0;
            ptr <= 0;
        end else begin
            // Simple priority: start from ptr, find first request
            case (1'b1)
                req_i[ptr]:   grant_idx_o <= ptr;
                req_i[ptr+1]: grant_idx_o <= ptr + 1;
                req_i[ptr+2]: grant_idx_o <= ptr + 2;
                default:      grant_idx_o <= ptr;
            endcase
            grant_o <= 4'b1 << grant_idx_o;
            ptr <= ptr + 1;
        end
    end
endmodule


// Wrapper module (sm2cluster_arb-like pattern: top with arbiter + downstream)
module sm2cluster_arb(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [3:0]  cluster_req_i,
    output wire [3:0]  cluster_gnt_o,
    output wire [1:0]  selected_idx_o
);
    arbiter_4client arb_inst (
        .clk(clk),
        .rst_n(rst_n),
        .req_i(cluster_req_i),
        .grant_o(cluster_gnt_o),
        .grant_idx_o(selected_idx_o)
    );
endmodule
