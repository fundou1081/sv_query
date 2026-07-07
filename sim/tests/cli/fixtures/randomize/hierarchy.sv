// hierarchy.sv — 多层 consumer (driver + monitor + scoreboard)
class packet;
    rand bit [7:0] addr;
    rand bit [7:0] data;
    rand bit [3:0] mode;
    randc bit [1:0] prio;
    rand bit [1:0] tag;
    rand bit [3:0] seq_id;
endclass

class driver;
    packet req;
    bit [7:0] out_addr;
    bit [7:0] out_data;
    bit [3:0] out_mode;
    bit [1:0] out_prio;

    task run();
        out_addr = req.addr;
        out_data = req.data;
        out_mode = req.mode;
        out_prio = req.prio;
    endtask
endclass

class monitor;
    packet req;
    bit [1:0] out_tag;
    bit [3:0] out_seq_id;

    task observe();
        out_tag = req.tag;
        out_seq_id = req.seq_id;
    endtask
endclass

module top;
    driver drv;
    monitor mon;
endmodule
