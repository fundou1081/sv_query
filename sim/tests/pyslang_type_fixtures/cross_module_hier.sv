// cross_module_hier.sv - 跨 module 测试 fixture
// 验证 parse_width_from_pyslang 找子模块 signal
// Hierarchical names: top.sub.signal, sub.signal (auto-detect top)
package hier_pkg;
    typedef enum logic [1:0] {
        IDLE = 2'd0,
        BUSY = 2'd1,
        DONE = 2'd2
    } state_t;
endpackage

module sub #(
    parameter int WIDTH = 8,
    parameter int DEPTH = 4
)(
    input                       clk,
    input                       rst_n,
    input                       enable_i,
    input  [WIDTH-1:0]          data_i,
    output logic [WIDTH-1:0]    data_o,
    output logic                valid_o,
    output logic                ready_o,
    output logic [$clog2(DEPTH)-1:0]  depth_idx_o  // [W=2] $clog2 derived
);

    assign ready_o  = enable_i;
    assign valid_o  = enable_i;
    assign data_o  = data_i;
    assign depth_idx_o = $clog2(DEPTH) - 1;  // placeholder

endmodule

module middle #(
    parameter int WIDTH = 16
)(
    input                       clk,
    input                       rst_n,
    input  [WIDTH-1:0]          data_i,
    output logic [WIDTH-1:0]    data_o,
    input                       valid_i
);

    logic [WIDTH-1:0] pipe_q;
    logic             valid_q;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pipe_q  <= '0;
            valid_q <= 1'b0;
        end else if (valid_i) begin
            pipe_q  <= data_i;
            valid_q <= 1'b1;
        end
    end

    sub #(.WIDTH(WIDTH), .DEPTH(4)) u_sub (
        .clk(clk), .rst_n(rst_n),
        .enable_i(valid_q),
        .data_i(pipe_q),
        .data_o(data_o),
        .valid_o(), .ready_o(),
        .depth_idx_o()
    );

endmodule

module top_hier #(
    parameter int DATA_WIDTH = 32
)(
    input                              clk,
    input                              rst_n,
    input                              enable_i,
    input  [DATA_WIDTH-1:0]            din,
    input                              valid_i,
    output logic [DATA_WIDTH-1:0]      dout,
    output logic                       ready_o
);

    logic [DATA_WIDTH-1:0] mid_data;
    logic                 mid_valid;

    // top 直接 instantiate middle
    middle #(.WIDTH(DATA_WIDTH)) u_middle (
        .clk(clk), .rst_n(rst_n),
        .data_i(din), .data_o(mid_data),
        .valid_i(valid_i)
    );

    // top 也有自己的 state (FSM)
    typedef enum logic [1:0] {
        TOP_IDLE  = 2'd0,
        TOP_BUSY  = 2'd1,
        TOP_DONE  = 2'd2
    } top_state_t;

    top_state_t state_q;
    logic [3:0] counter_q;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q   <= TOP_IDLE;
            counter_q <= '0;
        end else if (enable_i) begin
            state_q   <= TOP_BUSY;
            counter_q <= counter_q + 1;
        end
    end

    assign dout    = mid_data;
    assign ready_o = (state_q == TOP_IDLE);

endmodule
