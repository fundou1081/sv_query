# Task: P171.4.2 full fanin/fanout merge

**状态**: 进行中
**日期**: 2026-11-14

目标：fanin/fanout 共享 per-signal facts + filter/cap + output formatter，
每个函数 CC<10；保留 drivers/loads 输出语义。

验收：
- canonical 2744 passed / 0 failed；
- opensource 112 passed / 11 skipped / 0 failed；
- check_crap 通过；
- worker 复核无 High/Medium。
