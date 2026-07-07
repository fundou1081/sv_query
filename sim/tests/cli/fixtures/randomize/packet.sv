class packet;
    rand bit [7:0] addr;
    randc bit [3:0] mode;
    rand bit [7:0] data;
    bit [7:0] not_rand;

    constraint c_addr {
        addr inside {[0:63]};
        mode != 0;
    }

    function void pre_randomize();
        // user-defined pre_randomize hook
    endfunction

    function void post_randomize();
        // user-defined post_randomize hook
    endfunction
endclass

class my_seq;
    packet req;
    bit ok;
    task body();
        req.randomize();
        req.randomize() with { addr < 64; mode != 1; };
        ok = req.randomize() with { data == 8'hAB; };
    endtask
endclass

module top;
endmodule
