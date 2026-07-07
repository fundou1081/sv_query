// function_randomize.sv — randomize() 在 function body (跟 task 一样)
class packet;
    rand bit [7:0] addr;
endclass

class fn_seq;
    packet req;
    bit ok;

    function bit do_randomize();
        ok = req.randomize() with { addr < 64; };
        return ok;
    endfunction
endclass

class consumer;
    packet req;
    bit [7:0] out_addr;

    function void consume();
        out_addr = req.addr;
    endfunction
endclass

module top; endmodule
