// pr5_wrap.sv — benchmark 深结构 wrapper (iter_180, C 路线第二项)
//
// 背景: `axi_xbar_intf` 默认参数 `Cfg = '0` → NoSlvPorts/NoMstPorts = 0 →
// 空壳树 (2 实例 / 168 nodes), 结构断言只能弱化 (iter_145 登记的 TODO)。
// 本 wrapper 用**真实 Cfg** (4 slave / 3 master / 32bit addr / 64bit data)
// 实例化, 恢复深结构基准 (xbar → unmuxed → mux/demux 层次)。
//
// 用法: 加入 axi filelist 后 `--target pr5_wrap`。
module pr5_wrap #() (
  input logic clk_i,
  input logic rst_ni
);
  import axi_pkg::*;

  localparam xbar_cfg_t Cfg = '{
    NoSlvPorts:         4,
    NoMstPorts:         3,
    MaxMstTrans:        1,
    MaxSlvTrans:        1,
    FallThrough:        1'b0,
    LatencyMode:        10'b0,
    PipelineStages:     1,
    AxiIdWidthSlvPorts: 4,
    AxiIdUsedSlvPorts:  4,
    UniqueIds:          1'b1,
    AxiAddrWidth:       32,
    AxiDataWidth:       64,
    NoAddrRules:        3
  };

  AXI_BUS #(.AXI_ADDR_WIDTH(32), .AXI_DATA_WIDTH(64), .AXI_ID_WIDTH(4)) slv [4] ();
  AXI_BUS #(.AXI_ADDR_WIDTH(32), .AXI_DATA_WIDTH(64), .AXI_ID_WIDTH(6)) mst [3] ();

  xbar_rule_64_t [2:0] addr_map;
  logic [3:0]    en_default_mst_port;
  logic [3:0][1:0] default_mst_port;

  axi_xbar_intf #(.Cfg(Cfg)) i_xbar (
    .clk_i,
    .rst_ni,
    .test_i             (1'b0),
    .slv_ports          (slv),
    .mst_ports          (mst),
    .addr_map_i         (addr_map),
    .en_default_mst_port_i (en_default_mst_port),
    .default_mst_port_i (default_mst_port)
  );
endmodule
