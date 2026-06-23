//==============================================================================
// uvm_packet_coverage_demo.sv
//
// Real UVM-style packet class with constraint + covergroup, designed to
// showcase `coverage gap` CLI command output.
//
// Scenario: a typical random packet generator with conditional constraints
// (mode-based address range selection). Common verification gap: developers
// forget to write `cross mode, addr` and `illegal_bins` for the conditional
// branches.
//==============================================================================

class base_packet;
    rand bit [7:0]  addr;
    rand bit [3:0]  length;
    rand bit        valid;
endclass

class packet extends base_packet;
    rand bit [1:0]  mode;
    rand bit [3:0]  opcode;

    // Conditional constraint: address range depends on mode
    constraint c_addr {
        if (mode == 2'b00) {
            addr < 8'h40;          // low range
        } else if (mode == 2'b01) {
            addr inside {[8'h40:8'h7F]};  // mid range
        } else {
            addr inside {[8'h80:8'hFF]};  // high range
        }
    }

    constraint c_opcode {
        if (valid) {
            opcode != 4'h0;
        } else {
            opcode == 4'h0;
        }
    }

    // Covergroup — intentionally INCOMPLETE to demonstrate gap detection:
    //   - coverpoint on addr and mode exist
    //   - coverpoint on opcode and valid exist
    //   - BUT: no cross (mode, addr)  → missing_cross for (mode, addr)
    //   - AND: no cross (valid, opcode)
    //   - AND: no illegal_bins to exclude forbidden combinations
    covergroup cg;
        coverpoint addr  { bins lo[] = {[0:63]}; bins hi[] = {[64:255]}; }
        coverpoint mode  { bins m[]  = {[0:3]}; }
        coverpoint valid { bins v[]  = {[0:1]}; }
        coverpoint opcode{ bins op[] = {[0:15]}; }
        // missing: cross mode, addr
        // missing: cross valid, opcode
        // missing: illegal_bins
    endgroup

    function new();
        cg = new();
    endfunction
endclass

module top;
endmodule