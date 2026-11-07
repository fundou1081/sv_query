# Iteration 397: A/D 充分测试（P93）

**状态**: ✅
**日期**: 2026-11-07

## 覆盖

- prune scanner 边界/链式/fallback；
- `trace --prune` parity/错误路径；
- `filelist prune --output` / top missing；
- snapshot paths parity/无效 tag/互斥；
- AXI/SERV 8-task pruned matrix。

## 结果

- AXI 4/4，SERV 4/4；
- AXI 0.81–1.04s，SERV 1.25–1.33s；
- snapshot AXI load0.54s / path0.49s，SERV path0.23s；
- 2571 passed / 0 failed。
