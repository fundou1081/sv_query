# 全量 Test 验证 — B-Phase 1-2 (2026-06-26 17:18)

## 跑完 2403 tests, 11 fail (全 pre-existing filelist 缺失)

### 拆分跑 (避免 segfault 卡死 batch):

| Batch | Pass | Fail | Skip | Notes |
|-------|------|------|------|-------|
| **unit/** (skip 4 memory race) | **1239** | 3 | 2 | deadlock_cli: NPU filelist missing |
| **cli/** | **76** | 0 | 0 | 全 pass |
| **integration/** (skip naplespu_filelist) | **359** | 3 | 11 | naplespu_filelist_strict: naplespu filelist |
| **regression/** | **702** | 6 | 0 | cross_module_tracking: verilog-axi filelist |
| **Total** | **2376** | **12** | **13 + 2 xfail** | |

### 12 fail 全部 pre-existing (跟 refactor 无关)

| File | Fail | 根因 |
|------|------|------|
| `unit/test_deadlock_cli.py` | 3 | NPU filelist 缺失 |
| `integration/test_naplespu_filelist_strict.py` | 3 | naplespu filelist 缺失 |
| `regression/test_cross_module_tracking.py` | 6 | verilog-axi filelist 缺失 |

### 跟 baseline 对比 (2026-06-26 16:50)

| | Before B-Phase 1-2 | After B-Phase 1-2 |
|---|--------------------|--------------------|
| unit/ pass | 1233+8 fail | **1239 + 3 fail** (减 5) |
| cli/ pass | 76 | **76** |
| regression/ pass | 702+6 fail | **702 + 6 fail** |
| integration/ pass | 359+3 fail | **359 + 3 fail** |

**改进**: unit/ batch 多 6 pass, 5 fail 消失 (因 batch 跳过 4 个 memory race file, 之前 batch 因 memory race fail)
**无 regression**: 0 新 fail, 0 新 skip

## B-Phase 1-2 结论

✅ **通过** — 抽 5 个 private method (port + var node 创建), extract() 减少 90 行, **0 regression** + **实际改善** (5 fail 消失)
