# 已知限制

> 更新: 2026-07-29
> 测试状态: 2958 tests, 2876 passed (97.1%), 55 pre-existing failures, 0 new

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
