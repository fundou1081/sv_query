# Iteration 224: 彻底移除 strict — 核心层 `self._strict` 清零, 全仓 strict 概念归零

**Metadata**:
- **Iteration #**: 224
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_remove_strict.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (goal 轮 1)
- **Outcome**: ✅ 成功 (全量 **32 failed → 28 failed** 改善 4, 无新失败)

## 🎯 本次目标

方豆指令: **"彻底移除 strict"** / **"逐文件修改, 全改"** / **"继续做, 直到全部完成。"**

goal `goal-e8196ce3` 轮 1 的收尾动作: 清掉最后 **27 处 / 7 文件** 的 `strict`
(核心层 `self._strict` 语义分支 + 3 个类的形参/字段 + 残留实参),
按纪律**逐文件五层验证**, 全量门禁不恶化才提交。

## 📊 当前状态 / 预期结果

- 开工: `tools/scan_strict.py` = 27 处 / 7 文件 (形参 4 / 关键字实参 6 / 裸引用 4 / `self._strict` 3 …)
- 关键剩余: `src/trace/core/compiler.py` (`strict` 形参 + `self._strict`)、
  `src/trace/unified_tracer.py` (形参 + 字段 + 2 处实参)、
  `src/applications/bus/sv_extractor.py` (3 形参 + 2 实参 + 字段 + kwargs 字典)
- 预期: AST 清单归零 + 冒烟 rc=0 + 全量失败数 ≤ 32

## 🔬 实际结果

### 1. 核心层改写 (AST 精确, 每文件 `ast.parse` 后才写回)

| 文件 | 改动 |
|---|---|
| `src/trace/core/compiler.py` | 删 `strict: bool = True` 形参 + `self._strict = strict` + docstring 行 + **`if not self._strict:` 降级分支** (原 HEAD:468 `continuing in non-strict mode (partial AST)`, 本轮删) |
| `src/trace/unified_tracer.py` | 删形参 + docstring 2 行 + `self._strict = strict` + 2 处 `SVCompiler(..., strict=True)` / `CovergroupExtractor(..., strict=True)` |
| `src/trace/core/covergroup_extractor.py` | 删 `SVCompiler(..., strict=True)` |
| `src/trace/core/sva_extractor.py` | 删 `SVCompiler(..., strict=True)` |
| `src/applications/bus/sv_extractor.py` | 删 3 形参 + 2 处 `strict=True` 实参 + `self._strict` + `kwargs["strict"]` |
| `tools/benchmark/run_benchmark.py` | 删生成的 `-c` 片段里的 `strict={strict}` + argparse 的 `--strict` |
| `src/cli/commands/snapshot.py` | `graph_data["strict_mode"] = strict` → `= True` (**修 NameError, 见下**) |
| `src/cli/_common.py` | 删 docstring 的 `strict:` 项 + 错误提示里"Use --no-strict"改为"修根因" |

**扫描结果**: `python3 tools/scan_strict.py --summary` → **0 处 / 0 文件**
(形参 0 / 关键字实参 0 / 位置实参 0 / 裸引用 0 / `self._strict` 0)。

### 2. 冒烟 (4 条主链路, 全部 rc=0)

```
stats                                rc=0
trace fanin                          rc=0
visualize pipeline                   rc=0
coverage generate                    rc=0
```

`run_cli.py stats ... --no-strict` → typer 明确报 `No such option '--no-strict'`
(exit 2, 不是静默忽略); `tools/coverage_gen_demo.py ... --no-strict` →
新增的**显式拒绝**分支打印错误并 `exit(2)` (此前是静默 ignore)。

### 3. 全量门禁

| 状态 | 全量 canonical (`sim/tests/`, `-m "not opensource"`) |
|---|---|
| 基线 (HEAD `a4184a0`, iter_223) | **32 failed / 3283 passed** |
| 本轮 (功能改动后) | **28 failed / 3288 passed** |
| 本轮 (注释清理后复跑) | **28 failed / 3288 passed** (一致) |

失败构成 (**全部是基线已知项, 0 个新增**):

| 文件 | 数量 | 状态 |
|---|---|---|
| `cli/test_visualize_teach_nested_mux.py` | 16 | 按方豆指示暂缓 (fixture 有真实 elaboration 错误) |
| `unit/test_fix_report.py` | 4 | 严格模式暴露的 fixture 真错 |
| `unit/test_fix_imports.py` | 4 | 同上 |
| `unit/test_pyslang_type_extraction.py` | 3 | 同上 |
| `unit/test_f2_generate_expression_trees.py` | 1 | 同上 |

**改善来源 (32 → 28)**: `unit/test_snapshot_compare_flags.py` 的 **4 个失败被真正修好**
(该文件现 5 passed)。

## 💡 关键发现 / 关键技术 / 决策

### 1. 找到一个真 bug: `snapshot save` 的 `NameError` (iter_216 批次 2 的残留)

```python
# snapshot.py save() — 形参表里没有 strict, 函数体却引用它
graph_data["strict_mode"] = strict      # NameError: name 'strict' is not defined
```

**证据 (HEAD 工作树实测)**:

```
$ python3 run_cli.py snapshot save sim/tests/fixtures/golden_mini/inst_demo.sv --tag probe_head
Error: name 'strict' is not defined          # ← 被 `except Exception` 吞成一行提示
```

批次 2 删掉了 CLI 的 `--strict` 选项, 但函数体引用没同步 → 每次 `snapshot save`
都失败。过去 4 个测试红, 我此前误归因为"fixture 在严格模式下暴露真错",
**真实原因是这个 NameError** (broad `except Exception` 把它伪装成普通错误提示)。
修法: 该字段语义已恒为 True → `= True` (保留字段名, 兼容已存的 snapshot JSON)。

**教训**: `except Exception` + 只打印 `str(e)` = 错误被伪装; 排查失败必须看
真实异常类型, 不能只按"疑似原因"归类。

### 2. 扫描器也有盲点: 字典键形态 `{"strict": True}`

`scan_strict.py` 按 AST 找 `strict=...` 关键字实参, 但
`**{"strict": True}` / `kwargs["strict"]` 这类**字典键**形态看不见。
本轮靠 `grep '"strict"'` 兜底, 结论: `design.py:407` 的 `"strict": True`
是 **JSON 输出字段** (非传参, 保留恒 True 兼容下游), `sv_extractor.py` 的
`kwargs["strict"]` 是**真传参** (已删)。→ 扫描器需补"字符串键命中"分类。

### 3. 语义等价性判断: strict 只能"恒 True", 不能"恒 False"

`self._strict` 的两种语义 (raise vs partial AST) 中, 只有 raise 一侧可以留。
删分支而非删字段会留死代码, 删字段而不删分支会 `NameError` —— 因此
**必须同一次改动里删完 形参 + 字段 + 分支 + 全部实参** (这解释了 iter_217/218/220
三次回退)。

### 4. worktree 对照法的局限 (新发现, 影响后续排查方法)

`git worktree add` 做基线对照时, **依赖硬编码路径的测试会失效**:
`sim/tests/unit/test_snapshot_compare_flags.py` 里
`REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")` 写死 → 在 worktree 里跑
pytest 时, 子进程实际调用的是**主工作树**的 `run_cli.py`。
因此"worktree 里某测试通过"**不能**证明基线通过 (本轮就出现了这一假象)。
→ 结论: worktree 对照只对**进程内**测试可靠; 子进程型 CLI 测试必须在主树
用 `git stash` 或独立 checkout 复现。

### 5. 文档/注释也是 strict 的宿主

除了可执行代码, 还有 16 处注释/docstring 描述"non-strict 模式"的行为契约
(`_common.py` / `_viz_common.py` / `visualize.py` / `fix.py` / `protocol.py` /
`handshake.py` / `snapshot.py` / `errors.py` / `compiler.py` /
`uvm_testbench_extractor.py` / `unified_tracer.py` / `run_benchmark.py` /
`verify_native_parity.py` / `coverage_gen_demo.py`) 以及 1 处死代码
(`coverage_gen_demo.py` 的 `strict = False` + `if False:` 分支)。
**描述"已不存在的降级路径"的注释 = 误导下一个人**, 一并清理;
`sv_preprocessor.py` / `verify_native_parity.py` 中提到 pyslang 自身的
"strict compile mode" 属于外部概念, 保留。
另清掉 2 处 flag 改写残留的死包装: `coverage_gen_demo.py` 的 `if False: pass`
(已删) 与 `_common.py` 的 `if True:` (已回退缩进, 20 行)。

**已知遗留 (cosmetic, 未处理)**: iter_222 的 `remove_strict_in_file.py` 删实参时
留下了 46 处 `f(a, b, )` 形式的**尾随逗号** (19 文件) —— 语法合法、行为无影响,
但不该做盲正则清理 (`(x, )` 是 1-tuple, 正则替换会改变语义), 需按 AST 调用点判定。

## 📎 产物

- 代码: 18 文件 (`git diff --stat`: 56 insertions / 88 deletions)
- 工具: `tools/scan_strict.py` (只读清单) / `tools/remove_strict_in_file.py` (单文件改写)
- 文档: 本文件 + `tasks/L1_remove_strict.md` + `CURRENT_TODO.md` + `overview.md` + `docs/INDEX.md`
- 归档: `docs/archive/2026-09-09-nostrict-cleanup/` (3 个"专测 flag 行为"的测试文件 + README)

## ⏭️ 下一步

1. 修 **12 个非可视化失败** (fixture 真错: `fix_report` / `fix_imports` /
   `pyslang_type_extraction` / `f2_generate_expression_trees`)。
2. 16 个可视化失败待方豆解冻 (`test_visualize_teach_nested_mux.py`)。
3. 扫描器补字典键形态分类 (`**{"strict": x}` / `d["strict"]`)。
