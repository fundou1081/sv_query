// OpenTitan sv_query filelist -- hw/ip/uart top (`uart`) with its real dependency closure.
// Source root: /Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace
// Derived from hw/ip/uart/uart.core files_rtl depend list:
//   lowrisc:virtual_constants:top_pkg, lowrisc:prim:all,
//   lowrisc:ip:tlul, lowrisc:virtual_constants:top_racl_pkg
// plus the technology-independent prim_generic cells that `lowrisc:prim:all` resolves to.

// --- include dirs (prim_assert.sv / prim_flop_macros.sv / prim_fifo_assert.svh live here) ---
+incdir+hw/ip/prim/rtl
+incdir+hw/ip/prim_generic/rtl
+incdir+hw/ip/tlul/rtl
+incdir+hw/ip/uart/rtl

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

// --- prim cells used by the uart closure ---
hw/ip/prim/rtl/prim_alert_sender.sv
hw/ip/prim/rtl/prim_alert_receiver.sv
hw/ip/prim/rtl/prim_alert_to_diff.sv
hw/ip/prim/rtl/prim_clock_gating_sync.sv
hw/ip/prim/rtl/prim_diff_decode.sv
hw/ip/prim/rtl/prim_diff_encode.sv
hw/ip/prim/rtl/prim_diff_to_alert.sv
hw/ip/prim/rtl/prim_edge_detector.sv
hw/ip/prim/rtl/prim_fifo_sync.sv
hw/ip/prim/rtl/prim_fifo_sync_cnt.sv
hw/ip/prim/rtl/prim_intr_hw.sv
hw/ip/prim/rtl/prim_onehot_check.sv
hw/ip/prim/rtl/prim_onehot_enc.sv
hw/ip/prim/rtl/prim_reg_we_check.sv
hw/ip/prim/rtl/prim_sec_anchor_buf.sv
hw/ip/prim/rtl/prim_sec_anchor_flop.sv
hw/ip/prim/rtl/prim_subreg.sv
hw/ip/prim/rtl/prim_subreg_ext.sv
hw/ip/prim/rtl/prim_subreg_shadow.sv
hw/ip/prim/rtl/prim_subreg_arb.sv

// --- prim secded (tlul integrity) ---
hw/ip/prim/rtl/prim_secded_pkg.sv
hw/ip/prim/rtl/prim_secded_inv_39_32_dec.sv
hw/ip/prim/rtl/prim_secded_inv_39_32_enc.sv
hw/ip/prim/rtl/prim_secded_inv_64_57_dec.sv
hw/ip/prim/rtl/prim_secded_inv_64_57_enc.sv

// --- technology-independent prim cells (prim_generic: prim_buf / prim_flop / prim_flop_2sync /
//     prim_clock_gating / prim_xnor2 / prim_xor2 / prim_and2 / prim_const) ---
hw/ip/prim_generic/rtl/prim_buf.sv
hw/ip/prim_generic/rtl/prim_flop.sv
hw/ip/prim_generic/rtl/prim_flop_2sync.sv
hw/ip/prim_generic/rtl/prim_clock_gating.sv
hw/ip/prim_generic/rtl/prim_xnor2.sv
hw/ip/prim_generic/rtl/prim_xor2.sv
hw/ip/prim_generic/rtl/prim_and2.sv
hw/ip/prim_generic/rtl/prim_const.sv
hw/ip/prim_generic/rtl/prim_const_sec.sv

// --- tlul ---
hw/ip/tlul/rtl/tlul_pkg.sv
hw/ip/tlul/rtl/tlul_adapter_reg.sv
hw/ip/tlul/rtl/tlul_cmd_intg_chk.sv
hw/ip/tlul/rtl/tlul_rsp_intg_gen.sv
hw/ip/tlul/rtl/tlul_data_integ_dec.sv
hw/ip/tlul/rtl/tlul_data_integ_enc.sv
hw/ip/tlul/rtl/tlul_err.sv

// --- uart (top = uart) ---
hw/ip/uart/rtl/uart_reg_pkg.sv
hw/ip/uart/rtl/uart_reg_top.sv
hw/ip/uart/rtl/uart_rx.sv
hw/ip/uart/rtl/uart_tx.sv
hw/ip/uart/rtl/uart_core.sv
hw/ip/uart/rtl/uart.sv

// --- top-level virtual constant packages (top_pkg / top_racl_pkg) ---
hw/top_earlgrey/rtl/top_pkg.sv
hw/top_earlgrey/rtl/autogen/top_racl_pkg.sv
