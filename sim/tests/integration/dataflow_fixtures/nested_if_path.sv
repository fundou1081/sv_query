// nested_if_path.sv — 嵌套 if 导致多路径
// 预期: sel_a → result 应该有 2 条路径:
//   1. sel_a → (inner if sel_b) → data_a → result
//   2. sel_a → (inner if !sel_b) → data_b → result  
module nested_if_path(
    input  wire       sel_a,
    input  wire       sel_b,
    input  wire [7:0] data_a,
    input  wire [7:0] data_b,
    output reg  [7:0] result
);
    reg [7:0] intermediate;
    always @* begin
        if (sel_a) begin
            if (sel_b)
                intermediate = data_a;
            else
                intermediate = data_b;
        end else begin
            intermediate = 8'd0;
        end
        result = intermediate;
    end
endmodule
