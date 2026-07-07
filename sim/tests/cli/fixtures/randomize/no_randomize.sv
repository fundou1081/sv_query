// no_randomize.sv — 有 rand 但没 randomize() 调用 (consumed 但未 randomize)
class packet;
    rand bit [7:0] addr;
    rand bit [7:0] data;
endclass

class consumer;
    packet req;
    bit [7:0] out_addr;
    bit [7:0] out_data;

    task run();
        out_addr = req.addr;
        out_data = req.data;
    endtask
endclass

module top; endmodule
