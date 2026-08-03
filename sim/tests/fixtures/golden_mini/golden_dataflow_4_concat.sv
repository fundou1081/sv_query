// golden_dataflow_4_concat.sv — 含拼接
module with_concat(
    input [7:0] a, b,
    output [15:0] y
);
    assign y = {a, b};
endmodule
