//==============================================================================
// test_multi.sv - 多模块测试
// 模块实例化场景
//==============================================================================

// 子模块: DFF
module dff (
    input  logic clk,
    input  logic rst_n,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

// 顶层模块
module top (
    input  logic clk,
    input  logic rst_n,
    input  logic din,
    output logic dout
);
    // 内部信号
    logic data;
    
    // 数据路径
    assign data = din;
    
    // 实例化 dff
    dff u_dff (
        .clk  (clk),
        .rst_n(rst_n),
        .d   (data),
        .q   (dout)
    );
endmodule
