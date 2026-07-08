// understand.sv — 一个 IP 含 clk/rst/data/control ports, 用于测试 arch --understand
module cpu_top (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [7:0]  data_in,
    input  logic        valid,
    output logic [7:0]  data_out,
    output logic        ready,
    output logic [3:0]  status
);

    // Submodules
    regfile rf (.clk(clk), .rst_n(rst_n), .we(enable),
                .addr(data_in[3:0]), .wdata(data_in),
                .rdata(data_out));
    decoder dec (.clk(clk), .rst_n(rst_n),
                  .valid(valid), .ready(ready));
endmodule

module regfile (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        we,
    input  logic [3:0]  addr,
    input  logic [7:0]  wdata,
    output logic [7:0]  rdata
);
    // 内部 16x8 register file
endmodule

module decoder (
    input  logic clk,
    input  logic rst_n,
    input  logic valid,
    output logic ready
);
endmodule
