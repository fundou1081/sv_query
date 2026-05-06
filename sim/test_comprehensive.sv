//==============================================================================
// test_comprehensive.sv - 全面的 SystemVerilog 验证测试
// 严格遵循项目铁律13: 先定义金标准
//==============================================================================

//==============================================================================
// Case 1: 基础组合逻辑
// 金标准: data_out = din (assign)
//==============================================================================
module combo_basic (
    input  wire din,
    output wire data_out
);
    assign data_out = din;
endmodule

//==============================================================================
// Case 2: 基础时序逻辑  
// 金标准: q <= d (非阻塞时钟)
//==============================================================================
module seq_basic (
    input  wire clk,
    input  wire rst_n,
    input  wire d,
    output wire q
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

//==============================================================================
// Case 3: 异步复位
// 金标准: q <= rst_n ? d : 1'b0
//==============================================================================
module seq_async_rst (
    input  wire clk,
    input  wire rst_n,
    input  wire d,
    output wire q
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

//==============================================================================
// Case 4: 同步复位
// 金标准: if (rst_n) q <= d; else q <= 1'b0;
//==============================================================================
module seq_sync_rst (
    input  wire clk,
    input  wire rst_n,
    input  wire d,
    output wire q
);
    always_ff @(posedge clk) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

//==============================================================================
// Case 5: 组合always块
// 金标准: q = a & b
//==============================================================================
module combo_always (
    input  wire a,
    input  wire b,
    output wire q
);
    always_comb begin
        q = a & b;
    end
endmodule

//==============================================================================
// Case 6: 多驱动源 (mux)
// 金标准: q = sel ? a : b
//==============================================================================
module seq_mux (
    input  wire clk,
    input  wire rst_n,
    input  wire a,
    input  wire b,
    input  wire sel,
    output wire q
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else if (sel)
            q <= a;
        else
            q <= b;
    end
endmodule

//==============================================================================
// Case 7: 内部信号 (wire)
// 金标准: data -> internal -> q1, q2
//==============================================================================
module seq_internal (
    input  wire clk,
    input  wire rst_n,
    input  wire din,
    output wire q1,
    output wire q2
);
    wire internal;
    
    assign internal = din;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q1 <= 1'b0;
            q2 <= 1'b0;
        end else begin
            q1 <= internal;
            q2 <= internal;
        end
    end
endmodule

//==============================================================================
// Case 8: 跨模块实例化
// 金标准: top.a -> u1.d -> u1.q -> u2.d -> top.b
//==============================================================================
module sub_pipe (
    input  wire clk,
    input  wire d,
    output wire q
);
    always_ff @(posedge clk)
        q <= d;
endmodule

module pipe_top (
    input  wire clk,
    input  wire a,
    output wire b
);
    wire mid;
    
    sub_pipe u1 (.clk(clk), .d(a), .q(mid));
    sub_pipe u2 (.clk(clk), .d(mid), .q(b));
endmodule

//==============================================================================
// Case 9: 时钟域
// 金标准: 
//   - q1 driven by clk_a domain
//   - q2 driven by clk_b domain  
//==============================================================================
module dual_clk (
    input  wire clk_a,
    input  wire clk_b,
    input  wire rst_n,
    input  wire da,
    input  wire db,
    output wire qa,
    output wire qb
);
    always_ff @(posedge clk_a or negedge rst_n) begin
        if (!rst_n)
            qa <= 1'b0;
        else
            qa <= da;
    end
    
    always_ff @(posedge clk_b or negedge rst_n) begin
        if (!rst_n)
            qb <= 1'b0;
        else
            qb <= db;
    end
endmodule
