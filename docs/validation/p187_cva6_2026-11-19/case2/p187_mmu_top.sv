// NON-HISTORICAL elaboration harness for P187 value cases.
// Purpose: provide a concrete top so pyslang can elaborate the UNMODIFIED
// historical core/cva6_mmu/cva6_mmu.sv extracted from the CVA6 git history.
// The stub interface structs below carry the exact field names used by the
// historical source; widths come from the real cv64a6_imafdc_sv39 config.
// This file is a test harness only -- it is NOT CVA6 RTL and is not presented
// as a historical artifact.
module p187_mmu_top;
  import config_pkg::*;
  import cva6_config_pkg::*;

  localparam cva6_cfg_t CVA6Cfg = build_config_pkg::build_config(cva6_cfg);

  typedef struct packed {
    logic                    valid;
    logic [CVA6Cfg.XLEN-1:0] cause;
    logic [CVA6Cfg.XLEN-1:0] tval;
    logic [CVA6Cfg.GPLEN-1:0] tval2;
    logic [31:0]             tinst;
    logic                    gva;
  } p187_exception_t;

  // NOTE: CVA6 naming quirk -- input port `icache_areq_i` has type
  // `icache_arsp_t`, and output port `icache_areq_o` has type `icache_areq_t`.
  typedef struct packed {
    logic                    fetch_req;
    logic [CVA6Cfg.VLEN-1:0] fetch_vaddr;
  } p187_icache_arsp_t;

  typedef struct packed {
    logic                    fetch_valid;
    p187_exception_t         fetch_exception;
    logic [CVA6Cfg.PLEN-1:0] fetch_paddr;
  } p187_icache_areq_t;

  typedef struct packed {
    logic                    data_req;
    logic                    data_we;
    logic                    kill_req;
    logic                    tag_valid;
    logic [2:0]              cbo_op;
    logic [3:0]              data_id;
    logic [CVA6Cfg.DCACHE_INDEX_WIDTH-1:0] address_index;
    logic [CVA6Cfg.DCACHE_TAG_WIDTH-1:0]   address_tag;
    logic [3:0]              data_be;
    logic [2:0]              data_size;
    logic [CVA6Cfg.XLEN-1:0] data_wdata;
    logic [CVA6Cfg.XLEN-1:0] data_wuser;
  } p187_dcache_req_i_t;

  typedef struct packed {
    logic                    data_gnt;
    logic                    data_rvalid;
    logic [CVA6Cfg.XLEN-1:0] data_rdata;
  } p187_dcache_req_o_t;

  logic clk_i;
  logic rst_ni;
  logic lsu_req_i;
  logic [CVA6Cfg.VLEN-1:0] lsu_vaddr_i;

  cva6_mmu #(
    .CVA6Cfg        (CVA6Cfg),
    .exception_t    (p187_exception_t),
    .icache_areq_t  (p187_icache_areq_t),
    .icache_arsp_t  (p187_icache_arsp_t),
    .icache_dreq_t  (logic),
    .icache_drsp_t  (logic),
    .dcache_req_i_t (p187_dcache_req_i_t),
    .dcache_req_o_t (p187_dcache_req_o_t)
  ) u_mmu (
    .clk_i      (clk_i),
    .rst_ni     (rst_ni),
    .lsu_req_i  (lsu_req_i),
    .lsu_vaddr_i(lsu_vaddr_i)
  );
endmodule
