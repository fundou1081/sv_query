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

### 3.1 `-f` / `--file` 传 filelist → 原生 SIGTRAP (用法不一致, 不是上游缺陷)

> **方豆判定 (2026-09-09)**: 这是**用法不一致**问题 —— **不向上游 pyslang 报 issue**,
> 记录清楚并**避免这样使用**即可 (见 `AGENTS.md` 核心纪律 4)。

**正确用法**: `-f` / `--file` 只接受 SystemVerilog **源码**; filelist 一律用 `--filelist`。

```bash
sv_query visualize module -f project.f          # ❌ 禁止 (用法错)
sv_query visualize module --filelist project.f --target top   # ✅
sv_query stats -f design.sv                     # ✅ 单文件源码
```

**为什么会崩 (机制)**: filelist 的内容 (如 `/path/to/mod.sv`) 被当源码解析 →
slang 走 script 模式 → 根节点成了**表达式** (`DivideExpression`, 因为路径里有 `/`) →
`pyslang` 的 `Compilation.addSyntaxTree()` **直接 SIGTRAP** (exit 133, 无输出、
无 Python 异常可捕获, `faulthandler` 也拿不到栈)。

**本项目已加的守卫 (机械保障)**: `src/trace/core/compiler.py::_reject_non_design_unit`
在 `addSyntaxTree` 之前检查根节点类型, 表达式根 → 抛可行动的 `CompilationError`
(提示"请用 `--filelist`")。合法输入 (根节点 `CompilationUnit` /
`ModuleDeclaration` / `ClassDeclaration` / 空文件 / 仅 `define`) 不受影响。

回归测试: `sim/tests/unit/test_compiler_non_design_unit_guard.py` (守卫失效时测试进程
会以 exit 133 死掉, 信号明确)。

### 3.2 `MissingTimeScale` 诊断不触发 → `diagnose timescale` 形同虚设 (iter_234 发现)

`svq diagnose timescale` (原 `fix timescale`) 的判定依赖编译器报 `MissingTimeScale`,
但**实测当前 pyslang + 我们的编译配置下该诊断不触发**:

```
# 构造: 缺 `timescale 的模块 (含 #5 延迟)
svq diagnose timescale --filelist p.f   →  ✅ No MissingTimeScale errors found. Nothing to fix.
```

推断: 该诊断可能只在特定选项/上下文下出现 (e.g. 命令行 `--timescale` 未给 + 需要时间语义的构造),
而我们没有开启对应条件 → **命令对任何输入都返回"无需修复"**。

**旁证**: 仓库里原有两个 `--apply` 端到端测试**早已被注释** (注释写着"如果 pyslang 不报 MissingTimeScale…"),
说明这条路径从未被真正验证过。

**当前处置 (iter_234)**: 不掩盖 —— 写入逻辑抽成 `tools/fix_timescale.py::apply_timescale_to_files()` 直接单测
(写入 + `.bak` + idempotent 已验证); 命令本身的"触发条件"问题**待单独诊断** (新任务, 需查 pyslang 选项)。

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
