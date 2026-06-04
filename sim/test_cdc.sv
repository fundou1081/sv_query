// ==============================================================================
// test_cdc.sv - Minimal CDC test (跨时钟域数据流, 故意未同步)
// ==============================================================================
// 场景:
//   - 时钟域 A (clk_a): always_ff 产生 reg_a
//   - 时钟域 B (clk_b): 通过组合逻辑直接采样 reg_a → dout_b
//   - 这是典型 CDC 违规: 跨域无同步器
// 用途:
//   - cdc analyze 命令测试
//   - 验证 --evidence flag 显示跨域点的源码位置
// ==============================================================================

module top (
    input  logic clk_a,
    input  logic clk_b,
    input  logic rst_n,
    input  logic din_a,
    output logic dout_b
);
    // 时钟域 A: reg_a 在 clk_a 下寄存
    logic reg_a;
    always_ff @(posedge clk_a or negedge rst_n) begin
        if (!rst_n)
            reg_a <= 1'b0;
        else
            reg_a <= din_a;
    end

    // 跨时钟域: reg_a (clk_a 域) → dout_b (clk_b 域), 无同步器
    always_ff @(posedge clk_b or negedge rst_n) begin
        if (!rst_n)
            dout_b <= 1'b0;
        else
            dout_b <= reg_a;  // <-- CDC 路径在此: clk_a → clk_b
    end

endmodule
