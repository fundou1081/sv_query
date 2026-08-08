// case27: generate for 循环 — 信号展开
// generate_loop: 4 级累加器
//   genvar i; for (i=0; i<N; i++) begin : gen_accum
//     assign acc[i+1] = acc[i] + prod;
//   end
// 期望: visualize dataflow --target generate_loop 能把 generate 展开,
//       每个 iteration 有独立的 acc[1]/acc[2]/acc[3]/acc[4] 和 prod 信号

module generate_loop #(
    parameter N = 4,
    parameter W = 8
) (
    input  [W-1:0] data,
    input  [W-1:0] weights,
    output [W-1:0] sum_out
);
    wire [W-1:0] acc [0:N];
    wire [W-1:0] prod;

    assign acc[0] = {($bits(acc[0])){1'b0}};

    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen_accum
            wire [W-1:0] prod = data * weights[i];
            assign acc[i+1] = acc[i] + prod;
        end
    endgenerate

    assign sum_out = (acc[N] > {W{{1'b1}}}) ? 8'd255 : acc[N][?:0];
endmodule
