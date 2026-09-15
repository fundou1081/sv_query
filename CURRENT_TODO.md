# CURRENT_TODO — 当前正在做的事

> **唯一入口**: 本文件是"此刻在做什么"的**唯一稳定追踪点**。
> **位置固定**: 根目录 `CURRENT_TODO.md`, 路径永不变更。
> **更新时机**: 每次开始任务 / 完成 sub-task / 被打断切换任务时, 立即更新。
> **最后更新**: 2026-09-06 GMT+8 (iter_167: covergroup 对抗轮完成 — 2 真 bug 修 + 边界登记)

---

## 📍 分工 (避免和其他文件重复)

| 文件 | 职责 | 时间尺度 |
|---|---|---|
| **CURRENT_TODO.md** (本文件) | **此刻**在做的 1 个任务 + 它的 sub-task 勾选 | 小时 ~ 天 |
| `docs/ARCHITECTURE_TODOLIST.md` | 架构改造 7 项的长期追踪 (ROI / 工作量 / 状态变更日志) | 周 ~ 月 |
| `docs/TODO.md` | 版本级功能待办 (V6.8 / V6.9 / V7.0 ...) | 月 ~ 季 |
| `docs/task_tree/` | 任务迭代记录 (每次迭代一个文件, 详见 AGENTS.md) | 每次迭代 |

**规则**: 本文件**只写当前**。任务做完 → 归档到 `docs/task_tree/` + 更新对应长期 todolist → 从本文件移走。

---

## 🔥 当前任务

**当前任务 (方豆方向)**: **C 路线 + benchmark 稳定性专项 ✅ 完成** (iter_179~196; 下一步主线: 文本结构化输出审计)。

**⚠️ iter_185 (真根因, 推翻了 iter_181~184 的归因)**: pr5 wrapper 的
`test_l1_instance_chain` 失败 (instance_count=0) → 按纪律查根因, 证伪
"语料含非 UTF-8 identifier" (axi/common_cells **0 个**非 UTF-8 文件),
真因 = **`SVCompiler._do_compile()` 把 `pyslang.SourceManager` 存成局部变量**,
parse 循环结束后被 GC → 源文件 buffer 释放 → 符号名/token 是指向释放内存的
`string_view` → 乱码名 / getter 抛 `UnicodeDecodeError` / elaboration 不完整 /
**指标跨次漂移** (内存复用模式决定症状)。最小复现: 私有 manager 丢弃引用 →
top 名 `UnicodeDecodeError`; 保留引用 → 正常。
**修复**: compiler 持有 `self._source_manager` (+ `self._param_overrides`
同类加固; slang 侧 `topModules`/`paramOverrides` 都是 `string_view` 容器)。
**效果**: 可遍历符号 10,957→23,567 / 乱码名 3,349→**0** / nodes 2,275→**4,946
且 3/3 完全一致** / clk fanout →**445** / flakiness `--runs 3` **stdev=0.0** /
pr5 套件 1 failed → **13 passed + 1 skipped**。iter_184 基于错诊断放宽的断言
已收紧 (nodes≥4,000 / IM≥400 / 深度≥12 / clk≥300)。
unit+regression **2113 passed + 35 subtests** / 全量 canonical
`sim/tests/ -m "not opensource"` **3237 passed / 0 failed** (8 skipped / 164 deselected)。
[iter_185](docs/task_tree/iterations/iter_185_slang_sourcemanager_lifetime.md)

**iter_210 (清理测试 --no-strict 第一批 — 方豆: 不可接受, 必须更改)**: 实测 `sim/tests` **202 处 / 41 文件**; 本轮机械清理 **25 文件 111 处** (逐文件 `ast.parse` 校验后才写回, 12 个复杂文件安全跳过) → 撤后 unit+cli 暴露 **16 failed 全集中在一个文件** (`test_visualize_teach_nested_mux.py`, 过去靠 flag 容忍 fixture 的真实 elaboration 错误) → **回退该文件**并登记待修 fixture; 其余 24 文件撤后全绿 (证明 flag 本来多余); 全量 canonical **3337 passed / 0 failed**。剩余 91 处/22 文件 (含 3 个"专测 flag 行为"的文件, 建议归档)。
[iter_210](docs/task_tree/iterations/iter_210_no_strict_removal_batch1.md)

**iter_209 (R4-1 落地 — 方豆 好，去做吧)**: **推翻上轮结论** —— 守卫当时就生效, "只看到路径"是我调试打印 `l[:100]` 的假象 (路径 ~100 字符); `handle_compilation_error` 也没吞消息。真正问题: 提示自相矛盾 → 按错误类型分支 (输入类型错误不再建议 --no-strict); 判据含 iter_208 两条教训; 3 条回归测试, 合法 .v/.sv 语料不误判。**四轮对抗的发现 (F1~F6 / R4-1 / R4-3 / R4-4) 至此全部闭环**。
[iter_209](docs/task_tree/iterations/iter_209_r4_1_landed.md)

**iter_208 (R4-1 尝试与回退 — 方豆 可以，继续做吧)**: R4-1 原场景已被 iter_207 的 R4-3 顺带修好; 剩余"非 .f filelist 经 -f 传入"仍误导。守卫扩展尝试**未生效已回退**, 留三条线索: ① 判据不能只看首行 (预处理器注入 `timescale) ② 裸路径判据要收紧 (endswith(.v) 误判行尾注释) ③ **守卫消息被 `handle_compilation_error` 格式化吞掉** → 修 R4-1 必须先修该格式函数 (或把检测放到 CLI 层)。
[iter_208](docs/task_tree/iterations/iter_208_r4_1_attempt.md)

**iter_207 (R4-3 落地: filelist +incdir+ — 方豆 按这个来做)**: 新增 `_read_filelist_full()` 交出 `spec.include_dirs` + `_build_tracer` 合并 incdir; 实测 `graph/stats --filelist` 从 rc=1(Undeclared 级联) → **rc=0**, trace/简单 include 无回归; 追加 2 条回归测试。顺序验证: **先修 R4-4 再落地 R4-3** 是对的 (iter_205 卡在既有红上分不清新旧)。剩余: R4-1。
[iter_207](docs/task_tree/iterations/iter_207_r4_3_landed.md)

**iter_206 (R4-4 修复: 输入路径显示形态 — 方豆 好，push完再继续)**: 更正上轮判断 —— 全量 canonical 实测**同样 9 failed**, 所以不是测试隔离而是 HEAD 真实既有失败 (`--file` 显示 `/var/...` 而 `--filelist` 显示 `/private/var/...`); 通用修复: 新增 `cli._common.display_path()` 并收敛 **11 处**重复显示逻辑 (risk/cdc/sva/timing/verify/controlflow), 断言未动; 该文件 **9 failed → 15 passed**。下一步: 落地 R4-3 (障碍已除) → R4-1。
[iter_206](docs/task_tree/iterations/iter_206_r4_4_display_path.md)

**iter_205 (R4-3 修复: filelist +incdir+ 被丢弃 — 方豆 先修吧)**: 修 R4-2 过程里真因转向 — 纯 pyslang 0 错误、我们的编译器(原文/预处理)都通过, 但 `graph/stats --filelist` 失败而 `trace --filelist` 正常 -> `_build_tracer` 的 filelist 路径只取 sources, 丢弃了 `+incdir+` (iter_193 解析器已给出 spec.include_dirs) -> 头文件宏无法展开 -> 级联报错。修复: `_read_filelist_full()` + `_build_tracer` 合并 incdir; graph/stats rc=1->0; 但全量门禁出现 9 个 parity 失败 -> 回退后**仍失败** = **R4-4 测试隔离缺陷** (parity 测试单独跑 9 failed, 全量套件里绿) -> **修复已回退**; R4-2 结论更正 (含参宏由 pyslang 展开, 不构成 bug); 下一步: 先修 R4-4 再落地 R4-3; R4-1 仍待修。
[iter_205](docs/task_tree/iterations/iter_205_r4_3_filelist_incdir.md)

**iter_204 (对抗第四轮: 跨文件 include/宏 — 方豆 "继续")**: 通过项: include+incdir / 跨文件 define / 嵌套 filelist / 缺失条目 / 自包含 include 循环; **R4-2 真 bug: 宏 token paste (`nm``_q`) 不生效** → 3 行最小复现 + 对照实验 (同链路不含 `` → rc=0) 定位到**宏展开层** (非 include); **R4-1 UX 缺口: `-f <filelist>` 误用不再触发 iter_189 守卫的清晰提示** (判据只覆盖"表达式根") → 退化成下游错误 + "Use --no-strict" 误导。修复方案已列待拍板。
[iter_204](docs/task_tree/iterations/iter_204_adversarial_include_macro.md)

**iter_203 (对抗第三轮: 分析层 + F6 — 方豆 "继续")**: 打分析层 10 用例 (generate 双 genvar / 参数化 class extends + interface / 宏拼接名 / 重复 module / 多语言料) → **分析层健壮**; 但启发式标记追出 **F6: `trace --format json` 打印被 JSON 转义的字符串** (不是对象), 而 `--json` 正确 → 别名未收敛; 修复: 三处 dispatch 补 json 分支 (与 --json 同实现) + 3 条回归测试 (断言**类型**为 dict, 不只"能否解析")。
[iter_203](docs/task_tree/iterations/iter_203_adversarial_analysis_layer.md)

**iter_202 (对抗第二轮: --quiet 契约 — 方豆 "继续")**: 换面打 quiet × JSON × stdout 纯净性 + `-j` + 退出码一致性 → 通过项若干, **发现 F5: `--quiet` 实测残留 6 行 stderr** (Phase 3/4 + pipeline 摘要, 都绕过日志系统直接 print) 违背"抑制所有 stderr"契约; 修复: 新增 `compiler.is_quiet()` 供输出点自门控 + 6 行加门控 → stderr 从 225 → **0 字节** (默认模式诊断不变); 追加 3 条回归测试 (quiet 必须空 / quiet 不吞错误 / quiet+-j 纯 JSON)。
[iter_202](docs/task_tree/iterations/iter_202_adversarial_quiet_contract.md)

**iter_201 (JSON 契约 F1~F4 修复 — 方豆 "先把这几个修了")**: F1 错误路径也输出结构化信封 `{ok:false, command, error:{type,message}}` (**两层挂载**: 命令内 except + CLI 顶层, 因为文件/编码错误会逃到顶层); F2/F3 `--json` 与 `--svg/--timing` 等组合时显式告警且不产出文件; F4 `--max-paths` 负值报错 (0 仍合法); 新增 8 条对抗回归测试。
[iter_201](docs/task_tree/iterations/iter_201_json_contract_fixes.md)

**iter_200 (对抗性测试: JSON 契约 — 方豆 "来做一些对抗性测试，找到现有功能的问题")**: 14 组对抗组合 + 3 项静默行为验证 → **4 个问题**: F1 `--json` 错误路径 stdout 空 (成功信封有 `ok` 却无错误信封, 4 用例命中); F2 `--json --svg X` 静默丢弃 SVG; F3 `--json --timing` 静默忽略 timing; F4 `--max-paths -1` 静默当 0。根因: 成功契约≠完整契约 + 模式互斥无校验 + 参数校验缺失。**修复方案已列待拍板** (错误信封 / 互斥 flag 告警 / 负值报错 / 矩阵固化为回归测试)。
[iter_200](docs/task_tree/iterations/iter_200_adversarial_json_contract.md)

**iter_199 (timing analyze --json 补测 — 方豆 "按你的推荐，补测吧")**: 用 iter_198 同一模板补上 8 条字段级验收测试 (`sim/tests/cli/test_timing_analyze_json.py`): 纯 stdout / 信封与 pipeline 一致 / result 与 critical_paths 字段固定 / reg_count<=total_nodes / 每 path depth,score>=1 且 registers⊆full_path / --max-paths 生效 / reg_count==0 时 critical_paths 为空; **不把具体数值写死** (吸取 iter_195 `rankdir=LR` 教训)。两个命令信封现已统一。
[iter_199](docs/task_tree/iterations/iter_199_timing_json_tests.md)

**iter_198 (pipeline --json 落地 — 方豆 "嗯，去做吧")**: `sv_query visualize pipeline --json` 已实现 (导出 `PipelineInfo`, 信封与 `timing analyze --json` 一致, 诊断走 stderr 保证 stdout 纯 JSON), **不渲染可视化** (按决策冻结); 新增 7 条**字段级验收测试** (`sim/tests/cli/test_visualize_pipeline_json.py`): stdout 纯 JSON / 信封一致 / result 与 stages 字段固定 / 寄存器三分类互斥 / stage_count 与 latency 一致性 / 深链 latency 不变量。
[iter_198](docs/task_tree/iterations/iter_198_pipeline_json_output.md)

**iter_197 (文本结构化输出审计 — 方豆 "继续")**: 按新验收标准审计 —— `sv_query timing analyze` **已有 `--json`** (信封 `{ok, command, result}`), 而 `visualize pipeline` **完全没有结构化输出** (只有 stderr 的人类可读行) → 主要缺口。实现路径已定位且不需新分析逻辑: `pipeline_viz.detect_pipeline()` 已返回 `PipelineInfo` (stages/total_latency/pipeline_regs/control_regs/state_regs) → 加 `--json` = asdict + 对齐 timing 信封 (诊断走 stderr)。**下一步就是落地它**。
[iter_197](docs/task_tree/iterations/iter_197_text_output_audit.md)

**iter_196 (可视化 flag 统一 — 方豆决策执行)**: `--dot` 已在 **src + sim/tests 全仓清零**; 7 个 SVG 子命令收敛为 `--svg`, 5 个真 DOT 命令改 `--emit-dot` (换名保留能力); 测试按命令边界映射 57 处; **顺带发现真缺陷**: chain 的 `--svg` 被声明两次 (内部渲染器 vs 外部 graphviz), 旧代码把 `--svg` 绑到后者, 测试靠 deprecated `--dot` 别名才走通 → graphviz 那条改名 `--svg-graphviz`; 全量 3302 passed / 0 failed。
[iter_196](docs/task_tree/iterations/iter_196_viz_flag_unification.md)

**方豆决策 (2026-09-08)**: ① pipeline/timing 的验收标准改为**文本结构化输出**, 可视化暂时冻结; ② 可视化 flag 统一为 `--svg`、**不再支持 `--dot`**; ③ PNG/SVG 断言现阶段不处理; ④ 文本输出稳定后再看可视化。改名影响面实测: CLI 7 处 + 内部调用 2 处 + 测试引用 **57 处/≥12 文件** (试跑 52 failed) → 必须一次做完"改名 + 测试同步 + 全量验证", 且同批清理受影响文件里被禁的 `--no-strict`。**已在本地试做后回退** (不提交半成品/半红套件), 等方豆确认真 DOT 命令 (`visualize module`/`teach`/`datapath` + `timing`) 的处置方式后执行。
[决策记录](docs/architecture/ventus_viz_assertion_migration.md)

**iter_195 (viz 断言迁移决策就绪 — 方豆 "继续")**: 对 iter_188 的 13 个 skip 逐条实测"原断言意图 vs 当前 SVG 能否验证", 产出可拍板的表 (`docs/architecture/ventus_viz_assertion_migration.md`): 可直接迁移 3~4 条 / 需先定产品语义 7~8 条 / 需先补 CLI 能力 2 条; **额外发现原 `rankdir=LR` 断言早已不成立** (实测宽高比 0.28 竖版); 根因 = `--dot` 在同一 CLI 内三种语义。同时在 iter_189 记录里追加"可直接提给上游的 issue 文本"。**未改任何断言** (迁移属产品语义)。
[iter_195](docs/task_tree/iterations/iter_195_viz_assertion_migration_decision.md)

**iter_194 (空 filelist 报错 + reclaim opt-in — 方豆 "继续")**: ① 空 filelist 过去只告警 → 输出**空图且 rc=0** (静默失败); iter_193 统一解析规则后两侧消费方均改抛 `CompilationError` → 实测 rc=0 空图 → **rc=1 + 一行错误**; ② `run_benchmark.py::reclaim_memory()` (4GB 技巧) 默认关闭、保留 `--reclaim` (iter_185 后不再必要, 每次省 ~3s)。
[iter_194](docs/task_tree/iterations/iter_194_empty_filelist_and_reclaim.md)

**iter_193 (合并 filelist 加载器 — 方豆 "先合并 filelist")**: 抽出唯一解析实现 `trace/core/filelist.py::parse_filelist()` (结构化 `FilelistSpec`), tracer 与 CLI 两个消费方变薄封装; 实测差异为**两处** (相对路径基准 + 嵌套 `-f` 基准) → 统一为 "filelist 目录 → base_dirs" 候选; 新增 parity 测试 5 个 (两侧文件集必须一致 = 不变量); ADR: `docs/architecture/filelist_loader_unification.md`。
[iter_193](docs/task_tree/iterations/iter_193_filelist_loader_merge.md)

**iter_192 (filelist 双基准解析 — 方豆 "继续")**: 兑现 iter_190 未决项 —— 实测两套 filelist 加载器相对路径规则不同 (tracer 侧按 filelist 目录 / CLI 侧按 base_dir) → 同一 filelist 两侧结果不一致, 且 CLI 侧对**实际存在**的文件误报"条目不存在"(告警变噪声); 仓库内两种约定**并存** (industrial_filelists 用仓库根相对) → 改为**多候选解析** (filelist 目录优先 → base_dir, 都不中才告警并列出候选基准): filelist 目录相对 CLI 0→1, 仓库根相对 0→1; 新增 4 测试把两种约定 + 缺失情形钉死 (两套加载器统一时的安全网)。
[iter_192](docs/task_tree/iterations/iter_192_filelist_resolution_bases.md)

**iter_191 (CLI 错误格式化 — 方豆 "继续")**: iter_189 解决"崩进程"、iter_190 解决"静默"之后, 本轮解决"用户读不懂" —— 非法输入过去甩原始 traceback。新增 `src/cli/main.py::run()` 统一入口 (只格式化 OSError 家族 + UnicodeDecodeError + CompilationError; 其他异常照旧抛**不掩盖真 bug**; `SVQ_DEBUG=1` 恢复完整栈), `run_cli.py` 与 console script 共用。结果: 二进制/UTF-16/目录/不存在/filelist 当源码 → 全部 `sv_query: error: <一行原因>` + rc=1, traceback 消失; 新增 40 个回归测试(`test_cli_hostile_input.py`, 含"合法极端输入必须成功"的反向断言)。
[iter_191](docs/task_tree/iterations/iter_191_cli_error_formatting.md)

**iter_190 (`except: pass` 清算 — 方豆 "继续")**: 查 CLI 敌意输入时在 filelist 加载器发现被禁写法 → 全仓量化: **AGENTS v1.4 声称"计数=0", 实测 52 处** (25 处 `except Exception: pass`)。全部改为可见日志 (核心路径 debug / CLI warning, 保留理由注释, 9 文件补 logger) → **AST 扫描归零**; 新增 `tools/check_except_pass.py` (**写进 AGENTS 提交前清单**) + `test_discipline_except_pass.py` (含检查器自检); 连带修 filelist **静默缺陷**: 缺失条目 / 读失败 / 嵌套 filelist 缺失 / 语法错误 `-f` 行 → 全部可见告警 (过去会得到"少文件的图"却以为完整)。
[iter_190](docs/task_tree/iterations/iter_190_except_pass_cleanup.md)

**iter_189 (pyslang addSyntaxTree SIGTRAP — 方豆 "继续")**: 把 iter_188 发现的 `visualize module` 崩溃查到底 —— **纯 pyslang 5 行最小复现**: `Compilation.addSyntaxTree()` 在语法树根节点是**表达式**时原生 SIGTRAP (filelist 内容被 slang script 模式解析成 `DivideExpression`); 逐步二分证明只有 `addSyntaxTree` 崩 (faulthandler 对 SIGTRAP 无效)。合法根类型实测: `CompilationUnit`(空/注释/define/多成员) / `ModuleDeclaration`(单 module) / `ClassDeclaration`。修复: `SVCompiler._reject_non_design_unit` 只拒"表达式根"(不误伤合法输入) → `visualize module -f <filelist>` 从 **rc=-5 无输出** 变为 **rc=1 + 可行动错误提示**; 回归锁 11 测试 (守卫失效时 pytest 自己 exit=133)。
[iter_189](docs/task_tree/iterations/iter_189_addsyntaxtree_sigtrap_guard.md)

**iter_188 (Ventus viz 套件分诊 — 方豆 "继续")**: opensource 集里唯一常红文件 `test_ventus_all_viz_validation.py` 14 failed → **0 failed** (15 passed / 13 明确 skip)。四类根因: ① `--dot` 自 V100 起是 `--svg` 别名 (输出 SVG), 断言仍按旧 DOT 语义 (实测 SVG 无 rankdir/digraph/cluster) → `_read_dot()` 内容判定 + 明确 skip 原因; ② trace 子命令无 `--dot` (正确: `--format dot --output`); ③ `_ensure_sched_dots()` 静默吞 rc **且全程用被禁的 `--no-strict`** (10 处 → 0) → 记录失败原因并上抛到 skip; ④ **新发现真 bug: `visualize module` 原生崩溃 SIGTRAP** (rc=-5 / 无输出 / 任意 target) — 已用 `git worktree` 在 iter_183 (f639ed6) 复现, **非 iter_184~187 引入**, 待立项 native 调试。opensource 子集 111 passed / 14 skipped / 0 failed。
[iter_188](docs/task_tree/iterations/iter_188_ventus_viz_suite_triage.md)

**iter_187 (baseline 漂移清算 — 方豆 "继续")**: 回审"为掩盖 flaky 而加的补偿措施" → 挖出结构性缺陷: 3 个 baseline 全部与当前行为不符 **且不可复现** (都采集于 iter_145 top_modules 之前): picorv32 708→**438** / IM 2→**0**; verilog-axi 8,221→**715** / IM 51→**6**; `pulp_axi_xbar` 的 target 已不存在。旧断言 `600<=nodes<=800` 只查文件自身 → 过时 baseline 一路绿灯 → `check_regression` 对用户报**假 regression**。修复: 新增 `tools/benchmark/inputs.py` (唯一输入构建点) + `regen_baselines.py` (重生成 / `--check` rc=2 漂移检测), 重生成 3 个 baseline (flakiness stdev 全 **0.0**), 并加"活体 == baseline"守卫测试; 连带修 `test_benchmark_regression` 里硬编码的旧数值 (改按比例派生)。
[iter_187](docs/task_tree/iterations/iter_187_baseline_drift_cleanup.md)

**iter_186 (同族隐患排查 — 方豆 "继续")**: 按 iter_185 建议做 7 类模式全仓扫描 → 又修 2 处真实/潜在隐患: ① `sim/tests/test_d1_generate_flatten_signal_set.py::_compile_case27` 把 SourceManager 丢在函数帧里却返回符号 → 隔离实测 `top.name` **3/3 UnicodeDecodeError** (套件"8 passed"只是内存未被覆写的运气; 即 iter_158 记的 "symbol 对象 str 垃圾" 来源) → 模块级 `_LIVE_SOURCE_MANAGERS` 登记 manager ② `uvm_testbench_extractor._class_defs` 存 syntax node 逃出帧 → 显式持有 manager+compilation 至遍历结束, 并更正 "SVCompiler 污染 token.name" 错误注释 ③ `PYSLLANG_BINDINGS_PATH` 死路径 (目录不存在却无条件 插 sys.path) → 改为存在性判定。**新增 4 个回归锁并做红/绿双向验证** (去掉修复全红: d1 版实测 top.name 变成一片空格)。自伤如实记录: 红/绿验证时用 `git checkout --` 抹掉了该文件未提交的改动, 已重做并改用 /tmp 自备份。
[iter_186](docs/task_tree/iterations/iter_186_ownership_hazard_sweep.md)

**iter_184 (getter 残余点 + 部分 elaboration 记录 — 归因已被 iter_185 更正)**:
`graph_builder.py:822` / `bit_select_handler.py:330` 两处 getter 守护; 记的
"非 UTF-8 → 部分 elaboration" 结论 **❌ 错误**, 保留为历史。
[iter_184](docs/task_tree/iterations/iter_184_getter_sites_and_partial_elab.md)

**iter_181 (benchmark 稳定性)**: 修 2 个确定性缺陷 — flakiness 子进程缺
`top_modules` (与主测量对齐) / `native_adapter` 两处 `top.name` 未守护;
**当时定位的"根因族" (wrapper 语料含非 UTF-8 identifier → getter 抛
UnicodeDecodeError) 已被 iter_185 证伪** — 真因是 SourceManager 生命周期。
保留的教训: getter 级崩溃要用 `safe_attr` (`safe_str` 救不了, 实参求值即炸)。
[iter_181](docs/task_tree/iterations/iter_181_bench_stability.md)
**iter_182 (backlog 兑现)**: `tools/scan_pyslang_attrs.py` 扫描全仓 **126 处**
未保护属性读取 (getter 级崩溃族); **热路径收敛 70 点** (8 文件, 按属性给语义
安全默认值: `.name`→""、`.type`→None、`.body`→[]); 剩余 56 点 (可视化/CLI 等
非抽取路径) 登记。自伤如实记录: 导入深度写错 → 7 模块 ImportError, 已修。
[iter_182](docs/task_tree/iterations/iter_182_safe_attr_sweep.md)
**iter_183 (续)**: scanner 跳过 Store 上下文 (74→70); 逐点定性: **~60 处是我们
自己 dataclass 的误报**, 真实点仅 **5 处** (port_sym.type ×2 / _symbol.name /
member_val.name ×2 / node.body) 已修。**关键发现**: `hasattr(x,"name")` 在 pyslang
上**不安全** (只吞 AttributeError, UnicodeDecodeError 穿透) → 属性探测应用
`safe_attr(x,"name",None) is not None`。
[iter_183](docs/task_tree/iterations/iter_183_safe_attr_genuine_sites.md)
[iter_181](docs/task_tree/iterations/iter_181_bench_stability.md)

**已闭环**: C 路线 (iter_179~180) / 参数化成员 (iter_178) / adapter 拆解
(iter_174~177) / 缓存目录 (iter_172) / 文档清理 (iter_171) 等。


**iter_159 (2026-09-06)**: 组合数组 receiver (嵌套 ElementSelect: 成员数组
bus[0] + 常量索引 → p.bus[0]; 变量索引动态跳过) + E15 默认参数语义定案
(常量源空答合理, 不建假信号); 缺口全闭环; unit +2; 回归 2009 passed。
[iter_159](docs/task_tree/iterations/iter_159_composite_array_defaults.md)

**iter_158 (2026-09-06)**: **E5/E13 方法内嵌套调用** (方豆 "继续做 e5 e13",
静态限定: 动态分派文档标记) — _expand_nested_class_calls: 方法体遍历找
Call (StatementList body.list, 收敛 attr); receiver 编译期定 (隐式 this →
外层实例 / 显式成员 i → receiver.i); 实参经 param_map (symbol.name 修复
垃圾节点); 递归 depth≤3。坑: list(StatementList) 异常静默吞 → 删;
symbol 对象 str 垃圾。E5 fanin(p.data)={d,p.tmp} / E13 fanin(p.i.val)={d};
unit +2; 回归 2011 passed。
[iter_158](docs/task_tree/iterations/iter_158_e5e13_nested_calls.md)

**iter_157 (2026-09-06)**: class 缺口修轮 1 (方豆 "逐个修") — E7 继承方法
(_find_class_method 沿 extends 链递归父类) / E8 class 数组 receiver
(ElementSelect: arr[0] → value+selector, 类型剥 elementType; 元素隔离) /
E3 跨实例成员参数 (rhs other.data: class 形参 → 实参替换 top.p2.data);
E5/E13 (隐式 this) + E15 (默认参数) 登记遗留。unit +3; 回归 2008 passed。
[iter_157](docs/task_tree/iterations/iter_157_class_gap_fix1.md)

**iter_156 (2026-09-06)**: class **对抗测试** (方豆 "构造极端用例找问题") —
19 场景: 12 通过 (多实例隔离/成员交叉/条件体/package/命名参数/位选/
solve-before 约束/空类/实例名==类名); **修 2 真 bug**: E11 module 同名
function 抢 class 方法 (receiver 优先序) + E4 class 函数返回值 (top.get
假节点 → receiver.data, module 隐式返回跳过); 登记 6 缺口 (E7 继承/E8
数组/E3 跨实例参数/E5·13 方法内嵌套/E15 默认参数)。unit +3; 回归
1150 passed。
[iter_156](docs/task_tree/iterations/iter_156_class_adversarial.md)

**iter_155 (2026-09-06)**: **C5 Accuracy Claim 转正** (无代码) — audit Claim:
class/constraint 从 hybrid 例外域转正为追踪承诺域 (语义域/L1 结构/L2 查询
+建模决策表 class 类型级·约束行); 仍例外: covergroup/SVA/procedural/inline;
README 同步 class 追踪能力。主全量 **3085 passed** (class C1~C4 后零回归)。
[iter_155](docs/task_tree/iterations/iter_155_c5_claim_promotion.md)

**iter_154 (2026-09-06)**: **C4 kind 收束 + namespace + 冲突检测** (D5) —
实证隐患: 类型级 fanin(packet.data)={packet.addr} (模板驱动被当答案) +
同名 class 静默丢 (get_classes 按 name 去重源头杀定义, 冲突检测形同虚设)。
修: A 类型级 CLASS_PROPERTY fanin 守卫 (主循环+depth1, 模板不作实例答案,
实例保持) / B namespace 注释 (类型级 filter 后加入=显式保留) / C 冲突检测
(get_classes 改对象身份去重 — 根因修 + class_graph_builder 同名告警首保)。
unit +3; 回归 1999 passed。
[iter_154](docs/task_tree/iterations/iter_154_c4_kind_namespace_conflict.md)

**iter_153 (2026-09-06)**: **C3 constraint 语义查询** (D4) — 约束图已全
(CONSTRAINS/HAS_LHS/HAS_CONDITION/HAS_CONSEQUENT/HAS_ALTERNATE); 新建
query/constraint.py ConstraintTracer.trace(prop) → 约束块/vars/条件 (类型级
+ 实例属性自动解析: MEMBER_SELECT 反向 + REG fallback 经实例 IS_INSTANCE_OF);
约束不进数据 fanin; unit +4。
[iter_153](docs/task_tree/iterations/iter_153_c3_constraint_tracer.md)

**iter_152 (2026-09-06)**: **C2 实例↔类型级桥 + 查询语义** (D3) — 实证:
实例成员节点按需创建 (p1.data 建 / p2.data 未用不建); 实现 unified_tracer
3 关系 API (trace_class_members 结构参考 / trace_class_instances 反向 /
trace_member_instances 仅已建); 桥 = 查询遍历非反向边 (图不变);
fanin 数据端点语义保持; unit +4。
[iter_152](docs/task_tree/iterations/iter_152_c2_instance_type_bridge.md)

**iter_151 (2026-09-06)**: **C1 class 方法调用链** (按架构决策 D2) —
语义形态: Call.thisClass (receiver) + SubroutineSymbol; ClassSymbol 成员在
迭代 (body 空); 实现: _handle_invocation receiver 解析 → _find_class_method
(get_classes 按 receiver 类型匹配) → _create_invocation_edges class 成员
展开 (internal_drivers 非形参目标 → 实例属性, rhs 经 param_map);
fanin(top.p.data) = {din} (p.set(din), C1 前空); 未调用不展开; module
调用不回归; unit +4; 回归 1157 passed。
[iter_151](docs/task_tree/iterations/iter_151_c1_class_method_call.md)

**iter_150 (2026-09-05)**: class 追踪架构决策落档 (方豆 "从未来可维护性
考虑" + 拍板) — 5 决策: D1 单图分层 (不拆隔离, 图基建一份) / D2 方法调用
复用 SubroutineExpander 展开 (一套调用语义, 不建第二套) / D3 类型级=结构
宿主、实例级=数据端点 (无聚合债) / D4 约束查询独立 tracer (范式可复用
covergroup) / D5 kind 守卫集中 + namespace 规则 (消除类型级不过滤的未定义
行为)。
[决策](docs/architecture/class_tracing_architecture_decision.md)

**iter_149 (2026-09-05)**: class 追踪整体规划 (方豆 "先整体规划 class 相关,
covergroup 单独") — 现状实证: class 图结构/约束/继承/方法赋值 ✅; 实例属性
追踪 ✅ (fanin(p.addr)={din}); **差距**: 方法调用链断 (p.set(x)→data 无驱动,
最大缺口) / 实例↔类型级桥 / constraint 语义查询 / 查询层 class kind。
规划文档 C1~C5 迭代路线 (方法调用链 → 实例↔类型桥 → 约束查询 → kind 收束
→ 声明转正)。
[规划](docs/architecture/class_tracing_plan.md)

**iter_148 (2026-09-05)**: README 超能力宣传校对 (方豆 "cdc 描述先去掉") —
cdc/timing/risk 命令标 EXPERIMENTAL 却被 README 当能力列 → 从 Experimental
节 + CLI 能力表去除; 补 EXPERIMENTAL_FEATURES.md 链接; sva timing 真实
保留。无代码改动。
[iter_148](docs/task_tree/iterations/iter_148_readme_scope_fix.md)

**iter_147 (2026-09-05)**: README 同步 (方豆 "readme 是不是可以更新?") —
日期 2026-09-05 / 测试数 3071; 新增 📜 Accuracy Claim 三层声明节;
位对位/无 string fallback/CVA6 编译验证描述; 文档链接补审计+纪律。
无代码改动。
[iter_147](docs/task_tree/iterations/iter_147_readme_update.md)

**iter_146 (2026-09-05)**: coverage_generator stale skip 测试清理 (2 个
V6.9 visitor 删除遗留) — AST 级精确删除, 路径已由新测试覆盖; 套件
2 skip → 0, 177 passed。无代码改动。
[iter_146](docs/task_tree/iterations/iter_146_stale_skip_cleanup.md)

**iter_145 (2026-09-05)**: benchmark 测试环境修复 (方豆 "先处理 1") — 真因三层:
①/tmp filelist 缺失 (误判 HOME env 数月) ②axi repo 版本演进 (target
axi_xbar_dp_ram 不存在) ③free-floating type-param 预 elab (axi_demux,
CVA6 cvxif 同款)。修: **SVCompiler/UnifiedTracer top_modules 参数** (pyslang
options.topModules — 只 elaborate 目标树, iter_140 弃用方案落地) +
GenericClassDefSymbol 防崩 (真 bug) + pr5 filelist 自动生成 + 断言按真实
数据修正。pr5 11 skip → **10 passed**; picorv32 benchmark 11 passed
(数据更准: IM 0 = 自包含真实); 全量 3071 passed。
[iter_145](docs/task_tree/iterations/iter_145_benchmark_env_fix.md)

**iter_144 (2026-09-05)**: 方豆 "gate 和 sva 就先不做了, 用文档记录" —
L3 剩余 2 项拍板暂缓: #4 gate G-2/G-3 (增强型, 对查询无影响, 需
delay/strength 分析时再启) / #6 iter_121 SVA semantic 消歧重构 (架构
整洁型, 无用户可见收益, SVA 补丁堆叠时再启)。audit 反例表 + backlog
标注 🕐 暂缓 + 触发条件。无代码改动。
[iter_144](docs/task_tree/iterations/iter_144_defer_gate_sva.md)

**iter_143 (2026-09-05)**: A2 位对位**切片偏移** (iter_137 残留 / Claim L3 #3
收窄) — bus↔切片 CONNECTION (.y(y[7:4])) 位桥第二段: 声明序低位对齐
(bus[blo+off] ↔ slice[slo+off]), bus 侧位节点存在才建 + 切片侧单 bit
节点缺失则创建 (**不建 BIT_SELECT 聚合边** — 避免 bus 提升查询收位驱动
污染悬空位); 双向贯通: fanin(top.y[7]) = {a[3] 链} (偏移 4),
fanin(u_sub.a[3]) = {top.a[7]}; 悬空位保持 bus 粒度干净; 宽度不匹配不
瞎桥。unit +3; 全量 3061 passed。A2 位对位 (同构+切片) 全闭环。
[iter_143](docs/task_tree/iterations/iter_143_a2_slice_bridge.md)

**iter_142 (2026-09-05)**: interface 多写共享诊断 (Claim L3 #2) — 7 场景
实测 (双 writer / writer+reader / top 直驱 / master 写+slave 读 / 双写+
读 / modport / 同成员回读): iter_129 单向桥方向逐实例独立判定正确 —
多写给**多源集合**、读不反向、外部直驱并入, **无真缺陷**; "归属单点"
依赖协议时序 = 语义边界 (与 inout #1 同构)。反例 #2 闭环 → 反例表剩
2 项 + 1 重构待办。顺带 Accuracy Claim 文档演进标注 (iter_136~141:
L1 连接完整性/解码健壮性, L2 位对位/控制排除, 语料 3058)。无代码改动。
[iter_142](docs/task_tree/iterations/iter_142_iface_multiwrite_diag.md)

**iter_141 (2026-09-05)**: iter_140 续 — 解码健壮性**批量修复** (~15 点,
6 文件): pyslang pybind 属性/str() 在非 utf8 identifier 抛
UnicodeDecodeError 的系统性点全换 safe_attr/safe_str + 新 helper
safe_symbol_name (always/driver/function/semantic_adapter/_common/
expression_tree) — 崩溃 → warning (提取路径不再整图崩)。CVA6 完整建图
推进后 **Segmentation fault = 8GB 内存/原生边界** (iter_059 先例, 非
代码 bug, 大内存机器可验); core 编译已通 (iter_140)。unit+integration
1543 passed。
[iter_141](docs/task_tree/iterations/iter_141_decode_robustness.md)

**iter_140 (2026-09-05)**: CVA6 strict 编译 (Claim L3 #7) — 特征代码法:
①44 错根因 = cvxif_example **未实例化 type-param free-floating 模块**
(pyslang 用默认 type=logic 检查 body → 成员访问 InvalidMemberAccess;
Verilator 只 elaborate 实例树不报) — 最小复现确认, filelist 剔 3 示例文件
②**compiler.py override-orphan 假错修复** (override 指向被 drop 模块 →
CouldNotResolveHierarchicalPath 假错不该 fatal; 跳过重编; 重建须置
_comp=None 否则 0 SyntaxTree 空编译) ③解码健壮性 ×2 (_common.get_signal /
semantic_adapter MemberAccess — CVA6 大设计暴露非 utf8 identifier 崩溃)。
CVA6 core **编译通过** (root 含 cva6); 完整建图剩解码点 (always_extractor
hasattr 等) — iter_141 续。unit+cli 1514 / unit+integration 1543 passed。
[iter_140](docs/task_tree/iterations/iter_140_cva6_compile.md)

**iter_139 (2026-09-05)**: iter_138 方案 2 实施 (方豆拍板 "condition 已记录
不需 driver 重复") — 条件/分支边族 (BRANCH_*/CASE_*) 与 CLOCK/RESET 同规则
**不进数据 fanin** (query/signal.py; 控制信号保留在 DRIVER.condition +
条件边, detailed 可查)。i2c 双驱动 fanin(sda) = {data_master, data_slave,
u_slave.data} — en 不对称杂音清除 (双侧对称); ternary/case 数据源保持
({a,b} / {a,b,c})。unit +4; 全量 3058 passed。
[iter_139](docs/task_tree/iterations/iter_139_cond_signal_exclusion.md)

**iter_138 (2026-09-05)**: i2c 开漏多驱动归属诊断 (iter_129 backlog / Claim
L3 #1) — 6 场景实测: iter_129 单向建模已覆盖主要形态 (双器件多源集合 /
外部驱动+只读无反向污染 / 级联穿透); 定性: "归属单点"依赖运行时 en =
**静态语义边界** (fanin = 可能驱动方集合, 已实现), 非连接缺失。发现小
缺陷: 三态 en 控制信号 fanin 不对称杂音 (顶层缺/实例进) — **iter_139 已修
(方案 2)**。Claim L3 #1 闭环 (语义澄清 + 缺陷修复)。
[iter_138](docs/task_tree/iterations/iter_138_inout_multidriver_diag.md)

**iter_137 (2026-09-05)**: A2 位对位折算 (audit 后续项 / Claim L3 #3) —
bus↔bus **同宽同构直连**的位查询贯通: graph_builder 补位桥边
(_expand_bus_conn_bit_bridges: 仅两侧位节点都存在时, 不造假节点 —
纯 bus 直通保持总线粒度, iter_126 truth 不变) + 查询位桥出口递归
(CONNECTION src 位节点的 bus 父是 PORT_OUT → 不 append 桥中间节点,
递归其内部驱动)。fanin(top.y[3]) == fanin(top.u_sub.y[3]) (顶层位 ==
sub 内位一致, 贯通到 sub 内 y[3] 源 + 输入跨桥到顶层位)。unit +3;
全量 3054 passed。残留: 切片/非零 base 位偏移映射 (.y(y[7:4]))。
[iter_137](docs/task_tree/iterations/iter_137_a2_bit_bridge.md)

**iter_136 (2026-09-05)**: iter_119 "slang 合并" 观察复现 → 真身 = **input
端口位宽不匹配时 Conversion 壳未剥 → 连接静默丢** (leafm 1 位接 2 位切片,
nested 4/4 input 连接缺, fanin 断 u_leaf.a; output 侧 Assignment 不受影响
故 iter_120 后 y 侧 OK / a 侧残留, 且无断言覆盖)。修: get_instance_connection
Conversion 链式剥壳 → operand 交 _conn_expr_to_signal; unit +3; 全量
3051 passed (serv 1 env 假失败同前)。slang 观察闭环, 非 slang 合并。
[iter_136](docs/task_tree/iterations/iter_136_conn_conversion_shell.md)

**iter_135 (2026-09-05)**: 方豆问询"图是否 = 代码准确映射" → 结论落档:
**不能无限制说** — 图 = 建模决策产物 + 范围限定 + 已知反例。审计文档头部
新增 📜 Accuracy Claim 分层声明: L1 结构层 ✅ (已验证域) / L2 查询层 ✅
(限建模粒度语义) / L3 深层语义层 ❌ (多驱动归属不承诺, 7 项反例 = backlog,
修一项移一项)。纯文档, 无代码改动。
[iter_135](docs/task_tree/iterations/iter_135_accuracy_claim.md)

**iter_134 (2026-09-05)**: 嵌套 generate 深层重复段假节点清理 — gen_block
只取直接宿主 generate 段 (hp 紧邻实例名前段 name[N]); aes 假节点
279/1116→0, cordic 105→0 (truth 更新); 连带修 wrapper cross get_edges
全查 + PORT_OUT 内部驱动自递归 (test_deep 回归)。unit +3; 全量非
opensource 3048 passed (22 env/既有 skip; serv 1 假失败 = HOME 重定向
空 filelist, 真实 HOME 单跑通过)。
[iter_134](docs/task_tree/iterations/iter_134_nested_gen_dup_cleanup.md)

**iter_133 (2026-09-05)**: iter_131/132 真实项目复验 (aes 4834 节点/272
实例) — fanin 位隔离零跨 entry 生效; dataflow 已知限制区分。复验暴露
**嵌套 generate 深层重复段假节点 backlog** (aes 型 351/4834: ROUND[1].
U_ROUND.ROUND[1].U_SUB, 内层重复外层段; baseline 既有, fanin 主链 0 污染)
已登记 audit 🐛 区。
[iter_133](docs/task_tree/iterations/iter_133_real_verify.md)

**iter_132 (2026-09-05)**: generate per-entry fanin 位隔离 — fanin(top.y[3])
串入 G[0..2] 双根因修: A2 提升加 incoming-CONNECTION 守卫 (有实例输出源不
提升) + wrapper cross 加"无内部驱动才跨" (注释意图漏实现)。fanin(y[i]) 恰
[G[i].u_leaf.y], bus 聚合/wrapper/纯直通/xor 全保; unit +3; 全量 2934 passed。
[iter_132](docs/task_tree/iterations/iter_132_genfor_fanin_isolation.md)

**iter_131 (2026-09-04)**: usage 4 失败深挖 — 1 个真回归 + 3 测试债务。
真回归: dataflow _find_paths bus 查询首个非空候选组合即 return (iter_118
per-entry 后丢 req_i[1..7], arbiter 40→8→1) — 修复为合并所有候选组合,
8 paths 恢复; golden 40→8 同步 (usage + subfunction)。测试债务: p6 计数
断言过时 / m12 目录依赖 / factory 单文件 grep。unit +3; 主全量 2928 passed。
[iter_131](docs/task_tree/iterations/iter_131_dataflow_bus_agg_fix.md)

**iter_130 真实验证结论 (2026-09-04)**: iter_126~129 改动在真实设计
(aes 11292 nodes / CORDIC / minimal_3module CLI) 零副作用; usage 套件
4 失败当时判定基线既有 (后经 iter_131 深挖: 1 真回归 + 3 债务)。
push 12 commits 至 backup 完成。
[iter_130](docs/task_tree/iterations/iter_130_real_verify_wrapup.md)## 🔥 当前任务

**当前**: 等待方豆指示 (最近完成: iter_121 SVA 6 缺口 / iter_122 covergroup cross /
iter_125 inline 约束决策 — 见 overview rows 42-44)

**#7 inline 约束: 已决策暂缓不做** (iter_125, 方豆拍板) — semantic 侧确认不可达:
pyslang 语义模型对"声明级约束有符号 / 调用点 randomize-with 无符号"是固有不对称
(ConstraintBlock 只计 named; 语句是 StatementKind 非 SymbolKind); syntax 唯一入口
但受 pyslang import-order env bug 制约。维护:
[决策文档](docs/architecture/inline_constraint_semantic_unavailable.md) (含未来改善观察)

**准确性审计 (2026-09-03/04)**: [signal_graph_accuracy_audit.md](docs/architecture/signal_graph_accuracy_audit.md)
- ✅ A1 无 target_module → generate 嵌套实例内部缺失 (iter_126, 收窄后):
  库默认保留无 target 类型级多模块契约; CLI 可视化入口 (build_viz_tracer 无
  --module) 自动单 top target — cordic 365→542 节点/667 rects, genblk
  实例内部真实 assign 出现。`build_graph(..., auto_target_single_top=True)`
  供库调用方 opt-in
- ✅ A2 子模块输出总线直连顶层位 → 位查询空答 (iter_126): 位节点不存在/无驱动
  → 提升父总线 (总线粒度; 位对位折算 = 后续项)
- ✅ A3 端口 DRIVER 自环计入源 (iter_127): 查询层跳过 assign_type="internal"
  自环 (实例输出端口标记); nonblocking 真自环 (state<=state+1) 保留
- ✅ iter_133 backlog 嵌套 generate 深层假节点清零 (iter_134): gen_block
  直接宿主判定 (hp 末段前段 name[N]) — aes 279/1116→0 / cordic 105→0;
  wrapper cross 守卫 get_edges 全查 + wrapper_passthrough 自递归连带修
- ✅ 待验证候选 5 项全闭环 (iter_128/129): struct 字段正确; 派生时钟域
  CLOCK 提取正确 + fanin CLOCK 假驱动修复; 顶层输入空 fanin = 预期锁定;
  inout 跨模块连接修复 (output 式同线 CONNECTION); interface 成员级桥修复
  (单向按驱动方向: writer/slave) + fanin 假驱动消除 (A2 提升目标限 data 类)
- ⏳ 更深语义 backlog (iter_129 记录): inout 双向多驱动归属 (i2c 开漏) /
  interface master+slave 同线多写共享语义 — 当前单向链逐层可追, 多驱动
  归属需专项拍板

**backlog (未启动, 按序)**:
1. ~~gate G-2 (drive strength/delay) + G-3 (UDP table)~~ — 🕐 方豆拍板暂缓
   (2026-09-05): 增强型对查询无影响; tasks/L2_gate_primitive_support.md
   (G-1 ✅ iter_115); 触发: 需 delay/strength/UDP 分析时
2. ~~iter_121 补丁 semantic 消歧重构~~ — 🕐 方豆拍板暂缓 (2026-09-05):
   架构整洁型无用户可见收益; 触发: SVA syntax 症状修堆叠时
3. inout 双向多驱动归属 (i2c 开漏) — iter_138 已澄清为静态可能源集合
   (正确语义); 归属单点依赖时序超出承诺域, 无需代码专项 (closed)
5. cvfpu 全量覆盖 (vendor common_cells + PACE override) — 家族已由 fpnew 覆盖, 低优先
## ✅ 最近完成 (保留 3 条汇总, 逐项细节看 git log + docs/task_tree/iterations/)

| 完成时间 | 任务 | 产出 |
|---|---|---|
| **2026-09-05** | **benchmark 环境修复 + topModules (iter_145)** | 真因三层 (filelist 缺失 / axi 版本演进 / free-floating type-param); SVCompiler+UnifiedTracer top_modules; GenericClassDefSymbol 防崩; pr5 filelist 自动生成 + 断言修正; pr5 11 skip→10 passed, picorv32 11 passed; 全量 **3071 passed**. [iter_145](docs/task_tree/iterations/iter_145_benchmark_env_fix.md) |
| **2026-09-05** | **A2 切片偏移位桥 (iter_143)** | bus↔切片 CONNECTION 位桥 (声明序低位对齐 + 切片位节点创建, 无聚合边防污染); 双向位级贯通 (y[7]↔a[3] 偏移4); 悬空位干净; unit +3; 全量 **3061 passed**; A2 位对位全闭环. [iter_143](docs/task_tree/iterations/iter_143_a2_slice_bridge.md) |
| **2026-09-05** | **interface 多写诊断闭环 (iter_142)** | 7 场景实测 iter_129 单向桥正确 (多源集合/读不反向/方向逐实例独立); 无真缺陷; 反例 #2 闭环; Claim 文档演进标注; 无代码改动. [iter_142](docs/task_tree/iterations/iter_142_iface_multiwrite_diag.md) |
| **2026-09-05** | **解码健壮性批量修复 (iter_141)** | CVA6 暴露的非 utf8 identifier 解码崩溃 ~15 点 (6 文件) 全换 safe_attr/safe_str + safe_symbol_name; 崩溃→warning; CVA6 建图 = 8GB 内存/原生 segfault 边界 (环境项); unit+integration **1543 passed**. [iter_141](docs/task_tree/iterations/iter_141_decode_robustness.md) |
| **2026-09-05** | **CVA6 编译配方 + 修复 (iter_140)** | 特征代码法: 44 错 = 未实例化 type-param free-floating 模块 (pyslang 预 elab, filelist 剔 3 示例); compiler.py override-orphan 假错修复 (drop 模块 override 不 fatal); 解码健壮性 ×2 (非 utf8 identifier); CVA6 core 编译通过; 建图剩解码点 (iter_141). [iter_140](docs/task_tree/iterations/iter_140_cva6_compile.md) |
| **2026-09-05** | **条件控制信号排除 (iter_139)** | 三态/三目/case 的 en/sel 控制信号不进数据 fanin (与 CLOCK 同规则; condition 字段保留, detailed 可查); i2c 双驱动 en 杂音清除且双侧对称, ternary/case 数据源保持; unit +4; 全量 **3058 passed**. [iter_139](docs/task_tree/iterations/iter_139_cond_signal_exclusion.md) |
| **2026-09-05** | **inout 多驱动诊断 (iter_138)** | i2c 6 场景实测: 多源集合/穿透/方向均正确 — "归属单点"定性为静态语义边界 (依赖运行时 en); en 杂音小缺陷 (iter_139 修); Claim L3 #1 闭环. [iter_138](docs/task_tree/iterations/iter_138_inout_multidriver_diag.md) |
| **2026-09-05** | **A2 位对位同构直连 (iter_137)** | bus↔bus 同宽直连位查询贯通到位级: graph_builder 位桥边 (仅两侧位节点存在, 不造假节点; 纯 bus 直通保持总线粒度) + 查询位桥出口递归; fanin(top.y[3]) == fanin(top.u_sub.y[3]); unit +3; 全量 **3054 passed**. [iter_137](docs/task_tree/iterations/iter_137_a2_bit_bridge.md) |
| **2026-09-05** | **input Conversion 壳剥壳修复 (iter_136)** | iter_119 "slang 合并" 观察闭环: 真身 = input 位宽不匹配时 Conversion 壳未剥 → 连接静默丢 (nested 4/4 a 侧缺, y 侧 iter_120 已修); get_instance_connection Conversion 链式剥壳; unit +3; 全量 **3051 passed**. [iter_136](docs/task_tree/iterations/iter_136_conn_conversion_shell.md) |
| **2026-09-05** | **input Conversion 壳剥壳修复 (iter_136)** | iter_119 "slang 合并" 观察闭环: 真身 = input 位宽不匹配时 Conversion 壳未剥 → 连接静默丢 (nested 4/4 a 侧缺, y 侧 iter_120 已修); get_instance_connection Conversion 链式剥壳; unit +3; 全量 **3051 passed**. [iter_136](docs/task_tree/iterations/iter_136_conn_conversion_shell.md) |
| **2026-09-05** | **Accuracy Claim 落档 (iter_135)** | 审计文档头部分层声明: L1 结构 ✅ / L2 查询 ✅ 限粒度 / L3 深层 ❌ 不承诺 + 7 反例表 (修一项移一项); 纯文档. [iter_135](docs/task_tree/iterations/iter_135_accuracy_claim.md) |
| **2026-09-05** | **嵌套 generate 假节点清理 (iter_134)** | gen_block 直接宿主判定修深层嵌套假路径 (aes 279/1116→0, cordic 105→0); wrapper cross get_edges + PORT_OUT 自递归连带修; unit +3; 全量非 opensource **3048 passed** (22 env/既有 skip; serv 1 假失败 = HOME 重定向, 真实 HOME 通过). [iter_134](docs/task_tree/iterations/iter_134_nested_gen_dup_cleanup.md) |
| **2026-09-05** | **iter_131/132 真实复验 (iter_133)** | aes 4834 节点/272 实例复验: fanin 位隔离零跨 entry; dataflow 已知限制区分; 暴露嵌套 generate 深层重复段假节点 (351/4834, baseline 既有) 登记 audit backlog. [iter_133](docs/task_tree/iterations/iter_133_real_verify.md) |
| **2026-09-05** | **generate per-entry fanin 位隔离 (iter_132)** | fanin(top.y[3]) 串入 G[0..2] 双根因: A2 提升忽略 incoming CONNECTION + wrapper cross 无条件跨; 修后 y[i] fanin 恰 [G[i].u_leaf.y]; bus 聚合/纯直通/xor/wrapper 全保; unit +3; 全量 **2934 passed**. [iter_132](docs/task_tree/iterations/iter_132_genfor_fanin_isolation.md) |
| **2026-09-04** | **dataflow bus 聚合修复 + usage 债务清理 (iter_131)** | 真回归: _find_paths 首个非空候选组合即返 (iter_118 per-entry 后 bus 查询丢位, arbiter 40→8→1) → 合并所有候选组合, 8 paths 恢复; golden 40→8; 3 测试债务 (p6/m12/factory) 清理; unit +3; 主全量 2928 passed. [iter_131](docs/task_tree/iterations/iter_131_dataflow_bus_agg_fix.md) |
| **2026-09-04** | **inout + interface 建模 (iter_129)** | inout 跨模块连接修复 (connection_extractor inout 分支, output 式同线 CONNECTION, fanin 穿透实例三态链); interface 成员级桥 (收集 InterfacePortSymbol links + 后处理按驱动方向单向桥) + A2 提升目标限 data 类消假驱动; unit +7; 全量 **2928 passed**. [iter_129](docs/task_tree/iterations/iter_129_iface_inout_modeling.md) |
| **2026-09-04** | **审计待验证候选实测 (iter_128)** | 5 候选实测: 修 fanin CLOCK/RESET 假驱动 (跨模块时钟链) + A2 位提升条件双修 (struct 字段泄漏/位选 seen 污染); 登记 inout 跨模块连接 + interface 成员级缺口 (建模待拍板); 顶层输入空 fanin 预期锁定; unit +8; 全量 **2921 passed**. [iter_128](docs/task_tree/iterations/iter_128_audit_candidates_verify.md) |
| **2026-09-04** | **准确性审计 A3 修复 (iter_127)** | 实例输出端口 internal DRIVER 自环不计为 fanin 驱动源: 查询层 (主循环 + _find_drivers depth=1) 跳过 assign_type="internal" 自环, nonblocking 真自环 (state<=state+1) 保留; 图结构不改; unit +4; 全量 **2913 passed / 0 failed**. [iter_127](docs/task_tree/iterations/iter_127_accuracy_a3.md) |
| **2026-09-04** | **准确性审计 A1/A2 修复 (iter_126)** | A1 收窄: 库默认保留无 target 类型级契约 (8 回归恢复), CLI visualize 入口 (build_viz_tracer 无 --module) 自动单 top target — cordic 365→542 节点 genblk 内部真实 assign 恢复; A2 总线直连位查询提升非空; A1 测试弱断言 (self-loop) 重写为非自环; 全量 **2913 passed / 0 failed**. [iter_126](docs/task_tree/iterations/iter_126_accuracy_a1_a2.md) |
| **2026-09-02** | **测试资产扩充 + 缺陷修复收尾 (iter_086~108)** | truth 层 32→130 测试 (T1-T12 扩充 + A-F 修复断言); 缺陷 A-F (expression 字节切片 / net-decl 位宽 / LHS concat zip / ternary 常量 / part-select 宽度 / generate-if always) + ELK dangling + #23/#24 generate 单块 wire 全修; integration 419+0 历史首次全绿; 全量 2843 passed. 迭代记录 iter_086~108 |
| **2026-09-02** | **Truth 层扩充 T1-T12** | 12 文件 + 5 fixture, 集合相等断言; assign/clock-reset/case/位选/concat/function-task/parameter/alias/class/generate-if-case/SVG 布局/查询精确集. [iter_100 汇总](docs/task_tree/iterations/iter_100_t1_t12_wrapup.md) |
| **2026-09-02** | **B 组复查 + cli 3 失败修复** | iter_082 误分类纠正 (darkriscv SVG 断言 + 删 --no-strict); models.py width=None 序列化根因; unit+cli 1484 passed. [iter_086](docs/task_tree/iterations/iter_086_group_b_recheck_real_project_viz.md) / [iter_087](docs/task_tree/iterations/iter_087_cli_3_failures_fix.md) |

---

## 📋 下一个候选 (未启动, 不要自己开工 — 先问方豆)

- **工业算法模块开源项目调研** (进行中, 不在本任务内推进): 典型工业算法模块
  (CORDIC / 加法器族 / 乘法器族 / DSP 算法) 开源 RTL 摸底已 clone 至 `~/my_dv_proj/openrtl/`,
  REPOS.md 统一登记; 摸底缺口 → 逐个修复 (CORDIC iter_109~111, gate primitive 本任务)。
  剩余: fpnew/hardware/cvfpu 扫尾。
- ~~#7 — 迁 pyslang 11.0 native API~~ ✅ **已完成** (2026-08-29, iter_053-059)。
  遗留: CVA6/coralNPU/vortex 3 项目 strict 编译受阻 (pyslang↔项目语义不兼容),
  见 ARCHITECTURE_TODOLIST §#7。

---

## 📝 维护说明

1. **同时只有 1 个"当前任务"** — 多任务并行是错觉, 会导致两边都做不完
2. **切换任务前**, 把当前任务移到"已启动但暂停", 写清楚下一步是什么
3. **任务完成后**: 写 `docs/task_tree/iterations/iter_NNN_*.md` → 更新长期 todolist → 移到"最近完成"
4. **阻塞时必须写明**: 阻塞在什么、需要谁决策、有哪些选项和代价
5. **本文件必须和实际工作同步更新** — 文档更新和实际工作同等重要。
   任务开始前设为当前任务, 进行中逐项勾选, 完成后立即清出。
   完成判定 = **代码 ✅ + 测试 ✅ + 文档 ✅**, 只写完代码不算完成。
   详见 `AGENTS.md` → "📓 开发日志与迭代记录 → 任务前后必须更新文档"
