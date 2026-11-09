# Iteration 446: P136.3 TB→RTL candidate join

**状态**: ✅
**日期**: 2026-11-09

## 实现

`trace tb-join <tb_field> --filelist TB --from-snapshot RTL`：
- 返回 TB constraints；
- 按 leaf name 返回所有 RTL candidates；
- `join_status = unique | ambiguous | not_found`；
- 不静默选一个候选。

## 验证

synthetic unique + I2C rcont/nakok ambiguous；
test_tb_join.py 1 passed。

## 边界

name-based，不是 driver/BFM 映射证明。
