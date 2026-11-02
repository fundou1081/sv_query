# Task: 修正 indexed part-select / 多 top 位选前缀（P51）

**状态**: 已完成
**来源**: P50 bit consistency 发现 verilog-axi 269 / picorv32 2 parent 越界。

## 可验证目标

1. `bus[base +: width]` 生成 `bus[base+width-1:base]`，不再生成 `[base:width]`；
2. multi-top filelist 中每个 top 的位选使用自己的 namespace，不共用第一个 top 前缀；
3. `verify consistency --checks bit` 在 verilog-axi 的越界数下降（目标 0 或只剩已解释的表达式边）；
4. 新增 indexed / multi-top 测试；全量门禁 + 文档。

## 边界

- 不修改用户 RTL；
- 只修 extraction 的 ID/范围归一化；
- `mem_done[1]` 若另有来源，单独记录。
