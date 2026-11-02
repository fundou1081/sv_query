# Task: parent width 元数据调查（P52）

**状态**: 已完成
**来源**: P51 修正后剩余 verilog-axi 12 条 / picorv32 2 条 parent_range_out_of_bounds。

## 可验证目标

1. 解释 `out_hdr_next` parent width 为什么是 `(1,0)` 而不是 `HDR_WIDTH=18`；
2. 解释 `mem_done[1]` 的 bit1 从哪条路径生成；
3. 能修的修，不能修的写清可观察后果；
4. 测试 + 全量门禁 + 文档。

## 边界

- 不改用户 RTL；
- 不用 heuristic 猜 width 掩盖问题；
- parent width 不可靠时 bit check 必须显式标 unknown，而不是假 pass。
