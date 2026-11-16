# 代码实现架构审查建议 — 鲁棒性与结构性

> **文档版本**: v1.0（初稿）
> **评审时间**: 2026-11-16 20:59 CST (GMT+8)
> **评审对象版本**: git HEAD `2ddcfe92`（`docs: revise agent interface review; archive v1; register P182`）；v1 交付层评审基于 `2a004f76`，修订版 v2 基于 `8da675b3`，两轮之间代码有 P181 提交
> **相关文档**: [agent_interface_review_2026-11-16_revised.md](agent_interface_review_2026-11-16_revised.md)（交付层 v2，建议已登记 PLAN P182）；v1 原文已归档，只作时点记录
> **方式**: 只读静态代码审查（含关键片段人工抽查）；**未运行测试、未运行门禁、未编译 SV、未修改任何代码**
> **状态**: 讨论底稿 / 建议稿。**不是** PLAN 项、**不并入 P182**、**不是**已批准任务、**不是**契约。

---

## 0. 给后续 agent 的阅读须知

1. 本文只看**代码实现层**的鲁棒性与结构性，不重复交付层 v2 已覆盖的 envelope / schema / 入口 / 会话议题，也不新增或修改 PLAN 的 `P182.*`。
2. 编号 `Rb-*` / `St-*` **仅供本文索引**，与 PLAN 的 `P*` 无关，也不是待办列表。采纳前须按 `AGENTS.md §2` 单独登记 PLAN、置 current item、建任务文档。
3. 标注：`【事实】` = 代码可直接核实（附路径行号）；`【判断】` = 评审推断；`【建议】` = 未采纳候选。
4. **时点性**：所有【事实】绑定 `2ddcfe92`。数字（217 处宽捕获、31 处硬编码、394 测试文件等）是 2026-11-16 静态统计，会漂移；用 §6 命令复核，不要凭本文记忆改代码。
5. 权威源仍是 [PLAN.md](../../PLAN.md)、[SEMANTIC_CONTRACTS](../dev/SEMANTIC_CONTRACTS.md)、`capabilities --json` 与 [INDEX](../INDEX.md)。本文与代码冲突时，以代码为准。

---

## 1. 一句话结论

> 交付层的问题是「契约没被机器保证」；**实现层的问题是「失败没被结构化地表示」**。
> 项目把大量纪律投在语义正确性上，但 217 处宽异常捕获、无事务的构建状态、无上界的图遍历与递归，
> 使「内部失败」与「客观事实」在输出层仍可能混在一起——这会抵消 P182 想修的 envelope 契约：
> 再整齐的信封，也只是把假事实包装得更好看。

补充【判断】：P182.1（envelope 统一）与 P182.3（完整性联动）要真正生效，前置条件是实现层能把"失败"作为一等状态传出来。因此本轮建议 Rb-01 / Rb-02 的优先级高于继续扩充 gate 数量。

---

## 2. 审查范围

| 层 | 抽查文件 |
|---|---|
| 构建/状态 | `unified_tracer.py`（build_graph / _step_* / load_snapshot / _init_tracers / stats）、`core/pipeline.py`、`core/builder/graph_pipeline.py`、`core/graph_builder.py` |
| 图模型/数据 | `core/graph/models.py`（dataclass / to_dict / from_dict / find_all_paths / detect_cycles）、`core/graph/contracts.py`、`core/graph/search_budget.py`、`core/graph/dataflow.py` |
| 语义兼容层 | `trace/_safe.py`、`core/semantic/_wrappers.py`、`core/semantic/_expr_helpers.py`、`core/semantic_adapter.py`（6 mixin）、`core/compiler.py` |
| 缓存/快照 | `core/cache/ast_cache.py`、`core/snapshot_manager.py` |
| 输入/边界 | `core/filelist.py`、`core/sv_preprocessor.py`、`core/bit_select_handler.py`、`core/extractors/expr_tree_builder.py`、`core/query/signal.py`、`core/class_hierarchy.py` |
| CLI 失败路径 | `cli/main.py`（run）、`cli/_common.py`（_build_tracer / prune fallback）、`cli/errors.py`、`cli/_output.py` |
| 测试 | `sim/tests/`（unit / regression / cli / integration 组织与覆盖形态） |

---

## 3. 鲁棒性：现状事实

| # | 事实 | 证据 |
|---|---|---|
| F-R1 | `src/` 下 `except Exception` 约 217 处 / 60 文件；`warnings` 模块 0 使用，日志大量为 `logger.debug`（默认不可见） | 全库静态检索；`driver_extractor.py` 14、`graph_builder.py` 13、`unified_tracer.py` 11 |
| F-R2 | **事实型查询把异常吞成"看起来正常"的空结果**：`find_all_paths` → `[]`、`detect_cycles` → `[]`、`_backfill_source_locations` → `0`（无日志）；`_build_pruned_tracer` 吞**所有**异常后改用全量 filelist 重建 | `graph/models.py:551-561`；`unified_tracer.py:1219-1220`；`cli/_common.py:166-170` |
| F-R3 | `build_graph` 无事务性：`_step_graph` 先写 `self._graph`（`:404`），其后 8 个 step 任一失败 → 再次调用走 `:368` 直接返回半成品，`_signal_tracer is None` → `trace_signal()` `AttributeError`。缓存命中路径（`:328-332`）只恢复 graph + tracers，不恢复 MIG / PathResolver / class 状态；`load_snapshot`（`:450-475`）不重置 `_compiler` / `_adapter` / `_sources` | `unified_tracer.py` 上述行 |
| F-R4 | 顶层 `run()` 只捕获 `(CompilationError, OSError, UnicodeDecodeError)`；`ValueError` / `TypeError` / `RecursionError` 等 → `--json` 下 **stdout 完全空**（traceback 在 stderr）；`main.py:438` 的 `__main__` 直接调 `app()` 而非 `run()`，绕过统一错误格式化 | `cli/main.py:417-438` |
| F-R5 | 递归/遍历无上界：`expr_tree_builder.py:28-94`、`graph/viz/expression_tree.py:136-300`（`:238` 记载 picorv32_pcpi_mul 曾触发 RecursionError）、`builder/subroutine_expander.py:376-509`、`cli/.../condition_analysis.py:86-202` 均无 depth/visited；`class_hierarchy.py:64-79` 的 `get_ancestors` 是 `while` 且**无 visited**，继承成环会 hang（比 RecursionError 更难诊断） | 同上 |
| F-R6 | `SearchBudget` 只有 2 个消费者（`dataflow.py`、`module_instance_graph.py`）；`find_all_paths` / `detect_cycles` / `graph/diff.py` / `analysis/audit.py` / `query/constraint.py` 等仍是裸 `nx.all_simple_paths(cutoff=...)` 或仅 depth | `core/graph/search_budget.py:19-86` 与各消费者 |
| F-R7 | 缓存写盘**非原子、无锁**：`gzip.open(cache_path,"wt")` 直接写最终路径；`get_by_key` 只捕获 `OSError, json.JSONDecodeError`，截断 gzip 的 `EOFError` 与非 UTF-8 的 `UnicodeDecodeError` 会逃逸；缓存 key 是手写 `-v17`，与 `ast_cache.py:63 CACHE_VERSION="2.0"` 两套独立版本，且不含 pyslang 版本 / `preprocess_macros` / `top_modules`；snapshot `save()` 同样非原子写，读取侧无 size guard | `cache/ast_cache.py:393-395,421-430`；`unified_tracer.py:218`；`snapshot_manager.py:165-195` |
| F-R8 | 输入边界不一致：单文件 `-f` 用系统默认编码（`cli/_common.py:100`），filelist 与 compiler 用 `utf-8 + errors="replace"`（静默替换非法字节）；位选 `int()` 失败静默 `return 0`（`bit_select_handler.py:150-173`），`query/signal.py` 有约 10 处裸 `int()`、`(1 << width)` 的 width 无上限、X/Z 字面量静默 `None`；`-f` 误传 filelist 的守卫只扫前 20 行且只拒表达式根 | `cli/_common.py:100,213-222`；`compiler.py:147-203,301-303`；`query/signal.py:425-455` |
| F-R9 | pyslang 兼容层把"属性不存在/API 变更"静默降级：`_safe.py:100` 的 `except (UnicodeDecodeError, TypeError, Exception)` 等价宽捕获并 `return default`；`_wrappers.py` 动态伪造 Token；`_expr_helpers.py` 约 50 处 `getattr` + `or` fallback；且该降级被 `sim/tests/unit/test_safe.py:97` 锁成预期行为 | `trace/_safe.py:87-101`；`core/semantic/_wrappers.py`；`test_safe.py:97` |
| F-R10 | 进程级全局：`_QUIET` 由 CLI 在 import 期改写（`main.py:30` → `compiler.py:35-46`）；`_ELABORATION_INCOMPLETE` 写入后**全项目无消费者**（死代码）；`_check_memory_pressure()` 在 quiet 下直接 return、阈值 1536MB 约为实测峰值 169.2MB 的 9 倍且是构图后事后检测；`compiler.py:377-380` 把 pyslang 三个保护上限放大到 `1024*1024` | `compiler.py:19-46,104-144,374-380`；`QUERY_PERF_2026-11-04.md` |
| F-R11 | 测试缺口：394 个测试文件 / 约 65k 行，但未找到并发/多进程写缓存、损坏 gzip（EOFError/UnicodeDecodeError）、磁盘满、序列化失败、递归深度、超大源码输入、`RecursionError` 的用例；无 `hypothesis` / `@given`；契约测试是固定样本键集合断言 + 4 文件源码正则；mutation 是对 RTL 文本注入故障，不是 Python 实现变异 | `sim/tests/` 全量检索；`test_p158_data_edge_contract.py:121-138`；`test_mutation_faults.py:28` |

> 正面事实（避免误读）：`snapshot_manager.py:191-197` 对损坏 JSON 是**显式 ValueError**；`_list_snapshots()` 把损坏文件转成可见 error entry；`compiler.py:470-491` 有 elaboration error 即抛 `CompilationError`；缓存写失败降级为内存是**有文档约定的优化型降级**且配了 `test_cache_dir_config.py`。问题不在"所有降级都错"，而在**优化型与事实型降级没有区分**。

---

## 4. 鲁棒性：候选建议

> 格式：现状 → 风险（可观察后果）→ 建议 → 代价。全部为【建议】，未采纳、未排期。

**Rb-01 · 把"降级"分级，事实型降级必须输出 unknown**（优先级最高）
- 现状：F-R1 / F-R2；`find_all_paths` 等把异常变成 `[]`，`_build_pruned_tracer` 吞异常后换一条构建路径。
- 风险：agent 看到"无路径 / 无环 / 无来源位置"时，无法区分"客观不存在"与"内部失败"——正好违反产品契约 §4「not_found 只在完整搜索后使用，查询失败是 unknown」。
- 建议：定两条规则——**优化型降级**（缓存不可写、可视化失败）可静默但必须计数；**事实型降级**（图查询、证据、prune）一律返回 `unknown + unknown_kind + degraded[]`，不允许返回空集合。新增检查器扫描 `except Exception: return []/0/None/{}` 模式，命中的地方必须显式登记豁免理由。
- 代价：若干查询返回值与契约要改，可能触发 schema bump；但这是 P182.1 / P182.3 的语义前置。

**Rb-02 · 构建事务化 + 显式 phase**
- 现状：F-R3；`_graph` 在 pipeline 中段就被赋值，缓存/快照路径恢复不完整，无 `is_built` / phase。
- 风险：构建中途失败后对象处于半初始化态且对外可查询；`hydrated`（缺 class/MIG 语义）与 `ready` 共用 `_graph is not None` 一个布尔；`stats()` 未构建时静默 `{}`（`unified_tracer.py:1133-1136`）。
- 建议：pipeline 在局部 context 里组装产物，**全部成功后一次性 commit**；引入 `phase = empty | building | ready | hydrated`，`get_*` 在非 ready 时显式 `unknown`；`load_snapshot` 生成新 tracer（或完整重置所有语义状态）而非原地改旧对象；缓存命中路径要么补齐 MIG/PathResolver，要么明确标 `hydrated` 并让依赖命令返回 unknown。
- 代价：`build_graph` 重构，中等；收益是"非法状态无法表示"（ub-mode / Model the Domain）。

**Rb-03 · 顶层异常兜底，杜绝 --json 下 stdout 空**
- 现状：F-R4。
- 风险：未捕获异常 → 消费者拿到空 stdout + rc≠0，只能去解析 stderr traceback，agent 契约失效。
- 建议：`run()` 追加 `except Exception` 兜底，统一 `emit_json_error(..., error_code="E_INTERNAL")`；`main.py:438` 改调 `run()`；把 `stats` 等命令内部的 `handle_compilation_error` 也收敛到同一出口；`SVQ_DEBUG=1` 时仍可保留 traceback。
- 代价：小，纯 CLI 边界。

**Rb-04 · 遍历有界化，先修"会 hang 的环"**
- 现状：F-R5 / F-R6。
- 风险：损坏/异常的 `_parent_map` 成环 → `get_ancestors` 无限循环（无超时、无输出）；深嵌套表达式 → RecursionError 且 `analyze_condition` 只捕 `_ParseError`；大图无 budget 的遍历可能长时间无响应。
- 建议：优先给 `class_hierarchy.get_ancestors/get_all_descendants/get_depth` 加 `visited`（最小、最高收益）；抽一个 `BoundedTraversal`（visited + depth + work budget + deadline）覆盖递归解析与图遍历，把 `SearchBudget` 推广到 `find_all_paths` / `detect_cycles` / `diff` / `audit`；`RecursionError` 映射为 `unknown_kind="expression_too_deep"`，不要裸抛。
- 代价：中等；配合 Rb-01 的 `truncated/unknown` 输出契约。

**Rb-05 · 缓存/快照写盘原子化 + key 完整性**
- 现状：F-R7。
- 风险：多 agent / CI 并发构图同一工程时可能写出半截 gzip，读侧 `EOFError` 逃逸；改宏/top/引擎版本后可能命中旧图；snapshot 写一半断电留下损坏文件。
- 建议：临时文件 + `os.replace` 原子写（必要时 `fcntl.flock`）；读取异常族补 `EOFError / UnicodeDecodeError / TypeError`；读取侧加 size guard（与写入侧 64MB 对称）；把 `-v17` 与 `CACHE_VERSION` 合成单一版本源，并让 pyslang 版本、包版本、构建选项参与 key。
- 代价：小到中；不动现有内容 hash 的正确性设计。

**Rb-06 · 统一输入边界，让兼容层失灵可见**
- 现状：F-R8 / F-R9；另有 `compiler.py:52-54` 与 `semantic_adapter.py:52-54` 两份相同的本机 bindings 路径注入（已有 `os.path.isdir` 守卫，【判断】风险低，但本机存在本地 slang build 时会优先于 pip 包，造成环境间行为差异）。
- 风险：非法字节被静默替换、位宽解析失败静默取 0、超宽字面量放大内存；pyslang 升级后属性改名 → **静默缺边缺节点但 rc=0**，且现有测试把这种静默锁成预期。
- 建议：收敛为单一 `read_source()`（utf-8 + 显式 `UnicodeDecodeError` + 大小上限）和单一 `parse_int_literal()`（负索引/超宽/X-Z 显式判 `unknown`）；把属性缺失从 `logger.debug` 提升为可计数事件（输出 `degraded[]`），提供 `SVQ_STRICT_API=1` 时 fail-fast；本机 bindings 路径改为显式环境变量覆盖；`test_safe.py` 增加"属性缺失必须可见"的断言而非只断言返回 None。
- 代价：中；与"禁 silent fallback"铁律一致，但需重新界定"哪些属性允许缺失"。

**Rb-07 · 补故障注入与性质测试**
- 现状：F-R11。
- 建议：先做 5 个高价值用例——`SignalGraph.to_dict/from_dict` 往返不变量、并发写同一 cache key、损坏 gzip 缓存、超深表达式、snapshot 超大读取；再考虑 `hypothesis` 做 round-trip 与条件解析等价性。
- 代价：小到中（可选依赖）；把"推断的风险"变成"可观测的红/绿"。

---

## 5. 结构性：现状事实与建议

| # | 事实 | 证据 |
|---|---|---|
| F-S1 | 同一份输出形状有 **4 份无运行时绑定**的定义：`models.py` 的 dataclass + 手写 `to_dict/from_dict` 白名单、`_registry.py` 的 `JSON_CONTRACT`、命令模块约 99 处手写 `"ok":` / 34 处 `"result":` 裸 dict、`tools/llm_schema.json`；`src/cli` 无 `TypedDict`/`pydantic` | `graph/models.py:602-673,701-787`；`cli/core/semantic/*.py` |
| F-S2 | 序列化**显式有损且不对称**：`TraceEdge` 丢 `effective_condition`（重算恢复）/`condition_ast`（显式不保证），`SignalGraph` 丢 `_gen_block_map` / `_gen_iter_map` / `_lifo_priority` / nx 边属性 / `graph._adapter`（`unified_tracer.py:403`）；`from_dict` 对未知 `EdgeKind` **静默回退 `EdgeKind.DRIVER`**（`models.py:747-752`）——旧/新版本快照不兼容时，控制边会被当成数据边 | `graph/models.py:630-673,745-752` |
| F-S3 | `GraphPipeline` 的 `Stage.run: Callable[[], None]` **不传 context**，`requires/provides` 只做拓扑排序，17 个 Stage 靠 `self.graph`（该文件 161 处引用）与成员隐式共享副作用；注释仍写"12 个 pass"；`core/pipeline.py` 的 `PipelineStep` 才是真传 `ctx` | `builder/graph_pipeline.py:36-44,64-104`；`graph_builder.py:66-177,1738,1744` |
| F-S4 | `UnifiedTracer` 约 21 个可变状态（16 声明 + 4 构建期动态 + `graph._adapter`），无 phase；4 个 tracer + `PathResolver` + `DataFlowGraph` **共享同一可变 graph 引用**，且 pipeline 顺序是 `tracers → cond_ops → backfill`（`unified_tracer.py:349-351`），即 tracer 初始化后图仍被原地 `add_trace_node/add_trace_edge`；`DataFlowGraph` 有缓存但只提供手动 `clear_cache()`（`graph/dataflow.py:1138-1142`），图无版本号 | `unified_tracer.py:163-178,411-431,1141-1146`；`graph/dataflow.py:155-180` |
| F-S5 | 重复逻辑：条件解析/化简至少 8 份独立实现；signal 解析 8 个入口、3 套返回形状；`--from-snapshot` 互斥校验 8 处（含同文件两份）；`EdgeKind` 字符串硬编码 31 处 / 12 文件（`graph/dataflow.py` 9 处最多），而契约测试的正则只扫 4 个文件、只匹配一种写法 | `condition_analysis.py` / `subroutine_expander.py` / `source_assignment.py` / `trace_common.py` / `trace_lookup.py`；`test_p158_data_edge_contract.py:121-138` |
| F-S6 | core 层并不"纯"：35 处 `print`、6 处 JSON 序列化、5 处文件写入、2 份逐字相同的 `sys.path` 注入；`SemanticAdapter` 是 6 个 mixin 的空壳（自身 127 行 / mixin 3497 行），并保留 `parser/trees/items` 假 SyntaxTree 兼容面 | `compiler.py` / `graph_builder.py` / `sv_preprocessor.py`；`semantic_adapter.py:61-68,106-127` |
| F-S7 | 扩展成本：新增一个查询命令至少触及 7~8 个既有文件；新增一种 `EdgeKind` 触及 6 类位置 / 约 249 处引用 / 34 文件；`gen_cli_surface.py` 既是生成器又是 `--check` 文本比对器 | `main.py` / `_registry.py` / `CLI_SURFACE.md` / `AGENT_FEATURE_MAP.md` / `SKILL.md` / 测试 / `tools/llm_schema.json` |

**St-01 · 数据形状单一化，先修反序列化回退**（优先级最高）
- 现状：F-S1 / F-S2。
- 风险：字段重命名要手工同步 6 处且不会在 import 期报错；`from_dict` 把未知边类型静默变成 `DRIVER`，直接威胁 P158「CLOCK/RESET 不是数据边」的契约。
- 建议：`to_dict/from_dict` 由 dataclass 生成并版本化，缺字段显式失败或写进 [SNAPSHOT_SURFACE](../dev/SNAPSHOT_SURFACE.md) 的"不保证"清单；未知 `EdgeKind` 一律抛错（可给 `SVQ_ALLOW_LEGACY_SNAPSHOT=1` 显式兼容）；命令结果改用 TypedDict/dataclass 并由其生成 schema（与 P182.2 同向，但这里从实现侧消除第四份定义）。
- 代价：中；建议先只做 `from_dict` 的显式失败，收益/成本比最高。

**St-02 · 让声明式 DAG 名副其实**
- 现状：F-S3。
- 风险：`requires/provides` 只保证执行顺序，不保证数据依赖；某个 Stage 新增读取 `graph._gen_block_map` 却没声明，pipeline 不会发现；Stage 可任意改私有字段。
- 建议：`Stage.run` 改为接收/返回 context（对齐 `core/pipeline.py` 的 `PipelineStep`），两个 pipeline 合并为一份实现；`requires/provides` 在运行时与实际读写做校验。这也正是 P182.6「合并两套 DAG」的具体落地形态。
- 代价：17 个 Stage 签名改造，机械但面大，建议一次一个 stage 组。

**St-03 · 图版本 / 冻结，让派生缓存自动失效**
- 现状：F-S4。
- 风险：`cond_ops`/`backfill` 在 tracer 初始化后仍改图；跨 `load_snapshot` 建立的派生索引可能读到缺 `OP_TERNARY`/`BRANCH_*` 节点的陈旧视图，且运行时无法检测。
- 建议：给 `SignalGraph` 加 `revision`，构建完成后 `freeze()`（禁止 `add_*`）；所有派生缓存绑定 revision，变更即失效；撤销手动 `clear_cache()`。
- 代价：中；与 Rb-02 的 phase 一起做最省。

**St-04 · 把"单一实现"从正则 gate 升级为白名单制**
- 现状：F-S5 / F-S7。
- 风险：`contracts.py` 自称唯一 edge 策略，但 12 个文件里仍有字符串硬编码；现有 gate 只扫 4 个文件 → 新增命令很容易重新引入第二份策略且门禁不红。
- 建议：把 `test_p158_data_edge_contract.py` 的扫描扩到全 `src/`，对 `EdgeKind` 字符串字面量实行"白名单 + 显式豁免"；条件解析收敛到 `condition_analysis.py` 一处，其余模块调用它；`--from-snapshot` 互斥校验抽成公共参数校验；把 `CLI_SURFACE` / `AGENT_FEATURE_MAP` / `SKILL.md` / schema 统一由 registry 生成（`gen_cli_surface.py` 已有生成器，扩展它），把"改一处同步 7 处"变成一次生成。
- 代价：大，按模块分批；与 P182.4 / P182.6 同向但更偏实现。

**St-05 · 去掉进程级全局，边界收口**
- 现状：F-S6 / F-R10。
- 风险：同一进程内多个 tracer / 多次请求（pytest、批量查询）被 `_QUIET` 污染；quiet 会连带跳过内存检测；`_ELABORATION_INCOMPLETE` 是死全局；新增输出点极易漏 `is_quiet()` 门控（`graph_builder.py:617` 已漏）。
- 建议：把 quiet / log level / 构建上限变成显式 `BuildOptions` 沿调用链传；删除无消费者的 `_ELABORATION_INCOMPLETE`，或把内存/完整性状态真正接进输出；写盘与 stdout/stderr 集中到边界层；两份 `sys.path` 注入收敛为一处。
- 代价：中；收益是 core 真正成为可复用、可并发的纯计算层。

**St-06 · 测试形态从"固定样本"补一层"性质 + 故障"**
- 现状：F-R11 / F-S1。
- 建议：保留现有 394 个行为测试，另加 3 类性质测试（`SignalGraph` 往返不变量、8 份条件解析的等价性、任意命令信封字段完备）与 Rb-07 的故障注入套件；明确区分"RTL mutation（产品级 oracle）"与"Python 实现 mutation（检查器有效性）"，后者目前缺位。
- 代价：小到中；`hypothesis` 可选，用固定生成器也能起步。

---

## 6. 复核命令（给后续 agent，只读）

```bash
git rev-parse --short HEAD
grep -rn 'except Exception' src/ | wc -l
sed -n '549,562p' src/sv_query/trace/core/graph/models.py
sed -n '313,334p;399,406p;450,476p' src/sv_query/trace/unified_tracer.py
sed -n '36,44p;64,76p' src/sv_query/trace/core/builder/graph_pipeline.py
sed -n '740,755p' src/sv_query/trace/core/graph/models.py
sed -n '417,438p' src/cli/main.py
sed -n '416,432p' src/sv_query/trace/core/cache/ast_cache.py
grep -rn '"DRIVER"\|"CONNECTION"\|"BIT_SELECT"' src/sv_query/trace/ | wc -l
python3 tools/check_docs.py
```

判读原则：输出与本文【事实】不符时，以命令输出为准。

---

## 7. 与 P182 的边界

- **不重复**：P182.1~4（envelope / schema / stats 完整性 / 入口收敛）本文不提方案。
- **可作为输入**：Rb-05 / St-02 / St-04 与 P182.5（snapshot/cache/session 评估）、P182.6（结构清理）相关，但本文只给实现层证据与候选动作，**不新增 PLAN 项、不修改 P182 措辞**。
- **优先级主张**：Rb-01（失败分级）与 Rb-02（构建事务性）应先于或至少并行于 P182.1，否则统一后的 envelope 仍可能承载"内部失败被伪装成空事实"的载荷。

**若只做两件事**：Rb-01 与 Rb-02。一个保证"失败可观察"，一个保证"半成品不会被当成完整图"；两者都是语义契约在代码实现层的地基。

---

## 8. 变更记录

| 版本 | 时间 | 变更 |
|---|---|---|
| v1.0 | 2026-11-16 20:59 CST | 初稿。基于 git `2ddcfe92` 的只读实现层审查；11 条鲁棒性事实 + 7 条结构性事实、7 条 Rb / 6 条 St 候选建议。未改代码、未并入 P182。 |
