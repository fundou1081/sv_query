# Agent capabilities (generated — do not edit)

> Source: `sv_query capabilities --json` / `cli._registry.to_json()`
> Regenerate: `python3 tools/gen_agent_skill.py`  
> Check: `python3 tools/gen_agent_skill.py --check`
> Generated: 2026-11-19

## Entry rule

1. Run `sv_query capabilities --json` before choosing a command.
2. Treat this table as the command index; do not invent commands.
3. Use `--json`; decide success from `ok`, not only exit code.
4. A `found=false` answer is data; `ok=false` is a failed query.

## Counts (stable core view)

- core commands in this reference: **39**
- all registered commands (core+exp): **45** ({'core': 39, 'exp': 6}); `capabilities --json` 默认只列 39 条 core，exp 需 `--include-exp`
- core groups: {'semantic': 24, 'verify': 3, 'scope': 1, 'locate': 7, 'state': 4}
- `exp` commands are intentionally excluded from the stable table.

## Commands

| command | envelope | group | recommended | aliases | note |
|---|---|---|---|---|---|
| `capabilities` | direct | locate | ✅ | — | 本清单自身 (agent 应先读它再决定调什么) |
| `filelist prune` | standard | locate | — | — | [P91/P158.5] top-aware 保守 filelist 裁剪; 默认 dry-run; --apply 才写; 只允许 .f/.fl; 覆盖需 --force + .bak |
| `graph edges` | standard | locate | — | — | 列出图边; 支持 --file / --filelist (iter_236 补) |
| `graph nodes` | standard | locate | — | — | 列图节点 (kind/module/--match 过滤; --detail 给表达式等富字段); 支持 --file / --filelist |
| `graph subgraph` | standard | locate | — | — | [P60] seed 的 k-hop 局部子图; depth/direction/edge-kinds/budget; JSON boundary/truncated |
| `search` | direct | locate | — | — | 文本/正则搜索; [iter_231] 已补 --json |
| `stats` | standard | locate | ✅ | — |  |
| `scope` | standard | scope | ✅ | — | [规范入口] scope 聚合: 类型/父/子/端口/参数 (入口层, 不做因果追踪) |
| `class` | direct | semantic | — | — | 不给 name → 列出所有 class; 给了 → 成员(类型级)+实例(实例级); --member 查某成员实例 |
| `connections` | direct | semantic | ✅ | — | [规范入口] 连接: 仅接受实例路径 → 端口↔内部信号 (输出带 resolved_as; 模块类型明确报错) |
| `controlflow analyze` | standard | semantic | ✅ | — | 信号的驱动条件分析; --conditions-only 只要扁平条件列表 (原 controlflow conditions) |
| `controlflow list-conditioned` | standard | semantic | — | — | 列出所有带条件驱动的信号 (枚举, 用于找入口) |
| `dataflow analyze` | standard | semantic | ✅ | — | 源→目标路径 (有向, 跨模块; 实例级 id; 与 paths --directed 结论一致) |
| `drivers` | standard | semantic | ✅ | `trace fanin` | [规范入口] 谁驱动这个信号 (上游; DRIVER 边反向遍历); 兼容别名 trace fanin |
| `hierarchy` | direct | semantic | ✅ | — | [规范入口] 实例层级树 (机器可读版 arch show) |
| `instances` | direct | semantic | ✅ | — | 列出实例; 给实例路径 → 详情 (类型/父/子/端口); 支持 --filelist |
| `loads` | standard | semantic | ✅ | `trace fanout` | [规范入口] 这个信号被谁使用 (下游; DRIVER 边正向遍历); 兼容别名 trace fanout |
| `params` | direct | semantic | ✅ | — | [规范入口] 实例的**生效**参数值 (含 is_overridden: 区分 override 与默认) |
| `paths` | direct | semantic | ✅ | — | [规范入口] 图上路径 (实例级 id; --all 枚举; --directed 只沿数据流方向, 与 dataflow analyze 结论一致) |
| `ports` | direct | semantic | ✅ | — | [规范入口] 模块端口总览 (方向/位宽/入边数/出边数) |
| `trace constraint-chain` | standard | semantic | — | — | 两个 random 变量之间的最短 constraint 链 (co-membership; 非 solver 证明) |
| `trace constraint-neighborhood` | standard | semantic | — | — | 一次查询跨多个 constraint block 的 random 变量关系图 (co-constraint, 非 fanin; 含重要性指标, 启发式) |
| `trace constraints` | standard | semantic | — | — | [P63] 属性受哪些 constraint 约束 (类型/实例; 独立语义域, 不走 fanin) |
| `trace covergroup` | standard | semantic | — | — | [P63] covergroup 采样链; --rand 查属性→约束链 |
| `trace covergroups` | standard | semantic | — | — | [P63] 列出 covergroup 定义 (可按 class 过滤) |
| `trace coverpoints` | standard | semantic | — | — | [P63] 反向查询: 信号被哪些 covergroup/coverpoint 采样 |
| `trace evidence` | standard | semantic | ✅ | — | 源码证据 (always/if 块原文) |
| `trace frontier` | standard | semantic | — | — | 结构 trace 的边界/断点 + 下一步 probe；不分类 FIFO |
| `trace lookup` | standard | semantic | ✅ | — | 完整 RTL hier path → canonical id (严格; $root/位父回退/aliases; 不做模糊后缀) |
| `trace manifest` | standard | semantic | ✅ | — | 批量 waveform manifest: full path → canonical + profile (type/bit/clock/reset/stage) |
| `trace profile` | standard | semantic | ✅ | — | 信号 profile: canonical/aliases/位映射/clock/reset/sequential/source (波形关联) |
| `trace tb-join` | standard | semantic | — | — | TB random field → RTL snapshot candidate join (name-based; single_candidate 不是连接证明) |
| `snapshot compare` | direct | state | ✅ | — | 比较两个快照, 或两个 SV 文件 (文件模式 = 原 diff compare; --signal 看可达性差异) |
| `snapshot delete` | direct | state | — | — | [iter_231] 已补 --json |
| `snapshot list` | direct | state | — | — | 列出快照; 给 tag → 该快照详情 (原 snapshot show) |
| `snapshot save` | direct | state | — | — | [iter_239 1b] 默认写缓存目录 (~/.svq/cache/snapshots; 可用 SVQ_SNAPSHOT_DIR 覆盖) |
| `verify claim` | standard | verify | ✅ | — | 验证 claim: driver/path/connection/bit → verified\|contradicted\|unknown |
| `verify consistency` | standard | verify | ✅ | — | 双向一致性: fanin/fanout、bit parent/bit_range、connection port↔internal |
| `verify structural` | standard | verify | — | — | [P61] 结构审查: sibling 端口集合对称性 → findings + evidence + subgraph spec |

## Failure / completeness reminders

- `stats` success has `result.elaboration_errors=[]`; malformed RTL is structured failure.
- `drivers`/`loads`/`trace evidence`/`trace profile` unknown target are the documented
  rc=0 + ok=false hybrid exceptions; other failures are rc=1.
- `snapshot list` has a list root without a tag and an object root with a tag.

