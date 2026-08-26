# 已知限制

> 更新: 2026-08-26 23:00 GMT+8 (case27 架构决策生效)
> 测试状态: 2958 tests, 2876 passed (97.1%), 55 pre-existing failures, 0 new
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

### 3. pyslang 内存不足问题

8GB MBA 上 pyslang elaboration 内存不足时静默失败（UnicodeDecodeError / 随机 graph 大小）。

**修复**: 跑 `python3 -c "import time; a = bytearray(4*1024**3); time.sleep(3); del a"` 再跑 sv_query。

**文档**: `docs/PYSLANG_MEMORY_ISSUE.md`

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
