// case29: generate for chain (两个 generate for 串联信号链)
// generate_for_chain: 3 级累加器 + 1 个下游 stage
//   genvar i; for (i=0; i<N-1; i++) begin : gen_stage1
//     assign buf1[i+1] = buf1[i] + prod;     // 3 iterations
//   end
//   for (i=0; i<N-1; i++) begin : gen_stage2
//     assign buf2[i] = buf1[i+1] + prod;     // 3 iterations, depend on stage1
//   end
//   for (i=0; i<N-1; i++) begin : gen_stage3
//     assign buf3[i] = buf2[i] + prod;       // 3 iterations, depend on stage2
//   end
// 期望: 9 个 generate iteration assign 全部展开, 3 个 stage 通过 buf1/buf2/buf3 信号链串联

module generate_for_chain #(
    parameter N = 4,
    parameter W = 8
) (
    input  [W-1:0] data,
    input  [W-1:0] weights,
    output [W-1:0] chain_out
);
    wire [W-1:0] buf1 [0:N-1];
    wire [W-1:0] buf2 [0:N-1];
    wire [W-1:0] buf3 [0:N-1];
    wire [W-1:0] prod;

    assign buf1[0] = data;
    assign prod = data + weights;
    assign chain_out = buf3[N-2];

    genvar i;
    generate
        for (i = 0; i < N - 1; i = i + 1) begin : gen_stage1
            assign buf1[i+1] = buf1[i] + prod;
        end
        for (i = 0; i < N - 1; i = i + 1) begin : gen_stage2
            assign buf2[i] = buf1[i+1] + prod;
        end
        for (i = 0; i < N - 1; i = i + 1) begin : gen_stage3
            assign buf3[i] = buf2[i] + prod;
        end
    endgenerate
endmodule
