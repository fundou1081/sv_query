package cg_pkg;

class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;

    covergroup cg;
        option.per_instance = 1;

        coverpoint addr {
            bins low  = {[0:63]};
            bins high = {[64:255]};
            bins mid  = {[100:150]};
            illegal_bins bad = {[200:255]};
        }

        coverpoint mode {
            bins mode0 = {0};
            bins mode1 = {1};
            bins mode2 = {2};
            bins mode3 = {3};
        }

        cross addr, mode {
            illegal_bins addr_high_mode_low = binsof(addr.high) && binsof(mode.mode0);
        }
    endgroup

    function new();
        cg = new();
    endfunction
endclass

class my_seq;
    packet req;
endclass

endpackage
