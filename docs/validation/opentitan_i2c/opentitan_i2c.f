// OpenTitan sv_query filelist -- hw/ip/i2c top (`i2c`) with its real dependency closure.
// Source root: /Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace
// Derived from hw/ip/i2c/i2c.core files_rtl depend list:
//   lowrisc:virtual_constants:top_pkg, lowrisc:prim:all,
//   lowrisc:prim:ram_1p_pkg, lowrisc:prim:ram_1p_adv,
//   lowrisc:ip:tlul, lowrisc:ip:i2c_pkg,
//   lowrisc:virtual_constants:top_racl_pkg
// plus the technology-independent prim_generic cells that `lowrisc:prim:all` resolves to.
//
// Closure was derived by source inspection (not by dumping all prim files), so the
// file count is far smaller than the naive "all prim + all tlul" list that fails
// for hw/ip/uart (see /tmp/opentitan_svq/REPORT.md issue 1).

// --- include dirs (prim_assert.sv / prim_flop_macros.sv / prim_fifo_assert.svh live here) ---
+incdir+hw/ip/prim/rtl
+incdir+hw/ip/prim_generic/rtl
+incdir+hw/ip/tlul/rtl
+incdir+hw/ip/i2c/rtl

// --- prim macro/header units (include-only, NOT standalone compile units) ---
hw/ip/prim/rtl/prim_assert.sv
hw/ip/prim/rtl/prim_assert_standard_macros.svh
hw/ip/prim/rtl/prim_assert_dummy_macros.svh
hw/ip/prim/rtl/prim_assert_yosys_macros.svh
hw/ip/prim/rtl/prim_assert_sec_cm.svh
hw/ip/prim/rtl/prim_flop_macros.sv
hw/ip/prim/rtl/prim_fifo_assert.svh

// --- prim packages ---
hw/ip/prim/rtl/prim_alert_pkg.sv
hw/ip/prim/rtl/prim_mubi_pkg.sv
hw/ip/prim/rtl/prim_subreg_pkg.sv
hw/ip/prim/rtl/prim_util_pkg.sv

// --- prim cells directly instantiated by the i2c closure ---
hw/ip/prim/rtl/prim_alert_sender.sv
hw/ip/prim/rtl/prim_arbiter_tree.sv
hw/ip/prim/rtl/prim_count.sv
hw/ip/prim/rtl/prim_diff_decode.sv
hw/ip/prim/rtl/prim_fifo_sync.sv
hw/ip/prim/rtl/prim_fifo_sync_cnt.sv
hw/ip/prim/rtl/prim_intr_hw.sv
hw/ip/prim/rtl/prim_onehot_check.sv
hw/ip/prim/rtl/prim_onehot_enc.sv
hw/ip/prim/rtl/prim_ram_1p_adv.sv
hw/ip/prim/rtl/prim_reg_we_check.sv
hw/ip/prim/rtl/prim_sec_anchor_buf.sv
hw/ip/prim/rtl/prim_sec_anchor_flop.sv
hw/ip/prim/rtl/prim_subreg.sv
hw/ip/prim/rtl/prim_subreg_arb.sv
hw/ip/prim/rtl/prim_subreg_ext.sv

// --- prim secded (tlul integrity + prim_ram_1p_adv ECC) ---
hw/ip/prim/rtl/prim_secded_pkg.sv
hw/ip/prim/rtl/prim_secded_inv_22_16_dec.sv
hw/ip/prim/rtl/prim_secded_inv_22_16_enc.sv
hw/ip/prim/rtl/prim_secded_inv_39_32_dec.sv
hw/ip/prim/rtl/prim_secded_inv_39_32_enc.sv
hw/ip/prim/rtl/prim_secded_inv_hamming_22_16_dec.sv
hw/ip/prim/rtl/prim_secded_inv_hamming_22_16_enc.sv
hw/ip/prim/rtl/prim_secded_inv_hamming_39_32_dec.sv
hw/ip/prim/rtl/prim_secded_inv_hamming_39_32_enc.sv
hw/ip/prim/rtl/prim_secded_inv_64_57_dec.sv
hw/ip/prim/rtl/prim_secded_inv_64_57_enc.sv

// --- technology-independent prim cells (prim_generic mapping) ---
// prim_buf / prim_flop / prim_flop_2sync / prim_xnor2 / prim_xor2 / prim_and2 / prim_const
// and the SRAM cells prim_ram_1p + prim_ram_1p_pkg live here, NOT in hw/ip/prim/rtl.
hw/ip/prim_generic/rtl/prim_buf.sv
hw/ip/prim_generic/rtl/prim_flop.sv
hw/ip/prim_generic/rtl/prim_flop_2sync.sv
hw/ip/prim_generic/rtl/prim_xnor2.sv
hw/ip/prim_generic/rtl/prim_xor2.sv
hw/ip/prim_generic/rtl/prim_and2.sv
hw/ip/prim_generic/rtl/prim_const.sv
hw/ip/prim_generic/rtl/prim_const_sec.sv
hw/ip/prim_generic/rtl/prim_ram_1p.sv
hw/ip/prim_generic/rtl/prim_ram_1p_pkg.sv

// --- tlul ---
hw/ip/tlul/rtl/tlul_pkg.sv
hw/ip/tlul/rtl/tlul_adapter_reg.sv
hw/ip/tlul/rtl/tlul_cmd_intg_chk.sv
hw/ip/tlul/rtl/tlul_rsp_intg_gen.sv
hw/ip/tlul/rtl/tlul_data_integ_dec.sv
hw/ip/tlul/rtl/tlul_data_integ_enc.sv
hw/ip/tlul/rtl/tlul_err.sv

// --- i2c (top = i2c) ---
hw/ip/i2c/rtl/i2c_pkg.sv
hw/ip/i2c/rtl/i2c_reg_pkg.sv
hw/ip/i2c/rtl/i2c_reg_top.sv
hw/ip/i2c/rtl/i2c_fifo_sync_sram_adapter.sv
hw/ip/i2c/rtl/i2c_fifos.sv
hw/ip/i2c/rtl/i2c_core.sv
hw/ip/i2c/rtl/i2c_bus_monitor.sv
hw/ip/i2c/rtl/i2c_controller_fsm.sv
hw/ip/i2c/rtl/i2c_target_fsm.sv
hw/ip/i2c/rtl/i2c.sv

// --- top-level virtual constant packages (top_pkg / top_racl_pkg) ---
hw/top_earlgrey/rtl/top_pkg.sv
hw/top_earlgrey/rtl/autogen/top_racl_pkg.sv
