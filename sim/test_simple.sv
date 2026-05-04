module top (
    input  logic clk,
    input  logic rst_n,
    input  logic din,
    input  logic en,
    output logic dout
);
    // internal signal
    logic data;
    
    // assign: data 由 din 驱动
    assign data = din;
    
    // always: dout 由 data 驱动 (非阻塞)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            dout <= 1'b0;
        else if (en)
            dout <= data;
    end
    
endmodule
