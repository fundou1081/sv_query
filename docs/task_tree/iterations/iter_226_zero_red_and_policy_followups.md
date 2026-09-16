# Iteration 226: 全量归零 (16 viz 红清零) + 尾随逗号清理失败回退 + 回归阈值收紧 + 冻结 skip 分诊

**Metadata**:
- **Iteration #**: 226
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_zero_red_and_policy_followups.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 成功 (全量 **16 failed → 0 failed / 3316 passed**), 含 1 次失败尝试 (已回退, 如实记录)

## 🎯 本次目标

方豆指令: **"去做吧"** —— 执行上一轮列出的"需要你决定的事":
1. 解冻并修掉最后 16 个可视化红 (`test_visualize_teach_nested_mux.py`)
2. 46 处尾随逗号按 AST 调用点清理
3. `check_regression.py` 阈值收紧 (50%/0.7 → 30%/1.0)
4. 评估 13 个冻结可视化断言 skip 是否转正
5. 诊断 `collect_elaboration_diagnostics` 防御分支能否构造测试

## 🔬 1. 16 个可视化红: 一个词的根因

16 个失败**全部**是同一句报错:

```
[ERROR] nested_mux_demo.sv:271:22: [AssignToNet]
        error: cannot assign to a net within a procedural context
```

定位: `sim/tests/fixtures/golden_mini/nested_mux_demo.sv:44` 声明

```systemverilog
output     [7:0] y_array_index_mux     // ← net (wire)
```

但 Pattern 16 在 `always @(posedge clk)` 里用 `<=` 给它赋值 (第 268~275 行) ——
**net 不能在过程块里赋值**。修法 (根因层, 一个词):

```systemverilog
output reg [7:0] y_array_index_mux
```

**结果**: `stats` 报错数 4 → **0**; `test_visualize_teach_nested_mux.py` **16 passed**。

> 与 iter_213 (`sim/test_comprehensive.sv` 10 处 `output logic`) 是**同一个坑**:
> 过程赋值的信号必须声明为变量。过去 `strict=False` 让 AssignToNet 错误被吞,
> 16 个断言在"残缺图"上照跑 —— 这是"假绿"的典型样本。

## ❌ 2. 尾随逗号清理: 尝试失败, 已回退 (如实记录)

**目标**: iter_222 的改写工具留下 46 处 `f(a, b, )` 尾随逗号 (19 文件)。

**做法**: 写 AST 脚本 —— 遍历所有 `ast.Call`, 用 `end_col_offset` 回看 `)` 前面
是否有逗号, 有则删。第一版直接崩 (`IndexError`): **AST 的 `col_offset` 是 UTF-8
字节偏移, 而本项目源码满是中文注释** → 字节偏移不能直接当字符下标用。
第二版加了字节→字符转换, "成功"改了 1 个文件。

**结果 = 事故**: `git diff` 显示它删的是 **1-tuple 的逗号**:

```diff
-                PipelineStep("compile", _step_compile, outputs=("root",)),
+                PipelineStep("compile", _step_compile, outputs=("root")),
```

`("root",)` 是 tuple, `("root")` 是 **str** —— 语义从"一个元素的元组"变成字符串,
下游迭代它会得到 `'r','o','o','t'`。**这是我本人在 iter_224 文档里刚写下的警告**
("盲正则会把 `(x, )` 这种 1-tuple 改坏"), 然后自己踩了同一个坑 (因为 `, )` 的
外壳是 Call, 内层却是 Tuple)。

**处置**: `git checkout --` **立即回退**, 复核 `outputs=("root",)` 已恢复 + `stats` rc=0
+ 全仓 `ast.parse` 无语法错。

> **⚠️ iter_227 后续**: 这一项**当天就重做成功了** (46 → 0 处)。失败根因不是"做不到",
> 而是**缺一道机械闸**: 删尾随逗号不应改变 AST, 用 `ast.dump(before) != ast.dump(after)`
> 做硬拒绝即可安全清理 (详见 iter_227)。下面的"保持原样"结论**已被 iter_227 取代**,
> 保留原文是为了记录当时的判断与理由。

**结论 (当时的决策)**: **尾随逗号保持原样, 不做清理**。理由:
- 它**语法合法、语义无影响** (纯风格);
- 正确的清理必须按 AST 判定"这个逗号属于 Call 的实参列表" (而非内层 tuple/生成器),
  收益 (美化) 远小于风险 (改坏语义);
- 已用 grep 精确记录数量 (46 处 / 19 文件), 将来若要清, 有人可查。

## 📊 3. 回归阈值收紧 (表里如一的说明)

`tools/benchmark/check_regression.py`:

| 维度 | 旧 | 新 | 生效方式 |
|---|---|---|---|
| L2 nodes / edges / IM | 30% | 30% | 硬失败 (不变) |
| L1 instances | 50% | **30%** | ⚠️ **仅警告, 不改退出码** |
| L4 edges | 50% | **30%** | ⚠️ **仅警告, 不改退出码** |
| flakiness `deterministic_ratio_im` | ≥0.7 | **≥1.0** | 硬失败 |

**关键如实说明**: L1/L4 越界本工具**历来只警告**, 所以本次真正改变 CI 判定的是
**flakiness 0.7 → 1.0**; L1/L4 的 50→30 只让警告更早出现。
依据: flakiness 真因 (`SourceManager` 生命周期) 已在 iter_185 修复, 实测 3 次
stdev=0.0 / ratio=1.0 (4 个 baseline 全是 1.0)。
**待方豆单独拍板**: 是否把 L1/L4 也改成硬失败 (= 真正的"收紧")。

同步测试 (`sim/tests/integration/test_benchmark_regression.py`, opensource 标记):
- flakiness 用例 docstring: threshold 0.7 → 1.0
- 原 `test_l1_40_pct_drop_warns_only` **名不副实** (注释写着"跌 40%", 实际只是 baseline
  自比, 因为 picorv32 的 L1=0) → 拆成 3 个诚实用例:
  - `test_l1_35_pct_drop_warns_with_tightened_threshold` (verilog_axi L1=6 → 派生 65%):
    断言出现 `⚠️  L1_instances: dropped` + `max_drop=30.0%` + rc=0 (锁定"新阈值生效"
    且"仍是警告级")
  - `test_l4_35_pct_drop_warns_with_tightened_threshold` (L4=146 → 65%)
  - `test_l1_self_compare_passes` (保留原意)
- 结果: **14 passed**

## 🔍 4. 13 个冻结可视化 skip: 分诊结果 (1 个成功转正)

文件 `sim/tests/usage/test_ventus_all_viz_validation.py` (opensource 标记, 不在 canonical 门禁内)。

**转正 1 个** (`/tmp/sched_d1.dot`): 该 artifact **从未被生成** —— 断言读
`/tmp/sched_d1.dot`, 而生成器 `_ensure_sched_dots()` 只跑 `visualize pipeline` /
`trace` / `visualize chain`。真实来源是 `arch show --format dot --output`。
补上生成调用后实测: 7 个子实例节点 / 7 个名字**全部命中**, 断言从 skip 变 **pass**:

```
补前: 15 passed, 13 skipped
补后: 16 passed, 12 skipped
```

**顺带修**: `/tmp/sched_pipeline_nocontrol.dot` 的生成写的是 `.svg` 后缀, 而断言读
`.dot` → skip 理由显示"artifact 缺失"(**误导**, 真因是 SVG/DOT 语义不匹配)。
路径对齐后理由变准确。

**剩余 12 个 = 仍暂缓 (方豆决策 ③"PNG/SVG 断言现阶段不处理")**:

| 数量 | 理由 |
|---|---|
| 10 | `visualize pipeline/timing` 的 `--svg` 输出 SVG 内容 (V100 起 `--dot` 是 `--svg` 别名), 断言基于 V100 之前的 DOT 语义 |
| 2 | PNG artifact 需要 graphviz, 且 `visualize pipeline` 不支持 `--png` (只有 `chain` 支持) |

**结论**: 这 12 个要转正 = "按 SVG 语义重写断言", 属于你需要单独批准的可视化工作,
本轮只做分诊 + 让 skip 理由真实。

## ✅ 5. 防御分支: 我上一轮的判断是**错的**, 已补测试

iter_225 我写"`collect_elaboration_diagnostics` 的 'CompilationError 但诊断为空 → raise'
分支实际不可达"。**本轮证伪并修正** —— `CompilationError` 有多条**不产生诊断**的路径:

- `compiler.py:167/191` 输入内容守卫 (把 filelist 当源码传 / 根节点是表达式)
- `compiler.py:319` **filelist 一个源文件都没解析出来**
- `compiler.py:453` 解析失败

实测构造:

```
$ printf '/tmp/probe_empty/does_not_exist.sv\n' > /tmp/probe_empty/empty.f
$ python3 run_cli.py fix report --filelist /tmp/probe_empty/empty.f
sv_query: error: filelist ... 没有解析到任何源文件 (1 个条目缺失/不可解析) — 请检查路径与基准目录
rc=1
```

**新增回归测试** `test_fix_report_unresolvable_filelist_fails_loudly`:
断言 rc≠0 + **不得**出现 "Project is clean" + 根因文字可见。
`test_fix_report.py`: 7 → **8 passed**。

> 教训: "不可达"是**假设**, 不是结论 —— 必须去 `grep raise` 把路径走一遍再说。

## 📊 全量门禁

| 阶段 | 结果 |
|---|---|
| iter_225 结束 | 16 failed / 3300 passed |
| 修 fixture (`output reg`) | `test_visualize_teach_nested_mux.py` **16 passed** |
| **本轮 canonical (`-m "not opensource"`)** | **3316 passed / 0 failed** (8 skipped / 164 deselected) |
| opensource 定向 | ventus usage **16 passed / 12 skipped**; benchmark regression **14 passed** |

## 💡 关键发现 / 决策

1. **一个词的 fixture 错误 = 16 个红**: 与 iter_213 同类 (`output` 缺 `reg/logic`)。
   `strict=False` 时代这类错误全部被吞, 现在它们无处可藏 —— 这正是移除 strict 的意义。
2. **AST 的 `col_offset` 是字节偏移**: 中文注释项目里直接当字符下标会崩 (IndexError)
   或错位; 必须 `len(line.encode()[:byte_col].decode('utf-8', errors='ignore'))` 转换。
   iter_224 的 `remove_strict_in_file.py` 用的是**区间替换**而非列偏移, 所以没踩到。
3. **自己写下的警告也会被自己踩**: 1-tuple 的坑在文档里写过, 脚本仍然踩了 →
   教训是"文档警告 ≠ 机械防护", 要么不做, 要么写检查器 (类似
   `check_except_pass.py` 的做法: 声明必须配机械保障)。
4. **阈值收紧要表里如一**: L1/L4 越界只警告是历史语义, 收紧数字不等于收紧判定 ——
   不写清楚就会让下一个读文档的人以为 CI 变严了。

## 📎 产物

- 语料: `sim/tests/fixtures/golden_mini/nested_mux_demo.sv` (`output reg`)
- 工具: `tools/benchmark/check_regression.py` (阈值 + 说明)
- 测试: `sim/tests/integration/test_benchmark_regression.py` (14 passed) /
  `sim/tests/usage/test_ventus_all_viz_validation.py` (16 passed / 12 skipped) /
  `sim/tests/unit/test_fix_report.py` (8 passed, 新增 re-raise 分支用例)
- 已回退 (未提交): 尾随逗号 AST 清理 (1-tuple 语义事故, 见上)
