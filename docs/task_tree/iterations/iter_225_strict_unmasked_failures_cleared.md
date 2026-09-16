# Iteration 225: 严格模式暴露的 12 个失败清零 — 门禁只剩可视化 16 红

**Metadata**:
- **Iteration #**: 225
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_remove_strict.md` (收尾: "严格模式暴露的 fixture 真错")
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (goal 轮 2)
- **Outcome**: ✅ 成功 (28 failed → **16 failed**, 且 16 个全是方豆指示暂缓的可视化项)

## 🎯 本次目标

iter_224 把全仓 strict 清零后, 门禁剩 **28 failed** = 16 (可视化, 方豆指示暂缓) + **12**。
这 12 个不是 strict 移除引入的, 而是**过去被 `strict=False` 掩盖的真问题**在恒定严格下暴露出来的。

方豆指令 (本轮延续): **"继续做, 直到全部完成。"**
goal 的验收标准写的是"最终全量只剩按方豆指示暂缓的可视化失败 (16 个)" → 本轮清除这 12 个。

12 个的分布:

| 文件 | 数量 | 本质 |
|---|---|---|
| `unit/test_fix_report.py` | 4 | fix 类命令在恒定严格下无法工作 |
| `unit/test_fix_imports.py` | 4 | 同上 |
| `unit/test_pyslang_type_extraction.py` | 3 | filelist 缺依赖文件 → 位宽拿不到 |
| `unit/test_f2_generate_expression_trees.py` | 1 | 用例锁定的是"降级语义" (非法 SV 仍继续跑) |

诊断为**三个互不相同的根因**, 不是同一类, 分别处理。

## 🔬 根因 1: filelist 不完整 (3 个) — 与 iter_223 同类

NaplesPU 语料的 filelist 只有 `npu_core_logger.sv`:

```
[ERROR] npu_core_logger.sv:123:2: [UnknownModule] unknown module 'memory_bank_1r1w'
[ERROR] npu_core_logger.sv:142:2: [UnknownModule] unknown module 'memory_bank_1r1w'
```

`memory_bank_1r1w` 定义在**同仓库** `src/common/memory_bank_1r1w.sv` (实测存在)。
过去 `parse_width_from_pyslang` 走 `strict=False` → elaboration 报错但继续 →
`events_counter` / `mc_address_i` / `clk` 三个信号解析成 `None` → 3 个断言红。

**修法 (根因层, 非症状层)**: 补全 filelist (加 `+incdir+src/common` + 源文件),
**不是**改断言、**不是**恢复非严格模式。

```
sim/tests/unit/test_pyslang_type_extraction.py: 87 passed (原 84 passed / 3 failed)
```

> 同一个坑 (「测试语料缺依赖文件」) 这是第二次 (iter_223 是 darkriscv 的 `spi_master`)。
> 结论: `strict=False` 时代留下的语料普遍**不完整**, 撤掉降级后必须逐个补全 —— 这是
> 移除 strict 的**必然代价**, 也是它最大的价值 (把假绿变成真红)。

## 🔬 根因 2: fix 类命令的输入本身就是"坏项目" (8 个)

`fix report` / `fix imports` 的职责**就是诊断有错的项目**, 但恒定严格下
`build_graph()` 抛 `CompilationError`, 而命令的 `except Exception → exit 1`
把这个**预期状态**当成致命错误 → 8 个测试红:

```
E  assert 1 == 0
E  [ERROR] main.sv:3:33: [UndeclaredIdentifier]
E  [ERROR] broken.sv:3:33: [UndeclaredIdentifier]
```

**这不是"该不该严格"的问题, 是契约缺失**: 过去靠 `strict=False` 隐式让编译"不抛",
现在必须**显式声明**"编译失败 = 本命令的预期输入"。

**方案 A (采纳)**: `cli/_common.py` 新增结构化诊断入口

```python
@dataclass
class ElaborationDiagnostics:
    tracer: UnifiedTracer
    errors: list[dict]
    compile_failed: bool = False
    failure: str = ""

def collect_elaboration_diagnostics(file=None, filelist=None, log_level="ERROR"):
    tracer = _build_tracer(...)
    try:
        tracer.build_graph()
    except CompilationError as e:          # 只捕获这一个
        errors = tracer.get_elaboration_errors()
        if not errors:
            raise                          # 拿不到失败原因 = 真异常, 不吞
        return ElaborationDiagnostics(tracer, errors, True, str(e))
    return ElaborationDiagnostics(tracer, tracer.get_elaboration_errors())
```

4 个 fix 命令 (`report` / `imports` / `timescale` / `widths`) 全部改用它。

**为什么这不是 silent fallback (纪律 2)**:
- 只捕获 `CompilationError` (其它异常照抛);
- 读的是编译器**已收集的结构化诊断** (`get_elaboration_errors()`), **不解析报错文本**;
- **不把 partial AST 当成功返回**给上层 (graph 仍然不可用, 命令用的是诊断列表);
- 拿不到诊断就 `raise` —— 失败仍然可见。

**方案 B (未采纳)**: 让命令 `except CompilationError` 后解析错误字符串。
→ 违反"结构化数据优于字符串" (纪律 6.6), 且错误文本一旦改格式就崩。

**方案 C (未采纳)**: 给这些命令单独恢复 `strict=False`。
→ 直接违反方豆指令与 AGENTS 纪律 1, 且让"降级"重新长回来。

## 🔬 根因 3: 用例锁定的是"降级语义" (1 个)

`test_generate_case_runtime_sel_limitation`: fixture 是**非法 SystemVerilog**
(generate `case` 的 sel 必须是常量表达式, 用的是输入端口 `sel`)。旧用例断言
"0 边 0 tree" —— 那是"报错后继续跑 partial AST"的产物。

恒定严格下正确行为 = **明确拒绝**。用例改写为
`test_generate_case_runtime_sel_rejected`:

```python
with self.assertRaises(CompilationError):
    tracer.build_graph()
codes = [e.get("code") for e in tracer.get_elaboration_errors()]
self.assertIn("ConstEvalNonConstVariable", codes)   # 结构化诊断码
```

**这不是"为通过而改断言"**: 旧断言描述的是 bug 行为 (非法输入产出空图, 用户会误判
"这个设计没有驱动关系"), 新断言描述的是正确行为, 且比原来更强 (校验诊断码)。
类 docstring 与模块 docstring 中的 limitation 表已同步说明这次语义变更。

## 📊 实际结果

| 阶段 | 全量 canonical |
|---|---|
| iter_224 结束 | 28 failed / 3288 passed |
| 修 filelist (根因 1) | `test_pyslang_type_extraction.py` **87 passed** |
| 改用结构化诊断 (根因 2) | `test_fix_*` 四文件 **35 passed** |
| 改写用例 (根因 3) | `test_f2_generate_expression_trees.py` **5 passed** |
| **本轮全量门禁** | **16 failed / 3300 passed** ← 只剩方豆指示暂缓的可视化项 |

## 💡 关键发现 / 决策

1. **`strict=False` 的"假绿"有三层**: ① 不完备的测试语料 (缺文件); ② 以"坏项目"
   为输入的工具契约缺失; ③ 锁定降级行为的用例。移除 strict 时必须三层都处理,
   否则红/绿都不可信。
2. **"预期失败"要显式声明**: 诊断型命令的输入就是错的 —— 这不是 fallback, 是契约。
   关键区分: **是否把失败伪装成成功**。这里失败仍以结构化诊断 + 非零态可见。
3. **同类坑会重复出现**: 语料缺依赖 (darkriscv `spi_master` → NaplesPU
   `memory_bank_1r1w`)。下次移除降级开关时, 应先全量补全语料再撤开关。
4. ~~**覆盖缺口 (主动登记)**: `collect_elaboration_diagnostics` 的
   "CompilationError 但诊断为空 → raise" 分支没有测试, **实际不可达**。~~
   **⚠️ iter_226 更正: 我判断错了** —— `CompilationError` 有多条**不产生诊断**的路径
   (`compiler.py:167/191` 输入内容守卫 / `:319` filelist 一个源文件都没解析出来 /
   `:453` 解析失败)。实测 `fix report --filelist <全是不存在文件的 .f>` → rc=1 +
   `filelist ... 没有解析到任何源文件`, 已补回归测试
   `test_fix_report_unresolvable_filelist_fails_loudly` (iter_226)。
   教训: "不可达"是假设, 必须 `grep raise` 把路径走一遍再说。

## 📎 产物

- 代码: `src/cli/_common.py` (+ 结构化诊断入口) / `fix.py` / `fix_imports.py` / `fix_widths.py`
- 测试语料: `sim/tests/pyslang_type_fixtures/industrial_filelists/naplespu_logger.f` (补全依赖)
- 测试: `sim/tests/unit/test_f2_generate_expression_trees.py` (用例语义更新 + 断言增强)
