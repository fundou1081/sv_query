// multi_randomize.sv — 同一 var 多次 randomize() with different constraints
class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;
endclass

class multi_seq;
    packet req;

    task body();
        req.randomize();
        req.randomize() with { addr < 64; };
        req.randomize() with { addr >= 128; mode != 0; };
    endtask
endclass

class consumer;
    packet req;
    bit [7:0] out_addr;

    task run();
        out_addr = req.addr;
    endtask
endclass

module top; endmodule
