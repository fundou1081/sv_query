# 抽象层设计评审 — 现状与未来变化适配力

> **文档版本**: v1.0（初稿）
> **评审时间**: 2026-11-16 21:31 CST (GMT+8)
> **评审对象版本**: git HEAD `2ddcfe92`（`docs: revise agent interface review; archive v1; register P182`）。评审时 worktree 有未提交改动：`docs/INDEX.md` 与 `code_architecture_review_2026-11-16.md`，均为文档类，不影响代码基线
> **同系列文档**: [agent_interface_review_2026-11-16_revised.md](agent_interface_review_2026-11-16_revised.md)（交付层 v2，基于 `8da675b3`，建议已登记 PLAN P182）；[code_architecture_review_2026-11-16.md](code_architecture_review_2026-11-16.md)（实现层 v1.0，基于 `2ddcfe92`）
> **方式**: 只读静态代码审查 + 关键片段人工抽查；**未运行测试、未运行门禁、未编译 SV、未修改任何代码**
> **状态**: 讨论底稿 / 建议稿。**不是** PLAN 项、**不并入 P182**、**不是**已批准任务、**不是**契约。

---

## 0. 给后续 agent 的阅读须知

1. 本文只看**抽象层设计本身**（边界、接口、扩展点）与**对未来变化的承接力**。交付层的 envelope/schema/入口、实现层的异常/状态/原子写，分别由同系列另两份文档覆盖，本文不重复。
2. 编号 `Ab-*` **仅供本文索引**，与 PLAN 的 `P*`、同系列的 `R-*`/`Rb-*`/`St-*` 无关，也不是待办列表。采纳前须按 `AGENTS.md §2` 单独登记 PLAN、置 current item、建任务文档。
3. 标注：`【事实】` = 代码可直接核实（附路径行号）；`【判断】` = 评审推断；`【建议】` = 未采纳候选。
4. **时点性**：所有【事实】绑定 `2ddcfe92`。数字（140 个源文件、18 个 import pyslang、33 个引用 EdgeKind 等）是 2026-11-16 静态统计，会漂移；用 §9 命令复核，不要凭本文记忆改代码。
5. 本文**不裁决方向**。关于常驻服务/方案 C 存在三种口径（`arch_eval_2026-11-11.md:122` 推荐、`PLAN.md:514` 暂缓、交付层 v2 §P2 不直接上 serve）；本文只评估抽象层是否为它预留接缝，不主张启动或否决。
6. 权威源仍是 [PLAN.md](../../PLAN.md)、[SEMANTIC_CONTRACTS](../dev/SEMANTIC_CONTRACTS.md)、`capabilities --json` 与 [INDEX](../INDEX.md)。本文与代码冲突时，以代码为准。

---

## 1. 一句话结论

> 这个项目有**分层的目录**和**声明式的契约**，但几乎没有**可替换的抽象**。
> 真正承担抽象职责的三处（`_registry.py` 命令表、`graph/contracts.py` edge 策略、`Stage`/`PipelineStep` DAG）全是**描述性数据**，不驱动运行时行为；运行时由具体类直连串起。
> 于是每次变化都被"兼容层"吸收——把新东西伪装成旧接口，让上层零改动，代价是 pyslang 的具体形状渗透全栈。**当前抽象保护的是调用点，不是概念**。

补充【判断】：对未来而言，风险不在"能不能加一个命令"（这条有 R1/R4 门禁），而在**换 AST 前端、换会话形态、图模型升版本、只读边界松动**这四条轴上没有任何 seam，且破坏大多是**静默**的（缺边但 rc=0、控制边被当数据边、文档与代码各自漂移）。

---

## 2. 评审范围与三轮分工

| 轮次 | 文档 | 视角 | 本文是否重复 |
|---|---|---|---|
| 1 | `agent_interface_review_2026-11-16_revised.md` (v2) | 交付层：契约 / 信封 / 入口 / 会话 | 否，只在 §5/§7 引用其结论 |
| 2 | `code_architecture_review_2026-11-16.md` (v1.0) | 实现层：鲁棒性 / 结构性 | 否，Ab-04/Ab-06 只补"演进维度"的论证 |
| 3 | **本文** | 抽象层：边界 / 接口 / 扩展点 / 变化轴 | — |

抽查范围：`src/cli/{_entry,main,_registry,_output,_common}.py`、`src/cli/core/semantic/{verify,trace_common,params}.py`、`src/sv_query/{__init__.py,trace/__init__.py}`、`trace/unified_tracer.py`、`trace/core/{pipeline.py,graph_builder.py,semantic_adapter.py,compiler.py,native_adapter.py,ast_utils.py,_safe.py}`、`core/builder/graph_pipeline.py`、`core/semantic/{_wrappers,_expr_helpers,__init__}.py`、`core/graph/{models,contracts}.py`、`core/cache/ast_cache.py`、`tools/{gen_cli_surface,check_cli_layers,scan_pyslang_attrs}.py`、`pyproject.toml`、产品方向/AI_REQUIREMENTS/SNAPSHOT_SURFACE/SV_SYNTAX_ROADMAP 等治理文档。

---

## 3. 当前抽象层的实际形态

【事实】从入口向下共约 9 层，**绝大多数没有显式接口**，靠"直接 import 具体类 + 直接调用"串联：

| 层 | 核心类型 | 接口形态 |
|---|---|---|
| 入口 | `main()` / `run()` / `app` (`cli/_entry.py:23-35`, `cli/main.py:413-434`) | 无 |
| 命令分发 | `typer.Typer` (`cli/main.py:78-131`) | **手写 30+ 条** `app.command(...)(fn)` |
| 注册表 | `CommandSpec` / `COMMANDS` / `LAYERS` (`cli/_registry.py:89-136`) | `@dataclass(frozen=True)` 数据，只被校验器/生成器消费 |
| 命令实现 | 各 `*_cmd` + `emit_json`/`fail` | 统一的是函数，不是契约类型 |
| 编排 facade | `UnifiedTracer` (`unified_tracer.py:300-368`) | 无，`new` 具体类 |
| 查询器 | `SignalTracer` / `ModuleTracer` / `LoadTracer` … (`core/query/*`) | 无，`__init__.py` 只做再导出 |
| 构建 stage | `Stage` (`builder/graph_pipeline.py:36-48`) / `PipelineStep` (`core/pipeline.py:39-53`) | **最接近显式契约**：`requires/provides` 拓扑排序 |
| 语义适配 | `SemanticAdapter`（6 mixin）(`semantic_adapter.py:61-68`) | 无 ABC/Protocol，纯 mixin 组合 |
| AST 前端 | `SVCompiler` / `pyslang.Compilation` (`compiler.py:367,677`) | 无；`trace/__init__.py:21-38` 给 pyslang 打 PEP 562 猴子补丁 |
| 图模型 | `SignalGraph(nx.DiGraph)` / `TraceNode` / `TraceEdge` (`graph/models.py:112,198,224`) | 继承**具体** networkx 容器 |

【事实】全 `src/` 约 140 个 `.py`：`typing.Protocol` **1 处**（`core/extractors/_common.py:62`，无 `runtime_checkable`、无任何 `isinstance` 校验），`ABC`/`abstractmethod` **0 处**。构造注入确实存在，但注解绑死具体类（`graph_builder.py:34 adapter: SemanticAdapter`）或退化为 `object | None`（`query/signal.py:30`）。全项目 grep 无 `plugin/hook/event/strategy/entry_points/register_stage`；唯一 duck-typing seam 是 `graph_builder.py:55` 的 `hasattr(ext, 'set_target_module')`。

---

## 4. 好的设计（抽象层视角）

1. **声明式 DAG 是唯一真正有"扩展点"形态的一层**。`Stage`/`PipelineStep` 用 `requires/provides` 拓扑排序，非法依赖立即 `ValueError`，新增 pass 有明确插入点（`graph_builder.py:66-177`）。虽然两套并存、`run()` 不传 ctx，但"把顺序从代码里搬到数据里"的方向是对的。
2. **把领域规则数据化**。`graph/contracts.py:1-31` 把 edge 三/四类分类做成 frozenset 常量并明确"消费者不得自己写 `edge.kind in (...)`"，还配 mutation 测试。这是"抽象 = 一份可引用的规则"的正确直觉。
3. **抽象元数据运行时可查询**。`capabilities --json` 从 `_registry.py` 单一命令表导出 39 core / 6 exp 的 `mode/cost/recommended/envelope/write_scope`，`tools/gen_cli_surface.py` 由注册表生成 `docs/CLI_SURFACE.md` 并支持 `--check`。"单一源生成"在这里已经有可复用的样板。
4. **显式声明"哪一层保证什么"**。`docs/dev/SNAPSHOT_SURFACE.md` 是字段级矩阵（哪些字段 ✅ / 🔁重算 / ❌不保证）+ 命令级矩阵 + 维护规则，并配往返测试。这类文档是真正面向演进的抽象说明，而非使用说明。
5. **能力边界用结构约束固化**。`check_cli_layers.py` R3 是**零基线**（CLI 内任何写文件立即失败），配 `test_cli_readonly_guarantee.py` 的目录树逐字节指纹比对。比"约定不改 RTL"强得多。
6. **留了一处"换执行后端"的接缝**。`tools/agent/svq-query-tool/neighborhood.js:5-14` 把 `queryFn(args)` 作为纯函数参数注入；`arch_eval_2026-11-11.md:116-122` 据此判断常驻服务迁移难度"低"。这是全项目唯一为传输形态变化预留的 seam（可惜在 JS 侧，Python core 没有对应物）。
7. **有意识地给兼容成本封顶**。`docs/PYSLANG_V11.md:24-33,121-127` 记录 D5 决策：只支持 v11、删掉 232 行 compat shim、明令"不要再建 v9/v10 兼容层"。避免抽象层为兼容历史无限膨胀，是成熟判断（代价见 §5 A2）。

---

## 5. 不好的设计（抽象层视角）

> 以下每条都刻意避开"接口层契约没被保证""实现层异常被吞"这两类已覆盖结论，聚焦**边界与可替换性**。

**A1｜抽象层≈0 个显式接口。**【事实】见 §3：1 个无校验 Protocol、0 个 ABC。上层直接 import 具体实现的例子：`cli/main.py:46-73`（20+ 条）、`cli/_common.py:24-26`（`UnifiedTracer`）、`unified_tracer.py:59-76`（`GraphBuilder`/`SVCompiler`/`SemanticAdapter`）、`graph_builder.py:52-58`（硬编码 `self._extractors` dict）。【判断】这意味着"换实现"没有可编译/可测试的目标类型，所有替换都只能靠全文搜索。

**A2｜兼容层冒充抽象层，保护调用点而非概念。**【事实】`core/semantic/_wrappers.py:42` `self.type = type("TypeToken", (), {"value": ...})()`、`:46` 伪造 `.instances`、`:85-100` 伪造 `parent.header.name.rawText`——把 pyslang `InstanceSymbol` 伪装成**旧 SyntaxTree 接口**以迁就 GraphBuilder；`native_adapter.py:326-354` 是第二套 "API-compatible" wrapper；`semantic_adapter.py:110-127` 保留 `parser/trees/items/visit` 假兼容面；`trace/__init__.py:21-38` 给第三方模块装 `__getattr__` 维持 `pyslang.X` 顶层写法。【事实】`docs/PYSLANG_SEMANTIC_USAGE.md:271-295` 记录这种做法的战绩是"5 个生产调用方零改动"。【判断】正是这种成功让前端形状渗透：`core/semantic/` 8 文件合计约 268 次 `getattr`、95 次 `hasattr`、182 次 `str()`；`_expr_helpers.py` 单文件 22 个去重 pyslang 属性名；`exprs_drivers.py:805-840` 是 16 分支 `if "NamedValue" in kind_str` 字符串分派。`_safe.py:87-101` 把"属性不存在"静默降级为 `default`，`test_safe.py:97` 把该降级锁成预期行为。**兼容层与抽象层的区别**：前者让上层无需改变，后者让上层无需知道。

**A3｜领域模型层退化，承上启下的一环最弱。**【事实】`SignalGraph` 继承具体 `nx.DiGraph`；节点 id 是点分字符串并靠 `models.py:388-399` 的 `split(".", 1)` 反解 module/name；`EdgeKind` 在图模型是 Enum、CLI 变 `.name` 字符串、再被 `== "REG"/"CLOCK"` 比较（`trace_common.py:105-111`）；同一 `TraceNode → dict` 有 3 套字段集互不相同（`models.py:574-665`、`query/subgraph.py:106-141`、`cli/core/semantic/trace_common.py:745-794`）。【判断】没有"领域对象 → 输出 DTO"的唯一映射，于是每一层都自己解释一遍 signal/edge/scope，新增字段或输出形态必须穿透所有层。

**A4｜五个"唯一真相源"全是声明性的，不是执行性的。**

| 声明源 | 声明 | 实际执行 | 证据 |
|---|---|---|---|
| `COMMANDS`/`CommandSpec` | 命令清单 | `main.py:85-131` 手写注册，注册表只被 R1 事后校验 | `cli/_registry.py:136` vs `cli/main.py:90-98` |
| `graph/contracts.py` | edge 分类唯一策略 | 33 文件引用 `EdgeKind`，`dataflow.py:447-824` 等仍 `kind.name == "DRIVER"` | `contracts.py:9-12` 的自述 |
| `write_scope` | 能力边界 | 全 `src/` 无运行时读取，仅 `capabilities` 输出 + 1 个回归断言 | `_registry.py:101,388-393,1539` |
| `JSON_CONTRACT` | 输出字段 + bump policy | 无 validator 消费，无 `required/properties` | `_registry.py:351-359` |
| `SNAPSHOT_SURFACE.md` | 快照字段矩阵 | `to_dict/from_dict` 两处手工白名单对称维护 | `models.py:602-673,701-787` |

【判断】gate 能检查"声明与代码是否一致"，但不能让声明成为执行；所以任何演进都仍要人肉同步 N 处。【事实】补充一例：`tools/gen_cli_surface.py:35-89` 的 `collect()` 同时依赖注册表**与 typer/click 运行时 introspection**，因此"由注册表生成文档"并非纯静态——评审时在裸 `python3` 下 `gen_cli_surface.py --check` 因 `ModuleNotFoundError: No module named 'click'` 直接失败（环境缺依赖，不是契约漂移）。

**A5｜扩展机制 = 改源码列表 + 改硬编码集合 + 事后静态校验。**【事实】`_registry.py:285-296` 四个硬编码集合决定 `mode_of()`；`verify.py:611-621` 是 `if/elif/else` 链且错误字符串里再写一遍类型清单；`native_adapter.py:218-233` 是顺序敏感的 `elif 'GenerateBlock' in kind` 链（注释明说 `InstanceArray` 必须在 `Instance` 前）；`graph_builder.py:66-177` 与 `unified_tracer.py:338-352` 是两个硬编码 Stage 列表，无 `register_stage()`。【判断】"新增能力"始终是一次散弹式改动，而不是一次注册。

**A6｜进程级全局态 + 单一 entry point 阻碍库化。**【事实】`cli/main.py:34` 在 **import 期**改写 `sys.argv`；`compiler.py:19-46` 模块级 `_QUIET`、`signal_classifier.py:89-98` `_ACTIVE_CONFIG`、`ast_cache.py:518-527` 全局缓存单例；`src/sv_query/__init__.py` 只有 docstring、`src/cli/__init__.py:5` `__all__ = []`；`pyproject.toml:62-72` 只有一个 console script，无 `serve/batch/session`。【事实】`product_direction_2026-10-31.md:170` 自认"rtl_typo_checker 目前没有依赖 sv_query；'以 sv_query 为基底'是未来目标，不是已实现事实"。【判断】这不是"缺一个 MCP server"，而是**缺一个可被 import 的库 API**；没有它，所有传输形态变化都要改 `run()` 这一处。

**A7｜分层边界被跨层直连打穿。**【事实】`cli/core/diagnose/widths.py:29` 直接 `import pyslang` 并调用 `pyslang.SVInt/clog2`；18 个文件 `import pyslang`、约 28 个文件含具体类型/属性名；`compiler.py:52-54` 与 `semantic_adapter.py:52-54` 逐字重复同一段本机 bindings 绝对路径注入。【判断】"CLI 不碰引擎内部"在 import 方向检查（R2）下成立，在概念依赖上不成立。

**A8｜变化轴错配 + 真相源漂移。**【事实】机械保护集中在"加命令/加语法"；而 `SV_SYNTAX_ROADMAP.md:32-88` 标 Interface/Modport/Class 继承"未开始"，代码里 `models.py:214` 已有 `modport_dir`、`semantic/ports_ifaces.py:41-90` 已有 modport 抽取、`class_hierarchy.py` 已有继承链；`graph_builder.py:65` 注释写"12 个 pass"，实际 17 个。同一"方案 C"在 `arch_eval_2026-11-11.md:122`（推荐）、`PLAN.md:514`（暂缓）、交付层 v2 §P2（不直接上 serve）三处口径不同。【判断】演进启动前的第一项成本，是裁决哪份文档是当前真相。

---

## 6. 未来变化适配力评估（变化轴 × 承接力）

| # | 变化轴 | 现有保护 | 承接力 | 主要破坏形态 | 关键证据 |
|---|---|---|---|---|---|
| 1 | 新增 core 命令 / 输出视图 | R1、R4、`gen_cli_surface.py --check` | **中** | 登记不会漏，但 `AGENT_FEATURE_MAP.md`、`SKILL.md`、`llm_schema.json`、`CLAIMS.md` 靠字符串断言与人工 → agent 文档漂移 | `_registry.py:136,285,351`；`gen_cli_surface.py:166-204` |
| 2 | 新增 claim type | `test_verify.py` | **弱** | 改 `if/elif` 链 + 错误字符串 + `_verify_*` + 4 份文档/schema | `verify.py:608-621` |
| 3 | 新增 SV 语言特性 | 无按特性组织的 Stage | **弱** | 穿透 `semantic/` 6 域 + `extractors/` + `graph_builder.py` + `models/contracts` + 4 份特性清单 | `graph_builder.py:66-177`；`extractors/__init__.py:2-13` |
| 4 | 升级 / 更换 AST 前端 | v11 alias bridge、`scan_pyslang_attrs.py`、v11 smoke 测试 | **弱** | 属性改名 → `safe_attr` 静默 `default` → 缺边/缺节点但 rc=0；且 D5 明令禁止再建 compat 层 | `_safe.py:87-101`；`PYSLANG_V11.md:121-127`；`pyproject.toml:44-45` |
| 5 | 图模型 / 快照格式升版本 | `"version": "1.0"`、`SNAPSHOT_SURFACE.md`、往返测试 | **弱** | 未知 `EdgeKind` 静默回退 `DRIVER`，旧引擎读新快照把控制边当数据边；`to_dict/from_dict` 手工对称；`-v17` 与 `CACHE_VERSION="2.0"` 两套版本 | `models.py:579,690-692,746-752`；`unified_tracer.py:218`；`ast_cache.py:63` |
| 6 | 会话 / 传输形态（MCP、常驻、批量、流式） | JS 侧 `queryFn` 注入 | **无**（Python 侧） | `sys.argv` 改写 + `_QUIET`/`_ACTIVE_CONFIG`/缓存单例污染多请求；无 library API 可复用 | `main.py:34,413-434`；`src/sv_query/__init__.py`；`pyproject.toml:62-72` |
| 7 | 规模策略（增量 / 并行 / 多设计） | `ASTCache`、`compute_project_key()` | **弱** | `build_graph` 只有 `_graph is None or force` 二值状态；缓存命中不恢复 MIG/PathResolver；非原子 gzip 写；两套版本手工同步 | `unified_tracer.py:300-332`；`ast_cache.py:157-196,421-422` |
| 8 | 只读边界松动（写入 / 仿真联动 / 以本库为基底） | R3 零基线 + 指纹测试 | **约束强、演进承接弱** | 放进 `src/cli/**` 会被 R3 立即拦下；放 `tools/` 则失去 `capabilities`/`JSON_CONTRACT` 契约；`write_scope` 不提供运行时授权 | `check_cli_layers.py:264-274,339-357`；`_registry.py:101` |

【判断】8 条轴里只有 #1、#8 有较强机械保护，且 #8 是"拦得住"而不是"接得住"。**破坏性最大的四条（#4/#5/#6/#7）恰好都是静默的**：不会红 gate，只会产出看似合法的结果或让演进无从下手。项目自己刚把契约执行相关补课登记为 P182.1~P182.6 全组 `<待做>`，与本文结论一致。

---

## 7. 改善方案（现状 → 问题 → 建议 → 代价）

> 全部为【建议】候选，未采纳、未登记 PLAN。与 P182 的关系逐条标注。

**Ab-01（P0）把"声明源"升级为"执行源"的一个垂直切片**
现状：五个唯一真相源都只声明不执行（§5 A4）。问题：后续所有演进都需要"机器可校验的契约"作为回归基线，现在没有可复制的样板。建议：选一个窄切片（推荐 `verify claim`：把 `typ` 分派改成数据表驱动、由 `JSON_CONTRACT` 生成该命令真 JSON Schema、gate 用同一份校验成功/失败/截断三种输出、`write_scope` 在执行路径上被读取），证明"单一源既声明又执行"可行。**与 P182.1/P182.2 是同一方向的实现层落地形态，不新增 PLAN 项**。代价：局部重构 + 可能触发 schema bump；收益：Ab-02~06 都获得可验证的回归基线。

**Ab-02（P0/P1）在 CLI 与引擎之间定义一层真正的领域 seam**
现状：CLI 直接拿 `nx.DiGraph` 与裸 dict，同一概念 3 种形状（§5 A3）。建议：定义 `DesignView` Protocol（`resolve_signal` / `drivers_of` / `edges_of` / `node_view`），把 `NodeId`/`HierPath`/`EdgeKind` 值对象化，DTO 映射由 dataclass 单一函数生成；新命令先走新 seam，旧命令按命令族迁移。代价：全栈改造，不能一次完成，需兼容期；收益：新增字段/边类型/输出形态只改一处，换前端不必改 CLI。

**Ab-03（P1）把"兼容层"换成"前端接口"**
现状：18 文件 import pyslang、22 个属性名散落、16 分支 kind 字符串、静默降级（§5 A2）。建议：定义 `ASTFrontend` Protocol（`instances` / `expr_kind` / `symbol_of` / `drivers_in` / `diagnostics`），把全部 pyslang 属性名与 kind 字符串收进唯一一个 `pyslang_v11.py`；`safe_attr` 的 default 降级改为可计数 `degraded`；把现有 `scan_pyslang_attrs.py` 升级为 gate（白名单外不得出现 pyslang 属性名）。**与 D5 不冲突**：不是兼容多版本，而是隔离单一版本。代价：一次性约 28~35 文件，可用扫描器分批；收益：v12 升级只改一个文件，且不再静默缺边。

**Ab-04（P1）让 Stage 成为真扩展点**
现状：两套 Stage 契约、`run()` 不传 ctx、`requires/provides` 只保顺序、17 个 pass 硬编码列表（§5 A5）。建议：合并为一套 `Stage.run(ctx) -> ctx`，产物通过 context token 声明并校验数据依赖，提供 `register_stage()`；语言特性落点从"改多个 pass"变成"注册一个 extractor + 一个 stage"。**这是 P182.6「合并两套 DAG」与上一轮 St-02 在抽象层的具体形态**。代价：改动面大，建议一次一个 pass；收益：新增 SV 特性可隔离验证。

**Ab-05（P1）库化接缝，但不实现服务**
现状：`run()` 绑死 `sys.argv → Typer → stdout`，无公开 API，进程级全局态（§5 A6）。建议：抽 `Session.execute(request: dict) -> response: dict` 纯函数，`run()` 降为它的 CLI adapter；`sys.argv` 改写、`_QUIET`、`_ACTIVE_CONFIG` 改为显式 `RequestContext`/`BuildOptions`；`src/sv_query/__init__.py` 导出 `Session`。**不实现 serve/MCP/batch**，不违背 `PLAN.md:514` 对方案 C 的暂缓；只是把"换传输"从改核心变成加 adapter。代价：中等，需处理 Typer 与纯函数边界；收益：同时解锁 #6 与"以 sv_query 为基底"，成本远低于直接上常驻服务。

**Ab-06（P1）图模型版本化契约**
现状：`to_dict` 硬编码 `"1.0"`、`from_dict` 不读版本、未知 kind 静默回退（§5 A4/#5）。建议：单一 `GRAPH_SCHEMA_VERSION` 常量同时派生序列化字段与缓存 key；`to_dict/from_dict` 由 dataclass 生成；未知 `NodeKind`/`EdgeKind` 显式失败或走显式 migration；`SNAPSHOT_SURFACE.md` 的字段矩阵由代码生成。**与上一轮 St-01 是同一问题的"版本演进维度"**。代价：旧快照需重建；收益：新增边类型不再静默误判，也不会撞上旧缓存。

**Ab-07（P2）把"变化轴"纳入治理**
现状：roadmap 已漂移、注释计数过期、方案 C 三处口径不一致（§5 A8）。建议：把 §6 矩阵固化为一份短清单（每条轴：seam / 保护 gate / 承接力 / 真相文档），版本 bump 或新增能力时强制更新；`SV_SYNTAX_ROADMAP.md` 由 `EXTRACTION_COVERAGE.md` + 代码生成或纳入 gate；把"讨论底稿 vs 已登记计划"的裁决写进 PLAN。代价：文档维护；收益：演进启动时不必先花半天裁决哪份文档是真相。

---

## 8. 优先级主张

推荐顺序：**Ab-01**（先证明契约可执行）→ **Ab-05 与 Ab-02 并行**（都不破坏现有 CLI 输出形状：一个纯新增接缝、一个按命令族渐进迁移）→ **Ab-03 / Ab-04 / Ab-06**（结构性，一次收口一个可验证单元）→ **Ab-07**。

**如果只做一件：Ab-01 的垂直切片。**【判断】这个项目最强的能力是声明式治理，最缺的是让声明成为执行；Ab-03/04/06 这类跨层大改若没有机器可校验的契约基线，就无法证明"没破坏语义"，而 P182.1/P182.2 正好在补这条基线。若允许两件，加 **Ab-05**：它是成本最低、解锁最多未来变化轴（#6、#7、#8 的库化前提）的一条，且是纯新增、不改任何输出形状。

---

## 9. 复核命令（只读 / 校验，不改文件）

```bash
git rev-parse --short HEAD                                  # 应为 2ddcfe92
grep -rnE '\b(Protocol|ABC|abstractmethod)\b' src --include='*.py' | wc -l
grep -rln 'import pyslang' src --include='*.py' | wc -l    # 评审时 18
grep -c 'Stage(' src/sv_query/trace/core/graph_builder.py # 评审时 17（注释写 12）
grep -n '__all__\|def run' src/sv_query/__init__.py src/cli/__init__.py
grep -n 'version' src/sv_query/trace/core/graph/models.py | head
python3 tools/gen_cli_surface.py --check   # 需项目依赖环境（click/typer 可用）；
                                          # 裸 python3 报 ModuleNotFoundError: click 是环境缺依赖，不是漂移
python3 tools/check_docs.py
```

若数字变化，以代码为准；本文结论中依赖"当前没有 X"的判断需重新核实（例如 Ab-05 若已出现 `Session`，该条即失效）。

---

## 10. 变更记录

| 版本 | 时间 | 变更 |
|---|---|---|
| v1.0 | 2026-11-16 21:31 CST | 初稿。基于 HEAD `2ddcfe92` 的只读评审；抽象层清单、7 条优点、8 条问题、8 条变化轴评估、Ab-01~07 建议、优先级与复核命令。未新增/修改 PLAN 项，未改代码。 |
