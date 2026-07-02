`timescale 1ns/1ps
module sync_fifo #(parameter WIDTH = 8, parameter SIZE = 4) (
    input  wire             clk_i,
    input  wire             rst_ni,
    input  wire             push_i,
    input  wire             pop_i,
    input  wire [WIDTH-1:0] push_data_i,
    output logic[WIDTH-1:0] pop_data_o,
    output logic            full_o,
    output logic            empty_o
);
    logic [WIDTH-1:0] mem [SIZE];
    logic [$clog2(SIZE):0] count_q;
    logic [$clog2(SIZE):0] wr_ptr_q, rd_ptr_q;
    assign empty_o = (count_q == 0);
    assign full_o  = (count_q == SIZE);
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            count_q  <= '0;
            wr_ptr_q <= '0;
            rd_ptr_q <= '0;
        end
        else begin
            if (push_i && !full_o) begin
                mem[wr_ptr_q[$clog2(SIZE)-1:0]] <= push_data_i;
                wr_ptr_q <= wr_ptr_q + 1;
            end
            if (pop_i && !empty_o) begin
                pop_data_o <= mem[rd_ptr_q[$clog2(SIZE)-1:0]];
                rd_ptr_q <= rd_ptr_q + 1;
            end
            case ({push_i && !full_o, pop_i && !empty_o})
                2'b10: count_q <= count_q + 1;
                2'b01: count_q <= count_q - 1;
                default: ;
            endcase
        end
    end
endmodule
