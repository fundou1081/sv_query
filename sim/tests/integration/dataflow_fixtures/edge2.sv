// edge2.sv — case inside if / if inside case (test_dataflow_else_if_comprehensive.py)
module edge2(
    input  wire        clk,
    input  wire        en, valid,
    input  wire [1:0]  sel,
    input  wire [7:0]  data_in,
    output reg  [7:0]  out1, out2
);
    reg [7:0] r1, r2;
    always @* begin
        out1 = 8'd0;
        out2 = 8'd0;
        if (en) begin
            case (sel)
                2'b00:   out1 = data_in;
                2'b01:   out1 = data_in + 8'd1;
                2'b10:   out1 = data_in + 8'd2;
                default: out1 = data_in + 8'd3;
            endcase
        end
        // out2 case 嵌套 if
        case (sel)
            2'b00: r2 = data_in;
            2'b01: if (valid) r2 = data_in + 8'd1; else r2 = data_in + 8'd2;
            default: r2 = 8'd0;
        endcase
        out2 = r2;
    end
endmodule
