# Iteration 264: 清理 exp 退役后失联的 14 个库模块（src −5,127 行）

**Metadata**:
- **Iteration #**: 264
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（承接 iter_263 exp 退役）
- **Outcome**: ✅ 成功（src 145→130 文件、51,607→46,480 行；全量 2310 passed / 0 failed）

## 🎯 目标

exp 退役后，有一批 trace 库模块**失去了唯一的调用方** —— 它们只被测试引用，
产品里没有任何入口能到达。按"exp 是未落地的想法，代码归档、想法留档"的口径，
这批也应当归档，否则等于把死代码留在 `src/` 里。

## 🔬 判定方法（先扫再删）

1. **静态导入扫描**：解析全部 `src/` 的 import（含相对导入），找出没有任何引用者的模块
2. **逐个复核**：对每个候选再 `grep` 一遍（防止动态 import / 注释误判）
3. **检查测试**：找出"只测这些模块"的测试文件；混合文件只删依赖死模块的用例

## 📦 归档清单（14 个模块 / 5,127 行）

| 模块 | 行数 | 原用途 |
|---|---|---|
| `coverage_generator.py` | 950 | 覆盖率建议生成（exp coverage） |
| `uvm_testbench_extractor.py` | 592 | UVM testbench 抽取（exp） |
| `graph/analyzer/pattern_matcher.py` | 470 | 定点计算模式匹配 |
| `handshake_detector.py` | 456 | valid/ready 语义判定（exp handshake） |
| `call_graph_builder.py` | 388 | randomize 调用图（exp randomize） |
| `mig_validator.py` | 326 | MIG 校验工具 |
| `cli/core/locate/stats.py` | 273 | **与 main.py 内联 `stats` 重复的实现** |
| `visitors/constraint_visitor.py` | 226 | constraint 访问器（exp） |
| `covergroup_analyzer.py` | 221 | covergroup 结构分析（exp coverage） |
| `cdc_analyzer.py` | 187 | CDC 检测（exp cdc） |
| `builder/expression_builder.py` | 165 | expression 节点构造（dev 已归档） |
| `graph/analyzer/stage_inferrer.py` | 105 | 流水级推断 |
| `timing_analyzer.py` | 100 | 关键路径（exp timing） |
| `covergroup_binding.py` | 98 | covergroup ↔ class 绑定 |

顺带删掉空包 `src/trace/core/visitors/`（注释写着"全部 visitor 已删除"，只剩一个空壳）。

## 🧹 测试处理

| 情况 | 处理 | 数量 |
|---|---|---|
| 专门测这些模块的文件 | 归档 | 22 个文件（−310 用例） |
| 混合文件里依赖死模块的用例 | 删除方法 | covergroup 4 个文件 12 个方法；`test_pyslang_v11_aliases` 1 个 |
| `test_constraint_complete` / `test_constraint_deep_parsing` | 整文件归档（89 个用例全部依赖 ConstraintVisitor） | 2 个 |

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| `src/` 文件 / 行数 | 145 / 51,607 | **130 / 46,480（−5,127）** |
| 测试文件 | 325 | **300** |
| 全量门禁 | 2633 passed | **2310 passed / 0 failed**（−323） |

## 💡 决策

1. **"只有测试在用" = 死代码**。测试不是消费者；一个模块若只能被测试调用，说明它的
   产品入口已经消失。留着它会让 `src/` 的度量虚高，也会让后来者以为它是可用能力。
2. **先扫后删，逐个复核**：静态扫描有假阳性（`cli._entry` 是 console script 入口、
   `cli.errors` 被 `from src.cli.errors` 延迟导入、`viz/checker` 被手工脚本使用），
   所以每个候选都单独 grep 过。
3. **混合测试文件只删相关用例**：`test_covergroup.py` 等同时覆盖仍在用的
   `CovergroupExtractor`，整文件归档会误伤活代码的回归保护。

## 🔗 相关

- 前序: [iter_263 exp 区整体退役](iter_263_exp_retirement.md)
- 想法清单: [docs/EXP_IDEAS.md](../../EXP_IDEAS.md)
- 归档: [docs/archive/2026-10-20-exp-attic/README.md](../../archive/2026-10-20-exp-attic/README.md)
