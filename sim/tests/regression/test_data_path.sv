// 示例模块：带 SVA 和 Covergroup 的数据通路
module data_path #(
    parameter WIDTH = 8
)(
    input  logic             clk,
    input  logic             rst_n,
    // 输入接口
    input  logic [WIDTH-1:0] din,
    input  logic             din_valid,
    output logic             din_ready,
    // 输出接口
    output logic [WIDTH-1:0] dout,
    output logic             dout_valid,
    input  logic             dout_ready,
    // 配置
    input  logic [1:0]       mode
);

    // ---- 内部信号 ----
    logic [WIDTH-1:0] stage1_data;
    logic             stage1_valid;
    logic [WIDTH-1:0] stage2_data;
    logic             stage2_valid;
    logic [WIDTH-1:0] result;
    logic             result_valid;
    logic             pipeline_stall;

    // ---- 流控 ----
    assign pipeline_stall = stage2_valid && !dout_ready;
    assign din_ready      = !pipeline_stall;

    // ---- Stage 1: 输入锁存 ----
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage1_data  <= '0;
            stage1_valid <= 1'b0;
        end else begin
            if (din_valid && din_ready) begin
                stage1_data  <= din;
                stage1_valid <= 1'b1;
            end else if (!pipeline_stall) begin
                stage1_valid <= 1'b0;
            end
        end
    end

    // ---- Stage 2: 处理 ----
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage2_data  <= '0;
            stage2_valid <= 1'b0;
        end else begin
            if (!pipeline_stall) begin
                stage2_data  <= stage1_data;
                stage2_valid <= stage1_valid;
            end
        end
    end

    // ---- Stage 3: 输出 ----
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result       <= '0;
            result_valid <= 1'b0;
        end else begin
            if (!pipeline_stall) begin
                case (mode)
                    2'b00: result <= stage2_data;
                    2'b01: result <= stage2_data + 1;
                    2'b10: result <= stage2_data << 1;
                    2'b11: result <= ~stage2_data;
                endcase
                result_valid <= stage2_valid;
            end
        end
    end

    assign dout       = result;
    assign dout_valid = result_valid;

    // ---- SVA 断言 ----
    property p_valid_ready;
        @(posedge clk) din_valid && din_ready |-> ##2 dout_valid;
    endproperty

    property p_stall_no_data_loss;
        @(posedge clk) disable iff (!rst_n) stage2_valid && pipeline_stall |=> stage2_valid;
    endproperty

    property p_mode_stable;
        @(posedge clk) din_valid && din_ready |-> mode == 2'b00;
    endproperty

    assert property (p_valid_ready);
    assert property (p_stall_no_data_loss);
    assert property (p_mode_stable);

    // ---- 功能覆盖 ----
    covergroup cg_data_path @(posedge clk);
        cp_mode: coverpoint mode {
            bins pass   = {0};
            bins inc    = {1};
            bins shift  = {2};
            bins invert = {3};
        }
        cp_valid: coverpoint din_valid;
        cp_ready: coverpoint din_ready;
        cx_mode_valid: cross cp_mode, cp_valid;
    endgroup

    cg_data_path cov = new();

endmodule
