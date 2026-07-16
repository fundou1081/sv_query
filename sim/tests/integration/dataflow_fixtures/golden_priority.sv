// golden_priority.sv — priority encoder (test_dataflow_golden.py)
module golden_priority(
    input  wire [3:0]  req,
    output reg  [1:0]  out_b,
    output reg         out_d
);
    always @* begin
        if (req[0]) out_b = 2'd0;
        else if (req[1]) out_b = 2'd1;
        else if (req[2]) out_b = 2'd2;
        else if (req[3]) out_b = 2'd3;
        else out_b = 2'd0;
        
        if (req[0]) out_d = 1'b1;
        else if (req[1]) out_d = 1'b1;
        else if (req[2]) out_d = 1'b1;
        else if (req[3]) out_d = 1'b1;
        else out_d = 1'b0;
    end
endmodule
