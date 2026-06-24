//==============================================================================
// type_taxonomy.sv - 全面 type coverage 测试 fixture
//==============================================================================
// [P1 2026-06-24] 测试 coverage_gen_demo 工具的 parse_width_from_pyslang 在
// 各种 SystemVerilog type 构造上的能力.
//
// 覆盖:
//  - 1-bit scalar (logic, wire, reg)
//  - 1D vector (literal width, parameter width, arithmetic width)
//  - $clog2 derived parameters
//  - 2D packed array
//  - Unpacked array
//  - Package typedef → logic / enum / packed struct / packed union
//  - Module-scope typedef
//  - Packed struct (standalone + in port)
//  - Packed union
//
// 黄金标准: 每个 signal 都注释 [W=N], 测试必须 assert (width, hi, lo).
//==============================================================================

package type_taxonomy_pkg;

    // ---- 基础 typedef → logic ----
    typedef logic [31:0] word_t;          // [W=32]
    typedef logic [15:0] halfword_t;      // [W=16]
    typedef logic [7:0]  byte_t;          // [W=8]

    // ---- typedef → enum (4 values, needs 2 bits) ----
    typedef enum logic [1:0] {
        ST_IDLE  = 2'd0,
        ST_BUSY  = 2'd1,
        ST_DONE  = 2'd2,
        ST_ERROR = 2'd3
    } state_t;                              // [W=2]

    // ---- typedef → packed struct (8 + 24 = 32 bits) ----
    typedef struct packed {
        logic [7:0]  opcode;               // 8 bits
        logic [23:0] addr;                 // 24 bits
    } instr_t;                             // [W=32]

    // ---- typedef → packed union (max(32, 8+8+8+8) = 32 bits) ----
    typedef union packed {
        logic [31:0] raw;                  // 32 bits
        struct packed {
            logic [7:0] byte0;
            logic [7:0] byte1;
            logic [7:0] byte2;
            logic [7:0] byte3;
        } bytes;
    } word_u;                              // [W=32]

    // ---- 嵌套 typedef (typedef → typedef) ----
    typedef word_t         cached_word_t;   // [W=32]
    typedef state_t        cached_state_t;  // [W=2]

endpackage

module type_taxonomy #(
    parameter int WIDTH = 32,
    parameter int DEPTH = 4,
    parameter int COUNT = 8,
    parameter int N_SRC = 32
)(
    input                          clk,            // [W=1]
    input                          rst_n,          // [W=1]

    // scalar control ports
    input                          enable_i,       // [W=1]
    input                          valid_i,        // [W=1]
    output                         ready_o,        // [W=1]
    input                          trig_i,         // [W=1]

    // 1D vector ports
    input  logic [WIDTH-1:0]       data_i,         // [W=32]
    output logic [WIDTH-1:0]       data_o,         // [W=32]
    input  logic [WIDTH/2-1:0]     half_i,         // [W=16]
    output logic [WIDTH/4-1:0]     quarter_o,      // [W=8]
    input  logic [N_SRC-1:0]       src_i,          // [W=32]

    // $clog2 derived
    input  logic [$clog2(DEPTH)-1:0]  depth_idx_i,  // [W=2]
    output logic [$clog2(COUNT)-1:0]  count_idx_o,  // [W=3]
    input  logic [$clog2(N_SRC)-1:0]  src_idx_i,    // [W=5]
    output logic [$clog2(N_SRC)-1:0]  src_idx_o,    // [W=5]

    // typedef ports
    input  type_taxonomy_pkg::word_t      word_i,     // [W=32]
    output type_taxonomy_pkg::word_t      word_o,     // [W=32]
    input  type_taxonomy_pkg::halfword_t  halfword_i, // [W=16]
    input  type_taxonomy_pkg::byte_t      byte_i,     // [W=8]
    input  type_taxonomy_pkg::state_t     state_i,    // [W=2]
    output type_taxonomy_pkg::state_t     state_o,    // [W=2]
    input  type_taxonomy_pkg::instr_t     instr_i,    // [W=32]
    output type_taxonomy_pkg::instr_t     instr_o,    // [W=32]
    input  type_taxonomy_pkg::word_u      word_u_i,   // [W=32]
    output type_taxonomy_pkg::word_u      word_u_o,   // [W=32]

    // 嵌套 typedef
    input  type_taxonomy_pkg::cached_word_t  cached_word_i,  // [W=32]
    output type_taxonomy_pkg::cached_state_t cached_state_o, // [W=2]

    // 2D 嵌套
    input  logic [DEPTH-1:0][WIDTH-1:0]   matrix_i,    // [W=4] (外层)
    output logic [COUNT-1:0][7:0]        bytes_o,     // [W=8] (外层)

    // unpacked array (1D)
    input  logic [3:0]                   sel_i         // [W=4]
);

    // ---- 内部 signal: 派生 + array ----
    logic [WIDTH-1:0]            pipe_q;         // [W=32]
    logic [WIDTH/2-1:0]          half_q;         // [W=16]
    logic [$clog2(DEPTH)-1:0]    depth_idx_q;    // [W=2]
    logic [$clog2(COUNT)-1:0]    count_idx_q;    // [W=3]
    logic [$clog2(N_SRC)-1:0]    src_idx_q;      // [W=5]
    type_taxonomy_pkg::state_t   fsm_q;          // [W=2]
    type_taxonomy_pkg::instr_t   decoded_q;      // [W=32]
    type_taxonomy_pkg::word_u    word_u_q;       // [W=32]

    // module-scope typedef
    typedef logic [WIDTH-1:0] local_word_t;
    local_word_t local_reg;                    // [W=32]

    // unpacked array of logic (declare 内部)
    logic [7:0] mem [DEPTH];                  // [W=8] (packed 维度)

    // unpacked struct (complex — don't test exact width)
    struct {
        logic [7:0]   tag;
        logic [WIDTH-1:0] value;
    } entry_t;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pipe_q      <= '0;
            half_q      <= '0;
            depth_idx_q <= '0;
            count_idx_q <= '0;
            src_idx_q   <= '0;
            fsm_q       <= type_taxonomy_pkg::ST_IDLE;
            decoded_q   <= '0;
            word_u_q    <= '0;
            local_reg   <= '0;
        end else if (enable_i && valid_i) begin
            pipe_q      <= data_i;
            half_q      <= half_i;
            depth_idx_q <= depth_idx_i;
            count_idx_q <= count_idx_o;
            src_idx_q   <= src_idx_i;
            fsm_q       <= state_i;
            decoded_q   <= instr_i;
            word_u_q    <= word_u_i;
            local_reg   <= word_i;
        end
    end

    assign data_o         = pipe_q;
    assign ready_o        = !valid_i || (|src_idx_q);
    assign src_idx_o      = src_idx_q;
    assign count_idx_o    = count_idx_q;
    assign depth_idx_q    = depth_idx_i;
    assign half_o         = half_q[15:0];
    assign quarter_o      = half_q[7:0];
    assign state_o        = fsm_q;
    assign instr_o        = decoded_q;
    assign word_u_o       = word_u_q;
    assign bytes_o        = mem[0];
    assign cached_state_o = fsm_q;
    assign cached_word_i  = word_i;

endmodule
