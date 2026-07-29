# TESTING.md — 测试指南

> 最后更新: 2026-07-29

## 快速启动

```bash
# 核心回归测试 (不含 opensource 外部项目)
python -m pytest sim/tests/ -m "not opensource" -v

# 全量测试 (含外部项目)
python -m pytest sim/tests/ -v

# 只跑 golden 标记 (基准对比)
python -m pytest sim/tests/ -m golden -v

# 只跑 unit 测试 (不依赖外部项目)
python -m pytest sim/tests/unit/ -v
```

## 测试标记 (pytest markers)

| Marker | 含义 | CI |
|--------|------|-----|
| `golden` | 基准对比测试 (期望值与 pyslang 输出比较) | ✅ |
| `opensource` | 依赖外部开源项目 (ventus/picorv32/darkriscv/OpenTitan) | ❌ 本地跳过 |
| `slow` | 慢速测试 (>10s) | ⚠️ |

**本地开发推荐**: `python -m pytest sim/tests/ -m "not opensource"`

## 外部项目 (opensource) 管理

以下测试依赖外部开源项目源码，本地开发时自动跳过：

| 外部项目 | 本地路径 | 标记文件 |
|----------|---------|----------|
| ventus-gpgpu-verilog | `~/my_dv_proj/ventus-gpgpu-verilog` | `test_ventus_*_validation.py` |
| picorv32 | `~/my_dv_proj/picorv32` | `test_picorv32_validation.py` |
| darkriscv | `~/my_dv_proj/darkriscv` | `test_dataflow_latency_open_source.py` |
| OpenTitan | `~/my_dv_proj/opentitan` | `test_coverage_gen_demo_golden.py` |

**设计原则**: 测试的核心代码模式从这些项目中抽取，存储为 `sim/tests/integration/dataflow_fixtures/` 下的独立 `.sv` 文件。完整的开源项目使用场景迁移到 `docs/usage/`，不作为回归测试。

## 环境依赖

### 运行时依赖

- `/tmp/cdc_test/` — 部分 golden 测试的 fixture 文件存储位置
  - 从 `sim/tests/integration/dataflow_fixtures/` 复制
  - 文件: `sync_fifo.sv`, `two_flop_sync.sv`, `golden_mux5.sv`, `comprehensive.sv`, `edge2.sv`, `typo3.sv`, `typo4.sv`, `nested_not2.sv`

### CI 环境

- macOS runner (macos-latest)
- Python 3.11 / 3.12
- pyslang via GitHub source install

## 已知限制 (2026-07-29)

| 限制 | 状态 | 处理方式 |
|------|------|---------|
| pyslang 11.0+ 不再报 MissingTimeScale | 🔴 blocked | `test_fix_timescale.py` 相关 5 tests skipped |
| ventus 开源项目测试 | 🟡 opensource | pytest marker `opensource`，本地跳过 |
| picorv32/naplespu 项目测试 | 🟡 opensource | 已有 `skipif` |
| `/tmp/cdc_test/` fixture 依赖 | 🟡 runtime | conftest.py 可加 fixture setup |

## 2026-07-29 修复记录

本日共 8 个 commits，修复了 65 个测试失败中的核心问题：

### 纪律类修复 (10 failures → 3 fix + 7 skip)
- `test_evidence_assign_comb.py`: 行号漂移 6→7
- `test_localparam_driver_filter.py`: Conversion unwrap 修复 `_expr_is_compile_time`
- `test_advanced_syntax.py`: cross_module 新增 port 边界穿越 (3 drivers)
- `test_fix_timescale.py`: pyslang MissingTimeScale 不再支持 (5 skipped)
- `test_fix_report.py`: 同上 (2 skipped)

### Golden 修复 (34 failures → fix)
- `test_dataflow_else_if_comprehensive.py`: 铁律0 `2'b00`→`2'b0`
- `test_dataflow_golden.py`: fixture 文件 `/tmp/cdc_test/` 创建
- `test_dataflow_latency_open_source.py`: fixture 文件创建

### 新增功能
- `trace overview A B` (B 复合命令): `sim/tests/cli/test_trace_overview.py`
- CVA6 代码模式 fixture: `cva6_alu_pattern.sv`, `cva6_scoreboard_pattern.sv`, `cva6_frontend_pattern.sv`
- dataflow golden DOT 重新生成: `strict_uart.dot`
