// cva6_scoreboard_pattern.sv — 从 CVA6 Scoreboard 抽取的典型模式
//
// 模式 1: 多 bit 寄存器组 (commit pointer / issue pointer)
// 模式 2: always_ff 多寄存器同时更新 (scoreboard entries)
// 模式 3: always_comb 扫描空闲位 (find first zero)
// 模式 4: 嵌套 if-else 分支 (flush vs normal commit)

module cva6_scoreboard_pattern #(
    parameter int NR_ENTRIES = 8
) (
    input  logic                   clk_i,
    input  logic                   rst_ni,
    input  logic                   flush_i,
    input  logic                   issue_en_i,
    input  logic [NR_ENTRIES-1:0]  issue_rd_i,
    input  logic                   commit_en_i,
    input  logic [NR_ENTRIES-1:0]  commit_rd_i,
    output logic                   sb_full_o,
    output logic [NR_ENTRIES-1:0]  sb_entries_o,
    output logic [             2:0] issue_ptr_o
);

  // ── 寄存器组 (CVA6 scoreboard entries) ──
  logic [NR_ENTRIES-1:0] sb_q, sb_n;
  logic [           2:0] issue_cnt_q, issue_cnt_n;
  logic [           2:0] commit_cnt_q, commit_cnt_n;

  // ── 模式 1: find first zero (CVA6 scoreboard 核心) ──
  logic [2:0] first_zero;
  always_comb begin
    first_zero = '0;
    for (int i = 0; i < NR_ENTRIES; i++) begin
      if (!sb_q[i]) begin
        first_zero = i[2:0];
        break;
      end
    end
  end
  assign sb_full_o = (issue_cnt_q == NR_ENTRIES[2:0]);

  // ── 模式 2: 组合逻辑更新 ──
  always_comb begin
    sb_n = sb_q;
    issue_cnt_n = issue_cnt_q;
    commit_cnt_n = commit_cnt_q;

    // issue: set entry at first_zero position
    if (issue_en_i && !flush_i && !sb_full_o) begin
      sb_n[first_zero] = 1'b1;
      issue_cnt_n = issue_cnt_q + 2'd1;
    end

    // commit: clear entry
    if (commit_en_i && !flush_i) begin
      sb_n[commit_rd_i[2:0]] = 1'b0;
      commit_cnt_n = commit_cnt_q + 2'd1;
    end

    // ── 模式 3: 嵌套 if 分支 (flush override) ──
    if (flush_i) begin
      sb_n = '0;
      issue_cnt_n = '0;
      commit_cnt_n = '0;
    end
  end

  // ── 模式 4: always_ff 多寄存器同时更新 ──
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      sb_q         <= '0;
      issue_cnt_q  <= '0;
      commit_cnt_q <= '0;
    end else begin
      sb_q         <= sb_n;
      issue_cnt_q  <= issue_cnt_n;
      commit_cnt_q <= commit_cnt_n;
    end
  end

  assign sb_entries_o = sb_q;
  assign issue_ptr_o  = first_zero;

endmodule
