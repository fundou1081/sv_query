// golden_mux5.sv — 5-way mux (test_dataflow_golden.py)
module golden_mux5(
    input  wire [2:0]  sel,
    input  wire [7:0]  in0, in1, in2, in3, in4,
    output reg  [7:0]  out
);
    always @* begin
        if (sel == 3'd0)
            out = in0;
        else if (sel == 3'd1)
            out = in1;
        else if (sel == 3'd2)
            out = in2;
        else if (sel == 3'd3)
            out = in3;
        else if (sel == 3'd4)
            out = in4;
        else
            out = 8'd0;
    end
endmodule
