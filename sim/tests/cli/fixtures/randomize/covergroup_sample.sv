// covergroup_sample.sv — rand var 被 covergroup sample
class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;

    covergroup cg;
        coverpoint addr {
            bins low  = {[0:63]};
            bins high = {[64:255]};
        }
        coverpoint mode {
            bins mode0 = {0};
            bins mode1 = {1};
            bins mode2 = {2};
            bins mode3 = {3};
        }
    endgroup

    function new();
        cg = new();
    endfunction
endclass

class covergroup_seq;
    packet req;

    task body();
        req.randomize();
    endtask
endclass

module top; endmodule
