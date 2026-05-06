//==============================================================================
// test_cases.sv - 多场景测试用例
// 按照铁律13: 先推导金标准再验证
//==============================================================================

//==============================================================================
// Test 1: 多个 always 块
//==============================================================================
module test_multi_alway (
    input  logic clk,
    input  logic rst_n,
    input  logic a, b,
    output logic q1, q2
);
    // always_ff: 非阻塞
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q1 <= 1'b0;
        else
            q1 <= a;
    end
    
    // always_comb
    always_comb begin
        q2 = b;
    end
endmodule

//==============================================================================
// Test 2: 嵌套 if/else  
//==============================================================================
module test_nested_if (
    input  logic clk,
    input  logic rst_n,
    input  logic a, b, sel,
    output logic q
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
// Test 3: 多个模块实例
//==============================================================================
module sub (
    input  logic clk,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk)
        q <= d;
endmodule

module test_multi_inst (
    input  logic clk,
    input  logic a, b,
    output logic q1, q2
);
    sub u1 (.clk(clk), .d(a), .q(q1));
    sub u2 (.clk(clk), .d(b), .q(q2));
endmodule

//==============================================================================
// Test 4: 时钟域
//==============================================================================
module test_clk_domains (
    input  logic clk_a, clk_b,
    input  logic rst_n,
    input  logic da, db,
    output logic qa, qb
);
    // Clock domain A
    always_ff @(posedge clk_a or negedge rst_n) begin
        if (!rst_n)
            qa <= 1'b0;
        else
            qa <= da;
    end
    
    // Clock domain B
    always_ff @(posedge clk_b or negedge rst_n) begin
        if (!rst_n)
            qb <= 1'b0;
        else
            qb <= db;
    end
endmodule

//==============================================================================
// Test 5: 跨模块连接 + 组合逻辑
//==============================================================================
module pipe (
    input  logic clk,
    input  logic din,
    output logic dout
);
    logic tmp;
    
    assign tmp = din;
    
    always_ff @(posedge clk)
        dout <= tmp;
endmodule

module test_pipe (
    input  logic clk,
    input  logic a,
    output logic b
);
    pipe p1 (.clk(clk), .din(a), .dout(b));
endmodule
