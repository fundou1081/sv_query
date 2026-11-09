# Iteration 443: FIFO/bus connectivity（P135）

**状态**: ✅
**日期**: 2026-11-09

## 实现

- 父总线 fanin 聚合 bit driver；
- `EdgeKind.FIFO` + FifoBridgeBuilder；
- `paths --through-fifo` 显式跨 FIFO；
- 默认路径/verify 不变。

## 验证

- I2C `nakok.q -> fmt_flag_nak_ok` 通过；
- FIFO synthetic 2 tests；
- bus aggregation 1 test；
- path semantics 32 tests。

## 剩余

P136：false warning、architecture snapshot/cache、TB→RTL join、solve/dist、unknown flag。
