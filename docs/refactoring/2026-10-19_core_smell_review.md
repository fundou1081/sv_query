# 核心代码坏味道评审 + CLI 命令面减法方案

> **日期**: 2026-10-19 · **类型**: 评审 (只读分析, 未改代码) · **发起**: 方豆
> **原话**: "找出 core 代码中的坏味道，并评估严重程度。结合架构信息一起 review。
> 我们要对功能做一些减法，或者说分层处理。现在 cli 命令太多。以这个角度，进行 review。"
> **方法**: 全仓 AST 扫描 (函数长度/裸异常/重复定义/导入图) + 注册表盘点 + 逐命令测试与文档引用统计 + 真实 CLI 探测
> **关联**: [ARCHITECTURE.md](../ARCHITECTURE.md) · [CLI_SURFACE.md](../CLI_SURFACE.md) · [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md)

---

## 0. 严重度定义

| 级别 | 含义 | 处置 |
|---|---|---|
| 🔴 **P0** | 会给用户**错误答案**或破坏契约 | 立刻修 |
| 🟠 **P1** | 结构性债务：阻碍后续开发 / 修复成本随时间指数上升 | 排期修 |
| 🟡 **P2** | 局部脏乱：可读性、一致性、文档漂移 | 顺手修 |
| ⚪ **P3** | 观感问题 | 有空再说 |

**本次没有发现 P0。** 架构方向是干净的（见 §2），问题集中在**规模与表面积**。

---

## 1. 结论摘要

### 1.1 五个最值得动手的点

| # | 问题 | 严重度 | 体积/规模 | 一句话 |
|---|---|---|---|---|
| 1 | `src/` 里有 **3,248 行归档代码**仍在打包路径内 | 🟠 P1 | 16 文件 | 40% 的 `graph/viz` 是死的，还会被 grep 到、被新同学改 |
| 2 | `LoadExtractor._get_signal` 是 **283 行死方法** | 🟠 P1 | 283 行 | 自递归、无入口，注释还写着"已删死方法"却漏了它 |
| 3 | `UnifiedTracer` **36 个公开方法**跨 10 个领域 | 🟠 P1 | 1,403 行 | 改任何一处都要碰同一个上帝对象 |
| 4 | CLI **74 规范命令 + 30 别名 = 104 个叶子** | 🟠 P1 | 47 默认可见 | 你要减的就是这个；其中 24 个别名是 exp 老路径 |
| 5 | CLI **没有统一输出层**：`output_json` ×7、`output_text` ×6 | 🟡 P2 | 13 份副本 | 加一个字段要改 7 处，格式必然分叉 |
| 6 | **双导入根**：`from src.*` 27 处 vs `from cli/trace.*` 1,012 处 | 🟡 P2 | 启动时 3 个模块双份 | 同一文件被加载成两个模块对象，类身份与模块级状态会分裂 |

### 1.2 减法目标（建议）

| 指标 | 现在 | 目标 (T2 完成后) | 手段 |
|---|---|---|---|
| 规范命令 | 74 | **~52** | 同概念合并 (§5.2) |
| 别名 | 30 | **6** | exp 老路径到期下线 |
| 默认可见面 (`capabilities`) | 47 | **~33** | 合并 + 降级 |
| `core` 层 | 34 | **~26** | 合并同族 |
| `view` 层 | 13 | **~9** | 3 个叙述类合成 1 个 |
| `src/` 代码量 | 64,336 | **-3,600 行** | 删归档 + 删死方法 (T1，零风险) |

---

## 2. 架构现状（先确认方向是对的）

```
src/
├── trace/          44,620 行 / 114 文件   引擎: 图构建 → 查询 → 分析
│   └── core/
│       ├── graph/      图模型 + 分析器 + 可视化后端 (elk_bridge 2,340)
│       ├── query/      查询层 (signal / load / module / clock_domain)
│       ├── extractors/ 语法级抽取器 (10 个文件)
│       └── semantic/   语义层
├── cli/            15,987 行 / 54 文件   分层: core(34) / view(13) / exp(24) / dev(3)
└── applications/    3,724 行 / 14 文件   领域应用: bus / cpu(空) / operator(空)
```

**方向检查（机械验证）**：

| 检查 | 结果 |
|---|---|
| `trace` / `applications` 是否 import `cli` | ✅ 0 处（无反向依赖） |
| `core` 层是否写文件 | ✅ `check_cli_layers` R3 零基线 |
| 分层是否有单一真相源 | ✅ `src/cli/_registry.py`（74 条声明） |
| 是否存在完全没人 import 的模块 | ⚠️ 2 个孤立模块 + 16 个归档模块（见 A1 / A10） |
| 裸 `except:` | ✅ 0 处 |

结论：**分层骨架是好的**，`tools/check_cli_layers.py` 的 R1~R8 已把方向性错误挡在门外。
问题不在"层次对不对"，而在**每层的体量与入口数量**。

---

## 3. 引擎坏味道 (`src/trace/`)

### A1 🟠 P1 — 3,248 行归档代码仍在 `src/` 里

**证据**

```
src/trace/core/graph/viz/_archived/       4 文件   743 行
src/trace/core/graph/viz/_archived_dot/  12 文件 2,505 行
合计                                     16 文件 3,248 行
```

- 无任何 import（全仓 grep 0 命中）
- 但 `pyproject.toml` 的 `packages.find include = ["src.*", ...]` 会**打包进 wheel**
- 占 `graph/viz` 模块的 **40%**（viz 总计 8,226 行）

**影响**
1. 新人 grep `render_datapath` 会搜到两套实现，不知道哪套在跑
2. 度量失真（"viz 模块 8k 行"其实只有 5k 是活的）
3. 违反本项目的归档规则：**该进 `docs/archive/`，不是留在源码树**

**建议**: 整体移到 `docs/archive/2026-10-19-src-archived/` 并在该目录 README 说明来源。
零行为变化。

### A2 🟠 P1 — `LoadExtractor._get_signal` 是 283 行死方法

**证据**
- `src/trace/core/load_extractor.py:114`，函数体到 396 行（283 行）
- `extract()`（24~108 行）**从不调用它**；全仓无外部调用者
- 唯一的调用都是它**自己递归自己**（L124/139/143/153/165/171/176/181/206/344/351/361/370/378/386）
- L110 还留着注释："[重构 2026-08-07] 删除孤儿死方法 `_parse_assign`" —— 删了一个，漏了这个

**影响**: 283 行看起来像"load 提取的核心逻辑"，实际是死代码；任何人按名字读代码都会被误导。
**建议**: 删除（若将来要复用，git 历史里有）。

### A3 🟠 P1 — `UnifiedTracer` 是 36 方法的上帝门面

**证据**: `src/trace/unified_tracer.py` 1,403 行，公开方法 36 个，覆盖 10 个领域：

```
构建/图      build_graph, load_graph, get_graph, get_module_graph, get_path_resolver, stats
实例         get_instances
信号追踪     trace_signal, trace_loads, trace_fanout, trace_fanin, trace_detailed, trace_fanin_detailed
模块         trace_module, trace_port, find_connected_modules
class        trace_class_members, trace_class_instances, list_classes, trace_member_instances
约束         trace_constraints
covergroup   trace_covergroup_sampling, trace_coverpoints, trace_covergroup_rand_linkage
时钟域       trace_clock_domain, trace_all_domains, find_synchronizers, check_cdc_violations
路径/环      find_path, detect_cycles
FSM          analyze_fsm  (+ 同文件里的 StateMachineAnalyzer/StateMachineInfo)
```

**影响**: 每次新增查询域都要往这个类加方法；它是所有 CLI 命令的必经之路，
所以"改一处、影响全部命令"的风险持续累积。iter_240/241 的跨模块改动已经验证了这一点
（一处遍历语义改动波及 130 个测试文件）。

**建议**（结构性，需拍板）: 按领域拆成 `SignalQuery` / `StructureQuery` / `ClassQuery` /
`ClockQuery`，`UnifiedTracer` 退化为**组合根**（构造 + 持有 + 转发），
而不是所有逻辑的宿主。

### A4 🟠 P1 — `elk_bridge.py` 单函数 908 行

**证据**: `expr_trees_to_elk` 908 行（L150）、`viz_to_elk` 584 行（L1379）、`_wrap_into_clusters` 288 行。
文件 2,340 行，是全仓最大文件（与 `cli/view/visualize.py` 并列）。

**影响**: 无法单元测试单个阶段；改布局逻辑要通读近千行。
**建议**: 按"收集 → 转换 → 聚类 → 序列化"四阶段拆函数，每阶段可独立断言。

### A5 🟡 P2 — `driver_extractor.py` 1,445 行中有 14 个"薄壳"

**证据**: 文件内 14 处注释写着"[ARCHITECTURE_TODOLIST #1 Step N] 薄壳, 实际逻辑在 extractors/*"。

这不是坏设计（重构时保留签名是对的），但**壳与实现混在一个文件里**，
读代码时无法一眼看出"这个文件到底实现什么"。
**建议**: 把 14 个壳集中到一个 `compat`/`facade` 段落或独立模块，文件头声明它现在是门面。

### A6 🟡 P2 — 246 处 `except Exception`

**分布 top 5**: `driver_extractor` 14 · `mig_validator` 13 · `cli/core/semantic/trace.py` 13 ·
`graph_builder` 12 · `unified_tracer` 11。

`tools/check_except_pass.py` 只查 `except: pass`（当前 0），**不查过宽的捕获**。
在查询路径上捕获 `Exception` 会把契约破坏伪装成"查不到"——
iter_241 的 `"None.sig"` 假 root 正是同一类问题的近亲。

**建议**: 分两步——① 给 `core` 查询路径加一条 warn 级检查（`except Exception` 在白名单外即警告）；
② 逐步收窄为 `(ValueError, AttributeError, KeyError)` 等具体类型。

### A7 ⚪ P3 — 26 个函数 >200 行

| 行数 | 位置 | 函数 |
|---|---|---|
| 908 | `graph/viz/elk_bridge.py:150` | `expr_trees_to_elk` |
| 584 | `graph/viz/elk_bridge.py:1379` | `viz_to_elk` |
| 572 | `connection_extractor.py:119` | `extract` |
| 480 | `extractors/always_extractor.py:136` | `_create_always_edges` |
| 472 | `extractors/function_extractor.py:757` | `_create_invocation_edges` |
| 433 | `query/signal.py:98` | `_trace_drivers_recursive` |

### A8 ⚪ P3 — 两个空占位包

`src/applications/cpu/`、`src/applications/operator/` 只有 `__init__.py`（"规划中"）。
**建议**: 要么删，要么补一份 README 说明规划，别留着空壳让人误以为有实现。

### A9 🟡 P2 — 双导入根，同一文件被加载成两个模块对象

**证据**

| 写法 | 出现次数 |
|---|---|
| `from src.cli...` / `from src.trace...` | **27**（`main.py` 20、`semantic/trace.py` 6、`view/arch.py` 1；tests 4） |
| `from cli...` / `from trace...` | **1,012**（tests 670） |

实测（`PYTHONPATH=src`，与 `run_cli.py` 同一条导入路径）：

```python
import cli.errors as a; import src.cli.errors as b   # a is b  →  False
import cli.exp.verif.verify as x; import src.cli.exp.verif.verify as y
x.verify_app is y.verify_app                          # →  False (两个 Typer app)
```

CLI 启动后 `sys.modules` 里同时存在两份的模块：`cli`、`cli._common`、`cli.core`
（`cli.errors` 等按需再加载时同样双份）。

`run_cli.py` 用 `from src.cli.main import run`，而 `main.py` 内部大多数 import 用 `cli.*`
——**两个根同时活着**。

**影响**
- `ErrorCode` (StrEnum) 会有两个类对象 → 跨根的 `isinstance` 判否（当前无 isinstance 用法，所以是**潜伏**的）
- 模块级可变状态（如 `errors.EXCEPTION_TO_CODE`）会分裂成两份
- 启动时多做一次导入 + 多一份内存

**建议**: 统一到 `cli.*` / `trace.*` 一个根（改 `run_cli.py` 入口 + 27 处 import），
并把"禁止 `from src.*`"加进 `check_cli_layers.py`（新规则 R9）。改动机械、可用全量门禁兜底。

### A10 🟡 P2 — 两个孤立模块（无任何引用）

| 模块 | 行数 | 验证 |
|---|---|---|
| `trace/core/graph/signal_graph_viewer.py` | **895** | 全仓 grep 仅自引用（除 `_archived_dot` 内） |
| `trace/core/builder/function_expander.py` | 131 | 全仓 grep 0 命中 |
| `cli/commands/__init__.py` | 5 | 空包（`commands/` 只剩 `__init__`） |

**建议**: 删除或确认用途后再补引用。`signal_graph_viewer` 895 行是笔不小的死重。

---

## 4. CLI 坏味道 (`src/cli/`)

### B1 🟠 P1 — 表面积：74 规范命令 + 30 别名 = 104 个叶子

| 层 | 命令数 | 默认可见 | 说明 |
|---|---|---|---|
| `core` | 34 | ✅ | agent 契约面 |
| `view` | 13 | ✅ | 人眼面 |
| `exp` | 24 | ❌ | 需 `--include-exp` |
| `dev` | 3 | ❌ | 内部调试 |
| **合计** | **74** | **47** | +30 别名 |

- `src/cli/main.py` 466 行里有 **55 个注册点**
- `core` 内部：`semantic` 17 / `locate` 7 / `state` 6 / `diagnose` 4

**这是方豆指出的核心问题**：默认可见 47 个命令，对"问一个信号"的人来说太多。

### B2 🟠 P1 — `core/semantic/trace.py` 1,840 行承载 5 个命令

`fanin` 383 行、`fanout`、`impact`、`evidence`、`overview`（view 层复用同一文件）+ `_generate_chain_dot` 366 行。
一个文件同时管：JSON 输出、文本输出、DOT 生成、风险评估、证据提取。

### B3 🟠 P1 — `view/visualize.py` 2,376 行承载 10 个命令

`chain`(383) / `_generate_chain_dot`(366) / `teach`(168) / `module`(151) / `pipeline`(117) / `datapath`(106) /
`timed`(84) / `dataflow`(62) / `graph`(66) / `gap`(13) / `compute`(46)。

### B4 🟡 P2 — 没有统一输出层

| helper | 副本数 |
|---|---|
| `def output_json` | **7** 处（graph / stats / diff / trace / dataflow / controlflow / expression） |
| `def output_text` | 6 处 |
| 三个 `_common` | `cli/_common.py` 336 行 / `core/semantic/_common.py` 61 行 / `_viz_common.py` 160 行 |
| 专用 helper | `_evidence_helpers.py` 784 行 |

**影响**: 统一 schema 版本号、统一错误输出、统一 `--pretty` 都要改 6 处；
新增字段时各命令格式必然分叉（iter_231 补 `--json` 时就发现了这个）。
**建议**: 抽 `cli/_output.py`（`emit_json` / `emit_text` / `fail`），命令只负责组装 dict。

### B5 🟡 P2 — 注册表里的 note 已过期（单一真相源在漂移）

实测：`python3 run_cli.py graph nodes --filelist <f>` **可用**（iter_236 已补 `--filelist`），
但 `_registry.py` 里 `graph dump/edges/find/nodes` 四条的 note 仍写着
「[缺口] 只支持 --file 单文件, 真实项目(filelist)不可用」。

**影响**: `capabilities --json` 是 agent 的工具面真相源，note 过期 = agent 被误导。
**建议**: 修正 4 条 note；并把"note 与实际 `--help` 一致性"纳入 `gen_cli_surface --check` 的扩展。

### B6 🟡 P2 — 已宣布但未执行的合并

`diff compare` 的 note 写着「[计划] 并入 snapshot compare」，但命令仍在（10 个测试引用）。
**建议**: T2 里一并处理。

### B7 🟡 P2 — 零/近零测试覆盖的命令

| 命令 | 测试引用 | 判定 |
|---|---|---|
| `dev expression build/func/cond` | **0** | 内部调试，可降为库函数 |
| `visualize compute` | 1 | 保留价值待确认 |
| `graph dump` | 1 | 与 `graph nodes/edges` 重叠 |
| `visualize timed` | 2 | 同上 |
| `graph find` | 2 | 与 `search` 重叠 |
| `hierarchy` | 3 | ⚠️ 但文档引用 133 次，属"测试少而使用多" |

> 注：测试引用数是粗略指标（按命令名在 `sim/tests/**/*.py` 的出现次数），
> 用于**排序嫌疑**，不作为结论。真实判定要看 §5 的合并语义。

---

## 5. 减法方案

### 5.1 T1 — 零风险（无行为变化，1 个迭代）

| 动作 | 收益 |
|---|---|
| 归档 `_archived*` → `docs/archive/2026-10-19-src-archived/` | **-3,248 行** |
| 删除 `LoadExtractor._get_signal` | **-283 行** |
| 删除空包 `applications/cpu`、`operator`（或补 README） | -2 个空目录 |
| 修正 registry 中 4 条 `graph` 过期 note | agent 不被误导 |
| 删两个孤立模块（`signal_graph_viewer` 895 / `function_expander` 131） | **-1,026 行** |
| 统一导入根（27 处 `from src.*` → 单根） | 消除双份模块对象 |
| 删除 `diff compare`（并入 `snapshot compare`） | -1 个叶子命令 |

合计 **~4,560 行 + 1 个命令**，全部无行为变化（导入根统一需跑全量门禁确认）。

### 5.2 T2 — 合并同族命令（需测试保护，`core` 34 → ~26）

| 族 | 现状 | 建议 | 节省 |
|---|---|---|---|
| `graph` | `nodes` / `edges` / `dump` / `find` | `graph nodes` + `graph edges` + `graph export`(dump)；`find` 并入 `search --graph` | 4 → 2 |
| `diagnose` | `imports` / `report` / `timescale` / `widths` | `diagnose <kind>`（kind 为参数） | 4 → 1 |
| `class` | `class` / `classes` | `class` + `--list` | 2 → 1 |
| `controlflow` | `analyze` / `conditions` / `list-conditioned` | `list-conditioned` → `analyze --all` | 3 → 2 |
| `snapshot` | `list` / `save` / `show` / `delete` / `compare` | `show` 并入 `list --json --tag` | 5 → 4 |
| `dev` | `expression build` / `cond` / `func` | 合成 `expression --what` 或直接移出 CLI | 3 → 1 |
| **小计** | **34 → 8** | | **21 → 26 → 净 -8** |

`view` 层 13 → ~9：

| 族 | 现状 | 建议 |
|---|---|---|
| 叙述类 | `arch show` / `design show` / `trace overview` | `show <arch|design|overview>`（3→1） |
| 可视化 | `chain` / `compute` / `dataflow` / `datapath` / `gap` / `graph` / `module` / `pipeline` / `teach` / `timed` | `compute`/`timed` 降级进 `exp`（2a 时按使用度定去留） |

`exp` 层 24 条**不动**（已降级、需 `--include-exp` 才可见），但 **24 个老路径别名**应在下个
minor 移除（`protocol detect` 等 → 只保留 `exp protocol detect`）。

### 5.3 T3 — 结构性（需方豆拍板，与 2a 排期协调）

| # | 动作 | 收益 | 成本/风险 |
|---|---|---|---|
| T3-1 | `UnifiedTracer` 按领域拆查询门面 | 单点改动影响面下降 | 触及所有 CLI 命令；建议 2a 之后 |
| T3-2 | `cli/_output.py` 统一输出层 | 加字段只改 1 处 | 6 处 helper 收敛；需改 6 个命令模块 |
| T3-3 | 拆 `visualize.py`（2,376）与 `semantic/trace.py`（1,840） | 单文件可读 | 纯搬运，可用"CLI 表面指纹不变"证明（同 iter_232/233 手法） |
| T3-4 | 拆 `elk_bridge.expr_trees_to_elk`（908） | 可视化可测 | 涉及渲染回归，需 SVG 断言 |

---

## 6. 分层建议（"功能分层"而不只是删）

现在的层是**按承诺等级**分的（core/view/exp/dev），这是对的。缺的是**按问题类型**分的视图：

| 问题类型 | 应去哪一层 | 现状 |
|---|---|---|
| "这个信号谁驱动" | `core` | ✅ drivers/loads |
| "这个模块长什么样" | `core`（机器） + `view`（人眼） | ✅ hierarchy vs arch show |
| "这个工程有什么问题" | `core/diagnose` | ✅ 但 4 个命令太碎 |
| "给我一张图" | `view` | ✅ 10 个命令太碎 |
| "帮我改文件" | **`tools/`（不在 CLI）** | ✅ 已移出 |
| "时序/CDC/总线协议" | `exp` | ✅ 已降级 |

**建议补一条分层规则**（写进 `check_cli_layers.py`）：
> **同一层内，若两个命令的输入参数可由一个参数选择（枚举）表达，且输出 schema 同构，
> 则应为 1 个命令 + 参数，而不是 2 个命令。**

这条规则能机械地挡住"每加一个变体就加一个命令"的膨胀路径。

---

## 7. 不做的事（明确排除）

| 不做 | 理由 |
|---|---|
| 拆仓 / 拆子项目 | 方豆已拍板不拆 |
| 动 RTL 或用户工程 | 产品不变量 I1 |
| 删除 `exp` 命令本身 | 已降级，删了会丢能力展示；只到期删别名 |
| 现在做 T3 全部 | 与 2a（人眼可视化）冲突；T3-3 应等 2a 定稿后再动 visualize |
| 按测试引用数直接删命令 | 引用数只用于排序嫌疑，删除必须逐个确认语义重叠 |

---

## 8. 建议执行顺序

| 步骤 | 内容 | 验收 |
|---|---|---|
| **1** | T1（归档 + 删死方法 + 修 note + 删 diff compare） | 全量门禁不变；`src` -3.5k 行 |
| **2** | B4 统一输出层（T3-2 提前，因为它让后续合并变便宜） | 6 个命令模块改用统一 emit；输出字节不变 |
| **3** | T2 core 合并（graph → diagnose → class → controlflow → snapshot → dev） | 每合并一族跑一次全量；`capabilities` 数下降 |
| **4** | 2a 人眼可视化（view 层 13 → 9 在此定稿） | SVG 断言 + 使用度数据 |
| **5** | T3-1/T3-3/T3-4（拆分与门面重组） | 逐项做，每项独立 commit |

---

## 附：本次使用的测量口径

```bash
# 规模
find src -name '*.py' -not -path '*__pycache__*' -exec cat {} + | wc -l

# 函数长度 / 裸异常 / 重复定义: AST 扫描 (ast.FunctionDef.end_lineno / ExceptHandler.type)
# 导入图: ast.ImportFrom/Import → 判定死模块与反向依赖
# 命令盘点: PYTHONPATH=src python3 -c "from cli._registry import COMMANDS, ALIASES"
# 使用度: 命令名在 sim/tests/**/*.py 与 docs/**/*.md 的出现次数 (粗略排序用)
# 真实探测: python3 run_cli.py graph nodes --filelist sim/tests/fixtures/scheduler_minimal/filelist.f --json
```
