# Control Coverage Generator V2 总结

> 报告时间: 2026-06-03 00:30
> 状态: ✅ V2 全部 4 个核心候选完成
> 路径: /Users/fundou/my_dvproj/sv_query
> Git: main 分支

---

## 1. V2 是什么

V2 是 Control Coverage Generator 的**纯增量功能扩展**,在 V1 (cycles 1-10, commits 4bff463..7c49161) 基础上,补齐 5 个 V1 遗留限制:

| 限制 | 解决状态 |
|------|---------|
| 跨模块信号 | ✅ V1 cycle 9 (1e2dda0) |
| 多信号同时 decompose | ✅ V2.B (cycles 14-15) |
| JSON 输出 | ✅ V2.C (cycles 12-13) |
| AST 自动提取 | ✅ V2.A.2 (cycles 16-18) |
| ControlFlowGraph 集成 | ❌ P1 单独重构 (V2 不做) |
| Z3 集成 | ❌ V3 (V2 不做) |

V2 严格遵守:**纯增量、不动 P0/P1、每个 cycle 独立 commit**。

---

## 2. 4 个核心子目标完成情况

### 2.1 V2.A (基础) - cycle 11

**目标**: TraceEdge 增加 `condition_ast` 字段 + AST 提取工具方法

| 指标 | 数据 |
|------|------|
| Commit | 6c41d65 |
| 代码改动 | 1 字段 + 4 个新方法 (`_extract_atomics_from_ast` / `_convert_signal_result_to_atomics` / `_is_simple_literal` / `_extract_condition_atomic`) |
| 测试 | +7 |
| 局限 | **代码就位但未在 decompose() 接入** (cycle 16 修复) |

### 2.2 V2.C (JSON 输出) - cycles 12-13

**目标**: 兑现 V1 `--json (TODO)` 占位符

| 指标 | 数据 |
|------|------|
| Commits | 243e5d8 (plan) / 8144c79 (cycle 12) / a3ed5da (cycle 13) / afb56de (docs) |
| Cycle 12 | 4 个 dataclass 加 `to_dict()`, 加 `to_json()` |
| Cycle 13 | CLI `--json` 真实现 + `--json` 模式静音编译器 WARNING |
| 测试 | +28 |
| 代码改动 | ~80 行 (models + CLI) |

**真实输出**:
```bash
$ python run_cli.py coverage suggest -f test.sv --signal top.x --json
{"original_signal": "top.x", "atomic_signals": [...], ...}
```

### 2.3 V2.B (多信号 decompose) - cycles 14-15

**目标**: `decompose()` 处理 `signals` 列表,合并去重

| 指标 | 数据 |
|------|------|
| Commits | 4b44e8e / df9cc33 / df734a0 / f27ac4d |
| Cycle 14 | `decompose()` 主循环重构 + `original_signals: list[str]` 新字段 |
| Cycle 15 | CLI 验证(零代码改动,V1 解析已对) |
| 测试 | +17 |
| 代码改动 | ~80 行 |

**关键设计**:
- 跨模块快速失败 (任一信号跨模块 → 整个报错)
- 去重键: atomics `name`, control_blocks `(src, dst)`
- max_signals 合并后判断

### 2.4 V2.A.2 (完整利用 AST) - cycles 16-18

**目标**: 让 cycle 11 装的 AST 入口**真正在真实数据上跑通**

| 指标 | 数据 |
|------|------|
| Commits | 2f52af8 / 0397192 / c0a8ebf / 3b3ebd0 / 8f84b27 / f58a898 / 01211b1 / 45114a8 |
| Cycle 16 | `decompose()` 走 `_extract_condition_atomic` (1 行) |
| Cycle 17a | visitor `new_ctx` 加 `condition_ast` 字段 (1 行) |
| Cycle 17b | graph_builder 1/8 TraceEdge 点填 AST (1 行) |
| Cycle 17c | `graph._adapter = semantic_adapter` (1 行) |
| Cycle 17d | 剩余 7/8 ctx-based 点填 AST (7 行) |
| Cycle 18 | CLI 端到端验证 |
| 测试 | +13 |
| 代码改动 | **+11 行 (4 个文件, 0 删除)** |

**真实输出**:
```bash
$ python run_cli.py coverage suggest -f test_data_path.sv \
    --signal data_path.result --max-signals 10 --json \
    | jq '.atomic_signals[].evidence[].description'

"AST extract: rst_n (kind=UnaryOp)"
"AST extract: pipeline_stall (kind=UnaryOp)"
```

**AST 填充率**: 0% → 100% (47/47 条件边全部带 condition_ast)

---

## 3. V2 总数据

| 指标 | V1 终态 | V2 终态 | Δ |
|------|--------|--------|---|
| **总测试** | 1322 | **1380** | **+58** |
| **总 commits** | 11 (V1) | 25 (V1 + V2) | +14 (V2 实施) |
| **V2 实施 net 代码改动** | - | **~190 行** | - |
| **V2 净代码改动 (V2.A.2)** | - | **+11 行** | - |
| **删除行数** | - | **0** | - |
| **ruff src/ 错误 (V2 新增)** | 7 (pre-existing) | 7 (不变) | 0 |
| **AST 路径填充率 (test_data_path.sv)** | 0% | **100%** | +100% |
| **JSON 输出占位符兑现** | TODO | ✅ | - |
| **多信号分解** | 仅第 1 个 | 全部 + 合并去重 | - |

---

## 4. 完整 V2 时间线

| 日期 | 事件 |
|------|------|
| 2026-06-02 17:35 | 用户询问 V2 状态,生成状态报告 |
| 2026-06-02 20:33 | (其他 session) cycle 11: V2.A 基础 (commit 6c41d65) |
| 2026-06-02 22:00 | 用户问"先做 C 吧" |
| 2026-06-02 22:30 | cycles 12-13: V2.C (JSON) |
| 2026-06-02 23:00 | 用户问"然后做 V2.B 吧" |
| 2026-06-02 23:30 | cycles 14-15: V2.B (多信号) |
| 2026-06-02 23:55 | 用户问"开始 V2.A.2, 小心, 避免误删" |
| 2026-06-03 00:00 | cycles 16-18: V2.A.2 (完整利用 AST) |
| 2026-06-03 00:25 | V2 收尾: 本文档 |

---

## 5. 关键经验教训 (V2 全程 19 条)

### V1 教训 (1-5)
1. **小步快跑**: 每个 cycle 一个特性, 可独立回滚
2. **优先复用**: 用 dataclasses.asdict 思想, 显式 to_dict()
3. **兼容异构**: ControlBlock 类型未来会变, 提前兼容
4. **测试先写**: TDD 强制覆盖每个 case
5. **真实 CLI 测试**: 跑 `run_cli.py` 验证实际输出

### V2.C 教训 (6-9)
6. **placeholder 兑现**: V1 留的 TODO 是明确目标
7. **stdout/stderr 分隔**: `--json` 模式必须静音编译 WARNING
8. **异构兼容**: control_blocks 类型未来会变
9. **bit_range tuple → list**: JSON spec 不支持 tuple

### V2.B 教训 (10-14)
10. **测试考虑 max_signals 默认值**: 多信号场景下默认 5 容易截断
11. **max_signals 是合并后总限制**: 跟 V1 语义一致
12. **TDD 救场**: cycle 14 调试时用临时 print 发现是 max_signals 截断
13. **零 CLI 改动不丢人**: V1 解析已对, V2 内部能力够自动工作
14. **list[Any] 注释要 import Any**: ruff 严格

### V2.A.2 教训 (15-19) ⭐ 最重要
15. **code path 就位 ≠ 真实使用**: 必须验证 data path
16. **adapter 传递**: 真 AST 路径需要 `_graph._adapter` 联通
17. **小步可独立回滚**: 4 文件各 1 行改动, 任何一步只损失 1 行
18. **TDD 红→绿 真实暴露问题**: 17c 写测试才发现 graph 缺 adapter
19. **CLI 端到端是最终验证**: 单元测试通过 ≠ 用户能用

---

## 6. 数据流图 (V2 终态)

```
SV 源文件
  ↓
[UnifiedTracer.build_graph()]
  │
  ├─→ [GraphBuilder]
  │     ├─ TraceEdge(condition_ast=ctx.get("condition_ast"))   ← 17b/17d
  │     └─ ctx 由 [StatementCollectorVisitor] 提供
  │            └─ visit_conditional_statement: new_ctx["condition_ast"] = cond_expr  ← 17a
  │
  └─→ self._graph._adapter = semantic_adapter  ← 17c
  ↓
SignalGraph (含 AST 数据 + adapter)
  ↓
[ControlCoverageGenerator.decompose()]
  │
  └─ _extract_condition_atomic(edge, primary)  ← 16
        │
        ├─ _extract_atomics_from_ast(ast_node)
        │     └─ SignalExpressionVisitor(graph._adapter).extract(ast_node)  ← 真 AST
        │           → 产出 atomic + evidence[step_type=ast_extract]
        │
        └─ _parse_expression_to_atomics(cond_str)  ← fallback
  ↓
AtomicSignal[] + control_blocks[]
  ↓
to_dict() / to_json()  ← 12
  ↓
CLI output (--json 模式)  ← 13/18
```

---

## 7. V2 风险控制复盘

V2.A.2 阶段用户明确说"小心, 避免误删"。最终做到的:

| 风险点 | 实际控制 |
|--------|---------|
| graph_builder.py 3054 行 | 仅改 8 个 TraceEdge 创建点(1 行/点),共 7 行 |
| graph_builder.py 17+ sig_cond 点 | **不动**,留给 P1 |
| graph_builder.py 拆 driver_extractor | **不动** |
| 误删已有功能 | 0 行删除 |
| 测试回归 | 1322 → 1380 (全程 +58, 0 失败) |
| ruff src/ 错误 | 7 (V2.A.2 前 7, 后仍 7, V2 没引入) |
| 每个 cycle 可独立回滚 | ✅ 14 个 V2 commits, 任一可 `git revert` |

**用户原话**:"TDD 的方式, 小心, 避免误删" → V2.A.2 11 行净代码, 0 删除, 6 步小步 commit 守住承诺。

---

## 8. 剩余工作 (不属于 V2)

### P1 范围 (V2 不做, 单独启动)
1. **graph_builder.py 3054 行拆分** (driver_extractor.py 独立, ~1554 行)
2. **sig_cond-based 创建点** (7+ 处,需 refactor 局部变量为 ctx)
3. **case 语句 cond_expr 透传** (visitor line 760-781 需类似 17a 改动)
4. **CONTROL_FLOW_BLOCK control_vars 已知 bug**

### V3 候选
1. **Z3 集成** - 关键值 bin 求解
2. **from_dict()** - JSON 反序列化
3. **JSON Schema** - 官方 schema 文件
4. **ControlFlowGraph 集成** - if/case 块精确识别

### 工程债
- 7 个 pre-existing ruff E402 错误 (compiler.py / cdc_analyzer.py / timing_analyzer.py)
- CVA6 子模块不展开
- fpnew_top 等不存在模块

---

## 9. V2 文档地图

| 文档 | 内容 | 状态 |
|------|------|------|
| `COVERAGE_GENERATOR.md` | 用户文档 | ✅ V1 |
| `COVERAGE_GENERATOR_PLAN.md` | V1 实施计划 | ✅ |
| `COVERAGE_GENERATOR_V1.md` | V1 发布说明 | ✅ |
| `COVERAGE_GENERATOR_V2.md` | V2 计划 + 4 个附录 (A. V2.C / B. V2.B / C. V2.A.2 plan / D. V2.A.2 result) | ✅ |
| **`COVERAGE_GENERATOR_V2_SUMMARY.md`** | **V2 总结 (本文档)** | ✅ |

---

## 10. 一句话总结

**V2 用 14 个 commits / ~190 行净代码 / +58 个测试,把 Control Coverage Generator 从 V1 限制版升级到 JSON 输出 + 多信号分解 + 完整利用 AST 的版本,全程 0 行删除,每个 cycle 独立可回滚。**
