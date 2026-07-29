// cva6_frontend_pattern.sv — 从 CVA6 Frontend 抽取的典型模式
//
// 模式 1: always_ff state machine (IDLE → RUN → WAIT → FLUSH)
// 模式 2: always_comb 大 mux (next PC selection)
// 模式 3: 多驱动源组合 (PC = ras_top or ras_pop or branch_target)

module cva6_frontend_pattern #(
    parameter int XLEN = 64
) (
    input  logic                   clk_i,
    input  logic                   rst_ni,
    input  logic                   flush_i,
    input  logic                   stall_i,
    input  logic [      XLEN-1:0]  pc_i,
    input  logic [      XLEN-1:0]  branch_target_i,
    input  logic                   branch_taken_i,
    input  logic [      XLEN-1:0]  ras_top_i,
    input  logic                   ras_pop_i,
    input  logic                   exception_i,
    output logic [      XLEN-1:0]  pc_o,
    output logic                   valid_o,
    output logic [             1:0] state_o
);

  // ── 模式 1: state machine ──
  typedef enum logic [1:0] {
    IDLE  = 2'd0,
    RUN   = 2'd1,
    WAIT  = 2'd2,
    FLUSH = 2'd3
  } state_t;

  state_t state_q, state_n;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)
      state_q <= IDLE;
    else
      state_q <= state_n;
  end

  always_comb begin
    state_n = state_q;
    case (state_q)
      IDLE:  state_n = RUN;
      RUN: begin
        if (exception_i)
          state_n = FLUSH;
        else if (stall_i)
          state_n = WAIT;
      end
      WAIT:  state_n = stall_i ? WAIT : RUN;
      FLUSH: state_n = flush_i ? FLUSH : IDLE;
    endcase
  end

  // ── 模式 2: 多驱动源 mux (CVA6 frontend PC selection) ──
  logic [XLEN-1:0] next_pc;

  always_comb begin
    next_pc = pc_i + XLEN'(4);  // default: sequential

    // ── 模式 3: 嵌套 if 多源选择 ──
    if (branch_taken_i) begin
      next_pc = branch_target_i;
    end else if (ras_pop_i) begin
      next_pc = ras_top_i;
    end else if (exception_i) begin
      next_pc = '0;
    end
  end

  assign pc_o = next_pc;
  assign valid_o = (state_q == RUN) && !stall_i;
  assign state_o = state_q;

endmodule
