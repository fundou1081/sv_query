// orphan_23: generate_for containing always_ff with ternary
module orphan_23 #(parameter N = 4) (
    input clk, rst_n,
    input [7:0] data_in,
    input [N-1:0] enable,
    output reg [7:0] data_out [0:N-1]
);
    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen_reg
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n)
                    data_out[i] <= 8'd0;
                else
                    data_out[i] <= enable[i] ? data_in : 8'd0;
            end
        end
    endgenerate
endmodule
