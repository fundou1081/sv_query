# 文档 vs 代码 系统性核对报告 (2026-08-26)

> 目的: 找出项目文档与实际代码不一致的地方。**只总结, 不修改**。
> 审计方式: 对比 `docs/` + `README.md` + `docs/task_tree/` 声称的内容 vs `src/` + `run_cli.py` + git 实际状态。

---

## 🔴 严重不一致 (文档声称 vs 代码/现状明显不符)

### 1. README 测试数虚高
| 项 | 文档声称 | 实际 |
|----|---------|------|
| 测试总数 | `2958 测试 (97.1% pass)` | `pytest --collect-only` 实际收集 **3131 tests** |
| 说明 | — | 数字过时, 且 2958 < 实际 3131, 方向也不同 |

### 2. README "7 个开源项目" 只有 4 个存在
README 声称验证过: `picorv32, darkriscv, CVA6, OpenTitan, Ventus, CoralNPU, NaplesPU`
实际 `~/my_dv_proj/` 中只找到 **4 个**:
- ✅ picorv32 / darkriscv / cva6 / opentitan
- ❌ **ventus / coralnp / naples 目录不存在**

### 3. ARCHITECTURE.md CLI 命令数不符
| 项 | 文茕声称 | 实际 |
|----|---------|------|
| CLI 命令数 | `CLI Layer (27 commands)` | `run_cli.py --help` 实际 **22 个子命令** (含正式+experimental) |

(22 个: stats, search, trace, diff, snapshot, dataflow, controlflow, risk, sva, timing, cdc, coverage, verify, backpressure, handshake, protocol, visualize, arch, design, fix, randomize, expression, graph — 数下来是 23, 也 ≠ 27)

### 4. ARCHITECTURE.md extractor 行数不符
| Extracter | 文档声称 | 实际 |
|-----------|---------|------|
| driver_extractor.py | 2639 行 | **3987 行** (+1348) |
| load_extractor.py | 423 行 | 391 行 |
| connection_extractor.py | 503 行 | 515 行 |
| module_extractor.py | 467 行 | 468 行 |

### 5. ARCHITECTURE.md models.py 行数不符
| 项 | 文档声称 | 实际 |
|----|---------|------|
| models.py | 663 行 | **744 行** (+81) |

---

## 🟡 中度不一致 (目录/引用过时)

### 6. DOC_INDEX.md 声称的目录不存在
DOC_INDEX.md (更新 2026-05-31) 分类目录声称存在:
- `docs/core/` ❌ 实际不存在
- `docs/dataflow/` ❌ 实际不存在
- `docs/controlflow/` ❌ 实际不存在
- `docs/skeleton/` ❌ 实际不存在
- 只有 `docs/architecture/` (10 文件) 存在

### 7. DOC_INDEX.md 文档统计不符
| 项 | DOC_INDEX 声称 | 实际 |
|----|---------------|------|
| docs/ 根目录 | 64 | **85** |
| docs/archive/ | 21 | **24** |
| docs/architecture/ | 9 | **10** |
| 总计 | 90+ | 实际更多 |

---

## 🟠 严重过时的文档 (更新日期 vs 功能演进)

### 8. USER_GUIDE.md 几乎空的
- **554 行, 但只有 1 个命令的 `##` 标题 (`stats`)** — 其余 21 个命令未文档化
- 完全没覆盖: trace/dataflow/controlflow/cdc/sva/risk/visualize/arch/design/coverage/verify 等核心命令
- 对比实际 23 个子命令, USER_GUIDE 覆盖率 ~4%

### 9. CLI_COMMAND_CHEATSHEET.md 是 7-06 快照
- 标注 `Generated 2026-07-06`
- 声称 "22 top-level commands, 52 subcommands" — 但未包含后续加入的 `expression`/`graph`/`verify` 等命令的完整更新

### 10. PROJECT_PLAN.md 更新 2026-05-31
- 声称 OpenTitan "✅ 完成 176 题", verilog-axi "🔄 进行中 32" 等
- 未反映 6-8 月的 viz/design/backpressure/handshake 等大量新功能
- `README.md` 声称的功能 (arch show, design, backpressure) 完全没进 PROJECT_PLAN

---

## 🔵 引用/命名不一致

### 11. `--dot` flag 残留 (已改名为 `--svg`)
10 个文档仍引用废弃的 `--dot` flag:
- docs/USER_GUIDE.md
- docs/VIZ_COMMANDS.md
- docs/README.md
- docs/ARCH_VISUALIZATION.md
- docs/PRIMARY_FEATURES.md
- docs/archive/2026-07-29-cleanup/DESIGNER_PLAN.md
- docs/NAPLESPU_TEST_ISSUES_2026_06_11.md
- docs/task_tree/iterations/iter_014 / iter_020
- docs/debugging_lessons/2026-08-25_plan_b_step_g_picorv32_wb_port.md

(实际 commit `7701a4e` 已将 `--dot` flag 改名为 `--svg`)

### 12. PRIMARY_FEATURES.md 过期
- 更新 `2026-07-04`
- 声称主推 "latency 子功能" — 需确认当前 CLI 是否还有 `latency` (README 主推已变成 V6/V6.7 viz + design)

---

## ✅ 一致的部分 (无问题)

- `VIZ_COMMANDS.md` 存在 (14.9KB), ARCH_VISUALIZATION 引用有效
- `models.py` NodeKind/EdgeKind 定义与 ARCHITECTURE 描述**一致** (SIGNAL/WIRE/REG/PORT_*/DRIVER/CLOCK/RESET 等)
- Extractor 层 5+3 结构基本属实 (8 个 extractor 文件都在)
- Query 层 (UnifiedTracer / query/{signal,load,module,clock_domain}.py) 存在
- `visualize` 子命令丰富 (graph/dataflow/pipeline/compute/timed/gap/chain/module/teach/datapath) 与 CHANGELOG V6-V6.9 演进一致
- DESIGN_composition_chain.md / SPEC_UVM_TESTBENCH_* / SYNTAX_KIND_HANDLER_MAP 等专向文档存在

---

## 📊 总结: 需要修正的优先级建议

| 优先级 | 文件 | 问题 |
|--------|------|------|
| 🔴 P0 | README.md | 测试数 2958→3131; 项目数 7→4 |
| 🔴 P0 | ARCHITECTURE.md | 命令数 27→23; extractor/models 行数过时 |
| 🟡 P1 | DOC_INDEX.md | 目录结构与实际不符 (core/dataflow/controlflow/skeleton 不存在) |
| 🟡 P1 | USER_GUIDE.md | 覆盖率 ~4%, 21/22 命令缺失 |
| 🟠 P2 | CLI_COMMAND_CHEATSHEET / PROJECT_PLAN / PRIMARY_FEATURES | 更新日期 2-3 个月前, 功能已大改 |
| 🔵 P2 | 10 个文档 | `--dot` → `--svg` flag 残留 |

> ⚠️ 本次仅总结, 未做任何修改。如需修复, 按优先级逐项更新。
