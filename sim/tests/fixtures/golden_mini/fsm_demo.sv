`timescale 1ns/1ps
// [V6 Golden Test 2026-07-20] Minimal FSM
// - state_q updates each cycle from next_state
// - 4 outputs each controlled by current state
// - Exercises use case C (--show-drives on state_q)
module fsm_demo(
    input  clk,
    input  start,
    input  busy,
    output reg [1:0] y_idle,
    output reg [1:0] y_run,
    output reg [1:0] y_done,
    output reg [1:0] y_err
);
    reg [1:0] state_q, next_state;
    parameter IDLE = 2'd0, RUN = 2'd1, DONE = 2'd2, ERR = 2'd3;

    always @(posedge clk) begin
        state_q <= next_state;
        case (state_q)
            IDLE: begin
                y_idle <= 2'd1;
                y_run  <= 2'd0;
                y_done <= 2'd0;
                y_err  <= 2'd0;
            end
            RUN: begin
                y_idle <= 2'd0;
                y_run  <= 2'd1;
                y_done <= 2'd0;
                y_err  <= 2'd0;
            end
            DONE: begin
                y_idle <= 2'd0;
                y_run  <= 2'd0;
                y_done <= 2'd1;
                y_err  <= 2'd0;
            end
            ERR: begin
                y_idle <= 2'd0;
                y_run  <= 2'd0;
                y_done <= 2'd0;
                y_err  <= 2'd1;
            end
        endcase
    end

    always @* begin
        case (state_q)
            IDLE: next_state = start ? RUN : IDLE;
            RUN:  next_state = busy  ? RUN : DONE;
            DONE: next_state = IDLE;
            ERR:  next_state = ERR;
            default: next_state = ERR;
        endcase
    end
endmodule
