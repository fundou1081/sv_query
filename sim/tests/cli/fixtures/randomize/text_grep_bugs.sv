// text_grep_bugs.sv — exposes text-grep false positives
class packet;
    rand bit [7:0] used_real;       // 真 consumer in run()
    rand bit [7:0] unused_real;     // 真没 consumer — should be dead
    rand bit [7:0] only_in_comment;  // 只在 comment 里 — 应该 dead (NOT alive)
    rand bit [7:0] only_in_string;   // 只在 string 里 — 应该 dead
endclass

class consumer;
    packet req;
    bit [7:0] my_other_addr;     // 名字包含 'addr' — 但跟 used_real 无关

    task run();
        // 注释里提了 only_in_comment, 不该算 consumer
        // only_in_comment is a comment, not code

        // 真 consumer — used_real
        my_other_addr = req.used_real;

        // 只在 string 里: $display("only_in_string = %h", req.unused_real);
        // string 里的 var name 是 user output text, 不算 consumer
        $display("only_in_string = %h", req.unused_real);

        // 没用 only_in_comment / unused_real 真正读
    endtask
endclass

module top; endmodule
