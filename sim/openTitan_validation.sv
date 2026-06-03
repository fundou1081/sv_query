// ==============================================================================
// openTitan_validation.sv - Self-contained OpenTitan-style validation test
// ==============================================================================
// This file mimics real OpenTitan IP style with:
// - Multiple always_ff blocks with complex if/else chains
// - FSM-style state machine
// - Multi-mode operation (normal/alert/lp)
// - Conditional reset paths
// - Multi-clock domain awareness
// ==============================================================================

module openTitan_validation (
  input        clk_i,
  input        rst_ni,
  input        clk_secondary_i,
  input        rst_secondary_ni,

  // Main control
  input        enable_i,
  input [3:0]  mode_i,        // 0=idle, 1=active, 2=flush, 3=alert, 15=sleep
  input        trigger_i,

  // Data path
  input  logic [31:0] data_i,
  input  logic        valid_i,
  output logic [31:0] data_o,
  output logic        valid_o,

  // Status
  output logic       busy_o,
  output logic       error_o,
  output logic [2:0] state_o,
  output logic [2:0] alert_state_o
);

// ============================================================================
// Local signals
// ============================================================================
typedef enum logic [2:0] {
  IDLE    = 3'd0,
  ACTIVE  = 3'd1,
  FLUSH   = 3'd2,
  ALERT   = 3'd3,
  RECOV   = 3'd4,
  LP_MODE = 3'd5,
  SLEEP   = 3'd7
} state_e;

typedef enum logic [2:0] {
  NORMAL  = 3'd0,
  ALERT_MODE = 3'd1,
  LP_PATH = 3'd2
} op_mode_e;

logic [31:0] buffer_q, buffer_d;
logic [31:0] accumulator_q, accumulator_d;
logic [15:0] counter_q, counter_d;
logic [2:0]  state_q, state_d;
logic [2:0]  alert_q;
logic       buffer_valid_q;
logic       error_q;
logic       busy_q;
op_mode_e   op_mode_q;

// ============================================================================
// FSM state register
// ============================================================================
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) begin
    state_q   <= IDLE;
    alert_q   <= 3'd0;
    error_q   <= 1'b0;
    busy_q    <= 1'b0;
  end else begin
    state_q   <= state_d;
    alert_q   <= (trigger_i && mode_i == 3) ? ALERT :
                 (mode_i == 15)           ? 3'd7 :
                 (error_q)                ? ALERT : alert_q;
    error_q   <= (valid_i && !enable_i) || error_q;
    busy_q    <= (state_q != IDLE) || trigger_i;
  end
end

// ============================================================================
// Data buffer register (updated on valid_i)
// ============================================================================
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) begin
    buffer_q      <= 32'd0;
    buffer_valid_q <= 1'b0;
  end else if (valid_i && enable_i) begin
    buffer_q      <= data_i;
    buffer_valid_q <= 1'b1;
  end else if (state_q == FLUSH) begin
    buffer_q      <= 32'd0;
    buffer_valid_q <= 1'b0;
  end else begin
    buffer_valid_q <= 1'b0;
  end
end

// ============================================================================
// Accumulator (math on buffer_q, conditionally reset)
// ============================================================================
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) begin
    accumulator_q <= 32'd0;
  end else if (state_q == ALERT) begin
    accumulator_q <= 32'd0;           // clear on alert
  end else if (state_q == LP_MODE) begin
    accumulator_q <= {16'b0, buffer_q[31:16]};  // half-width in LP
  end else if (buffer_valid_q) begin
    accumulator_q <= accumulator_q + buffer_q;  // running sum
  end
end

// ============================================================================
// Counter (overflow check)
// ============================================================================
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) begin
    counter_q <= 16'd0;
  end else if (mode_i == 15) begin
    counter_q <= 16'd0;                // reset in sleep mode
  end else if (trigger_i) begin
    counter_q <= counter_q + 1'b1;
    if (counter_q == 16'hFFFF) begin
      counter_q <= 16'd0;             // wraparound
    end
  end
end

// ============================================================================
// Secondary clock domain register
// ============================================================================
always_ff @(posedge clk_secondary_i or negedge rst_secondary_ni) begin
  if (!rst_secondary_ni) begin
    op_mode_q <= NORMAL;
  end else begin
    op_mode_q <= (mode_i == 3) ? ALERT_MODE :
                 (mode_i == 15)? LP_PATH : NORMAL;
  end
end

// ============================================================================
// Next-state logic (combinational, drives *_d signals)
// ============================================================================
always_comb begin
  state_d = state_q;
  buffer_d = buffer_q;
  accumulator_d = accumulator_q;

  unique case (state_q)
    IDLE: begin
      if (trigger_i && enable_i) begin
        state_d = ACTIVE;
      end else if (mode_i == 15) begin
        state_d = SLEEP;
      end
    end

    ACTIVE: begin
      if (mode_i == 2) begin
        state_d = FLUSH;
      end else if (error_q || (alert_q == ALERT)) begin
        state_d = ALERT;
      end else if (counter_q[15]) begin
        state_d = LP_MODE;
      end else if (!enable_i) begin
        state_d = IDLE;
      end
    end

    FLUSH: begin
      state_d = IDLE;
    end

    ALERT: begin
      if (mode_i == 4) begin
        state_d = RECOV;
      end
    end

    RECOV: begin
      state_d = IDLE;
    end

    LP_MODE: begin
      if (mode_i == 1) begin
        state_d = ACTIVE;
      end else if (mode_i == 15) begin
        state_d = SLEEP;
      end
    end

    SLEEP: begin
      if (trigger_i) begin
        state_d = ACTIVE;
      end
    end

    default: state_d = IDLE;
  endcase
end

// ============================================================================
// Output assignments
// ============================================================================
assign data_o  = accumulator_q[31:0];
assign valid_o = buffer_valid_q && (state_q == ACTIVE || state_q == LP_MODE);
assign busy_o  = busy_q;
assign state_o = state_q[2:0];
assign alert_state_o = alert_q;

endmodule