# CLI 能力清单 (生成物 — 请勿手改)

> **生成方式**: `python3 tools/gen_cli_surface.py`  (数据源: `src/cli/_registry.py` + typer introspection)
> **生成日期**: 2026-11-11  |  **漂移校验**: `python3 tools/gen_cli_surface.py --check`
> **分层检查**: `python3 tools/check_cli_layers.py` (R1~R6)

## 总览

- 叶子命令总数: **45**
- 按层: `core`=40, `exp`=5
- core 内分组: `semantic`=25, `verify`=3, `scope`=1, `locate`=7, `state`=4

| 层 | 消费者 | 稳定性 | 只读 | 必须 JSON | schema | 说明 |
|---|---|---|---|---|---|---|
| `core` | agent | stable | ✅ | ✅ | 1 | agent 一等公民: 只读 + JSON + 稳定 schema; readonly = 不改 RTL/项目文件, cache/output 由 write_scope 标记 |
| `view` | human | stable | ✅ | — | — | 人眼面 (图/叙述); 默认含于 capabilities, 后续重点开发 |
| `exp` | none | unstable | ✅ | — | — | 降级区: 规范入口 svq exp <组> <子> (老路径为别名); 无 schema 承诺, 只修 bug; --include-exp 才列出 |
| `dev` | dev | none | ✅ | — | — | 开发者内部调试 (当前无命令; expression 已于 iter_252 归档) |
| `out` | none | none | ✅ | — | — | 移出 CLI (会写 RTL/项目文件) → tools/; 不算产品命令 |

## `core` (40 个)

| 命令 | 兼容别名 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|---|
| `capabilities` | — | — | locate | primitive | cheap | ✅ | — | ✅ | 本清单自身 (agent 应先读它再决定调什么) |
| `filelist prune` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | [P91/P158.5] top-aware 保守 filelist 裁剪; 默认 dry-run; --apply 才写; 只允许 .f/.fl; 覆盖需 --force + .bak |
| `graph edges` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | 列出图边; 支持 --file / --filelist (iter_236 补) |
| `graph nodes` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | 列图节点 (kind/module/--match 过滤; --detail 给表达式等富字段); 支持 --file / --filelist |
| `graph subgraph` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | [P60] seed 的 k-hop 局部子图; depth/direction/edge-kinds/budget; JSON boundary/truncated |
| `search` | — | — | locate | primitive | cheap | ✅ | — | ✅ | 文本/正则搜索; [iter_231] 已补 --json |
| `stats` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ |  |
| `scope` | — | — | scope | fact | cheap | ✅ | ✅ | ✅ | [规范入口] scope 聚合: 类型/父/子/端口/参数 (入口层, 不做因果追踪) |
| `class` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 不给 name → 列出所有 class; 给了 → 成员(类型级)+实例(实例级); --member 查某成员实例 |
| `connections` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 连接: 仅接受实例路径 → 端口↔内部信号 (输出带 resolved_as; 模块类型明确报错) |
| `controlflow analyze` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 信号的驱动条件分析; --conditions-only 只要扁平条件列表 (原 controlflow conditions) |
| `controlflow list-conditioned` | — | — | semantic | fact | expensive | ✅ | ✅ | ✅ | 列出所有带条件驱动的信号 (枚举, 用于找入口) |
| `dataflow analyze` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 源→目标路径 (有向, 跨模块; 实例级 id; 与 paths --directed 结论一致) |
| `drivers` | `trace fanin` | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 谁驱动这个信号 (上游; DRIVER 边反向遍历); 兼容别名 trace fanin |
| `hierarchy` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 实例层级树 (机器可读版 arch show) |
| `instances` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | 列出实例; 给实例路径 → 详情 (类型/父/子/端口); 支持 --filelist |
| `loads` | `trace fanout` | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 这个信号被谁使用 (下游; DRIVER 边正向遍历); 兼容别名 trace fanout |
| `params` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [规范入口] 实例的**生效**参数值 (含 is_overridden: 区分 override 与默认) |
| `paths` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 图上路径 (实例级 id; --all 枚举; --directed 只沿数据流方向, 与 dataflow analyze 结论一致) |
| `ports` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [规范入口] 模块端口总览 (方向/位宽/入边数/出边数) |
| `trace constraint-chain` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | 两个 random 变量之间的最短 constraint 链 (co-membership; 非 solver 证明) |
| `trace constraint-neighborhood` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 一次查询跨多个 constraint block 的 random 变量关系图 (co-constraint, 非 fanin; 含重要性指标, 启发式) |
| `trace constraints` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [P63] 属性受哪些 constraint 约束 (类型/实例; 独立语义域, 不走 fanin) |
| `trace covergroup` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [P63] covergroup 采样链; --rand 查属性→约束链 |
| `trace covergroups` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [P63] 列出 covergroup 定义 (可按 class 过滤) |
| `trace coverpoints` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [P63] 反向查询: 信号被哪些 covergroup/coverpoint 采样 |
| `trace evidence` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 源码证据 (always/if 块原文) |
| `trace frontier` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | 结构 trace 的边界/断点 + 下一步 probe；不分类 FIFO |
| `trace impact` | — | — | semantic | fact | expensive | ✅ | ✅ | ✅ | 传递影响 + 启发式风险分 (未标定, 仅用于同一图内相对排序; 见 KNOWN_LIMITATIONS §3.4) |
| `trace lookup` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | 完整 RTL hier path → canonical id (严格; $root/位父回退/aliases; 不做模糊后缀) |
| `trace manifest` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 批量 waveform manifest: full path → canonical + profile (type/bit/clock/reset/stage) |
| `trace profile` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | 信号 profile: canonical/aliases/位映射/clock/reset/sequential/source (波形关联) |
| `trace tb-join` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | TB random field → RTL snapshot candidate join (name-based; single_candidate 不是连接证明) |
| `snapshot compare` | — | — | state | state | medium | ✅ | — | ✅ | 比较两个快照, 或两个 SV 文件 (文件模式 = 原 diff compare; --signal 看可达性差异) |
| `snapshot delete` | — | — | state | state | cheap | ✅ | — | ✅ | [iter_231] 已补 --json |
| `snapshot list` | — | — | state | state | cheap | ✅ | — | ✅ | 列出快照; 给 tag → 该快照详情 (原 snapshot show) |
| `snapshot save` | — | — | state | state | medium | ✅ | ✅ | ✅ | [iter_239 1b] 默认写缓存目录 (~/.svq/cache/snapshots; 可用 SVQ_SNAPSHOT_DIR 覆盖) |
| `verify claim` | — | — | verify | fact | medium | ✅ | ✅ | ✅ | 验证 claim: driver/path/connection/bit → verified|contradicted|unknown |
| `verify consistency` | — | — | verify | fact | medium | ✅ | ✅ | ✅ | 双向一致性: fanin/fanout、bit parent/bit_range、connection port↔internal |
| `verify structural` | — | — | verify | fact | medium | ✅ | ✅ | ✅ | [P61] 结构审查: sibling 端口集合对称性 → findings + evidence + subgraph spec |

## `exp` (5 个)

| 命令 | 兼容别名 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|---|
| `diagnose` | — | — | diagnose | experimental | cheap | ✅ | ✅ | ✅ | [exp] 只读诊断; --json 干净路径不稳定, 默认不提供, 仅 --include-exp 列出 |
| `architecture graph` | — | — | render | experimental | medium | ✅ | ✅ | ✅ | [P133] module/instance architecture graph from real net connections; not the retired full signal graph ; [exp] experimental, hidden by default |
| `review render` | — | — | render | experimental | cheap | ✅ | ✅ | ✅ | [P62] 单个 structural finding 的局部 SVG/HTML; 只消费 subgraph ; [exp] experimental, hidden by default |
| `trace overview` | — | — | render | experimental | expensive | ✅ | ✅ | ✅ | 两个信号之间的综合叙述 (dataflow + controlflow + evidence) ; [exp] experimental, hidden by default |
| `audit` | — | — | semantic | experimental | medium | ✅ | ✅ | ✅ | [exp] 设计审计; 启发式/完成度低, 默认不提供, 仅 --include-exp 列出 |

## 兼容别名 (老名保留, 同一实现)

| 别名 | 规范名 |
|---|---|
| `trace fanin` | `drivers` |
| `trace fanout` | `loads` |

## 计划新增 (语义 core 缺口: instance 查询)

| 新命令 | 复用现有 API | 输出 |
|---|---|---|

