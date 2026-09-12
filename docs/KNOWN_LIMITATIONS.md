# 已知限制

> 更新: 2026-08-26 23:00 GMT+8 (case27 架构决策生效)
> 测试状态: 见 [INDEX.md 当前基线](INDEX.md#-当前基线-单一真相源--计数只写在这里)
>
> **架构决策**: `docs/architecture/case27_signal_graph_completeness_decision.md` (D1-D5 锁定, 含 v11-only)

### 5. pyslang 版本兼容代码 (~1.5h 清理, iter_034)

D5 锁定: 以后仅支持 v11 API, 不再考虑 v9/v10 兼容.

**当前 compat shim**: `src/trace/core/_pyslang_compat.py` (8327 bytes)
- `_detect_version()` — 版本探测 (v11 不需要)
- `_KIND_ALIASES` — kind 名字 v10/v11 映射
- `is_syntax_list` / `iter_syntax_list` — v11 已拆 plain list, 可能不需要
- 5 个调用点 (uvm_testbench_extractor / expression_tree / semantic_adapter / subroutine_expander / base)
- 4 个 hasattr probes (mig_validator / semantic_adapter x2 / graph_builder)
- 6 处 `[Stage 6] v10/v11 兼容` 注释

**iter_034 计划**: 全部清理, 直接用 `pyslang.ast.*` (v11 only API)

---

## 当前已知限制

### 1. generate-if/else 限制 (pyslang 已知)

当 `generate if (PARAM)` 控制哪个 always 块运行时，pyslang 的 `get_always_blocks()` 可能不枚举 else 分支。

**影响**: picorv32 `alu_shr`, `alu_add_sub`, `alu_eq`, `alu_lts`, `alu_ltu` 等信号没有 leaf driver。

**文档**: V6.4 `test_known_limitations.py`

### 2. ElementSelect 解析 (pyslang 已知)

`arr[N]` 被 pyslang `_get_signal` 解析为两个独立信号，位索引丢失。

### 3. pyslang 内存不足问题 — **归因已更正 (iter_185)**

> ⚠️ 2026-09-08 iter_185: "内存不足导致 elaboration 静默失败" 的归因**已被证伪** —
> 真因是 `SVCompiler` 的 `SourceManager` 生命周期 bug (buffer 提前释放 → 符号名悬垂
> `string_view`), 已修复。修复后同一输入 3 次完全一致 (stdev = 0.0)。
> 内存压力仍然会让 pyslang 变慢/失败, 但不再产生乱码名与结果漂移。

**文档**: `docs/PYSLANG_MEMORY_ISSUE.md` (已按真因改写),
`docs/task_tree/iterations/iter_185_slang_sourcemanager_lifetime.md`

### 3.1 pyslang 非设计单元输入 → 原生 SIGTRAP (iter_189, 已在我们层加守卫)

`pyslang`/`slang` 的 `Compilation.addSyntaxTree()` 在语法树根节点是**表达式**时
**直接 SIGTRAP** (exit 133, 无输出、无 Python 异常可捕获)。触发条件: 输入文本不是
SystemVerilog 设计单元 → slang 走 script 模式解析成表达式。最典型事故是**把
filelist 当源码传**:

```bash
sv_query visualize module -f project.f     # 曾经直接崩 (filelist 内容被当 SV 源码)
```

**我们层的守卫** (`src/trace/core/compiler.py::_reject_non_design_unit`): 在
`addSyntaxTree` 之前检查根节点类型, 表达式根 → 抛可行动的 `CompilationError`
(提示"是否把 filelist 当源码传入")。合法输入 (根节点 `CompilationUnit` /
`ModuleDeclaration` / `ClassDeclaration` / 空文件 / 仅 `define`) 不受影响。

**上游建议**: pyslang 应在 `addSyntaxTree` 里拒绝非设计单元树 (返回错误), 而不是 trap。
回归测试: `sim/tests/unit/test_compiler_non_design_unit_guard.py` (守卫失效时测试进程
会以 exit 133 死掉, 信号明确)。

### 4. 测试已知失败 (55 个，全部为 pre-existing)

| 模块 | 数量 | 原因 |
|------|------|------|
| test_fix_timescale | 6 | MissingTimeScale 检测差异 |
| test_fix_report | 2 | 报告格式变化 |
| test_deadlock_cli | 1 | naplespu filelist 不存在 |
| test_dataflow_else_if | 36 | 条件表达式比较差异 |
| test_dataflow_else_if_typo | 4 | 同上 |
| test_dataflow_golden | 3 | golden 比较差异 |
| test_ventus_all_viz | 5 | arch/trace/PNG 波动 |

**所有 55 个均为既存问题，与 V6.5-V6.7 改动无关。**

---

## 已修复限制

| 限制 | 修复版本 |
|------|---------|
| Binary operator 分解无法检测 op | V6.5 (DriverSource→SignalSource) |
| expression/bit_slice 用纯字符串存储 | V6.5 (SignalSource 结构化) |
| 可视化 6 个渲染器分散 | V6.7 (VizData 统一管线) |
| DriverInfo 不含位精确信息 | V6.6 (source: SignalSource) |
| pipeline 图 5 种变体混乱 | V6.6/V6.7 (deprecated load_dot) |
| NodeKind/EdgeKind 混乱 | V6.6 (命名空间分区) |

---

## ⚠️ 2026-08-26 case27 架构决策生效

### 接受为设计选择 (不再修)

| 项 | 原因 | 决策文档 |
|---|---|---|
| **case27 Gap 1** — `acc[i]` 显示模板 label `[i]` 而非 `[0..4]` | Semantic API 不展开 genvar 替换 | D2 |
| **case27 Gap 2** — generate-block 内 `prod[0..3]` 4 个 `*` op 节点缺失 | Semantic API 不 walk generate-block body | D2 |
| **generate-block 整体展平** | 可视化彻底展平到 module 顶层 | D3 |

### 仍待修 (核心约束: 信号图信息完整)

| 项 | 优先级 | 决策 |
|---|---|---|
| **case27 Gap 3** — module 顶层 `sum_out` ternary `?:` op 节点缺失 | ⭐⭐⭐⭐⭐ | iter_033 必做 |
| **"信号图信息完整" 定义** (A/B/C/D) | ⏳ 待用户选 | 待 Feishu 回复 |

---

## 📞 相关引用

- 决策文件: `docs/architecture/case27_signal_graph_completeness_decision.md`
- iter_032 (前置已知问题): `docs/task_tree/iterations/iter_032_case27_semantic_gaps.md`
- iter_033 (待开工): `docs/task_tree/iterations/iter_033_*.md` (创建中)
