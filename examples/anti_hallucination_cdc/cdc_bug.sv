// Anti-hallucination demo: single-flop CDC, no synchronizer.
// Agent claim to refute: "dst_valid is safely synchronized into dst_clk
// through a two-flop synchronizer."
module cdc_bug (
  input  logic src_clk,
  input  logic dst_clk,
  input  logic resetn,
  input  logic src_valid,
  output logic dst_valid
);
  // BUG: src_valid is sampled directly in dst_clk domain. There is no
  // meta/dst_valid two-stage chain; this is a single-flop CDC.
  always_ff @(posedge dst_clk or negedge resetn) begin
    if (!resetn) dst_valid <= 1'b0;
    else         dst_valid <= src_valid;
  end
endmodule
