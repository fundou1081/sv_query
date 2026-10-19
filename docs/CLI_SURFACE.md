# CLI 能力清单 (生成物 — 请勿手改)

> **生成方式**: `python3 tools/gen_cli_surface.py`  (数据源: `src/cli/_registry.py` + typer introspection)
> **生成日期**: 2026-10-20  |  **漂移校验**: `python3 tools/gen_cli_surface.py --check`
> **分层检查**: `python3 tools/check_cli_layers.py` (R1~R6)

## 总览

- 叶子命令总数: **63**
- 按层: `core`=26, `exp`=24, `view`=13
- core 内分组: `semantic`=15, `locate`=5, `diagnose`=1, `state`=5

| 层 | 消费者 | 稳定性 | 只读 | 必须 JSON | schema | 说明 |
|---|---|---|---|---|---|---|
| `core` | agent | stable | ✅ | ✅ | 1 | agent 一等公民: 只读 + JSON + 稳定 schema |
| `view` | human | stable | ✅ | — | — | 人眼面 (图/叙述); 默认含于 capabilities, 后续重点开发 |
| `exp` | none | unstable | ✅ | — | — | 降级区: 规范入口 svq exp <组> <子> (老路径为别名); 无 schema 承诺, 只修 bug; --include-exp 才列出 |
| `dev` | dev | none | ✅ | — | — | 开发者内部调试 (当前无命令; expression 已于 iter_252 归档) |
| `out` | none | none | ✅ | — | — | 移出 CLI (会写 RTL/项目文件) → tools/; 不算产品命令 |

## `core` (26 个)

| 命令 | 兼容别名 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|---|
| `diagnose` | — | — | diagnose | diagnosis | cheap | ✅ | ✅ | ✅ | 只读诊断: <检查项> = imports|report|timescale|widths; 不改文件 (写文件用 tools/fix_*.py) |
| `capabilities` | — | — | locate | primitive | cheap | ✅ | — | ✅ | 本清单自身 (agent 应先读它再决定调什么) |
| `graph edges` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | 列出图边; 支持 --file / --filelist (iter_236 补) |
| `graph nodes` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | 列图节点 (kind/module/--match 过滤; --detail 给表达式等富字段); 支持 --file / --filelist |
| `search` | — | — | locate | primitive | cheap | ✅ | — | ✅ | 文本/正则搜索; [iter_231] 已补 --json |
| `stats` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ |  |
| `class` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 不给 name → 列出所有 class; 给了 → 成员(类型级)+实例(实例级); --member 查某成员实例 |
| `connections` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 连接: 实例→端口↔内部信号 / 模块→四类边+置信度 (输出带 resolved_as) |
| `controlflow analyze` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 信号的驱动条件分析 |
| `controlflow conditions` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 信号的全部驱动条件 |
| `controlflow list-conditioned` | — | — | semantic | fact | expensive | ✅ | ✅ | ✅ | 列出所有带条件驱动的信号 (枚举, 用于找入口) |
| `dataflow analyze` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 源→目标路径 |
| `drivers` | `trace fanin` | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 谁驱动这个信号 (上游; DRIVER 边反向遍历); 兼容别名 trace fanin |
| `hierarchy` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 实例层级树 (机器可读版 arch show) |
| `instances` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | 列出实例; 给实例路径 → 详情 (类型/父/子/端口); 支持 --filelist |
| `loads` | `trace fanout` | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 这个信号被谁使用 (下游; DRIVER 边正向遍历); 兼容别名 trace fanout |
| `params` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [规范入口] 实例的**生效**参数值 (含 is_overridden: 区分 override 与默认) |
| `paths` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 图上路径 (跨模块端口跳转; --all 枚举全部, 有上限) |
| `ports` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [规范入口] 模块端口总览 (方向/位宽/入边数/出边数) |
| `trace evidence` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 源码证据 (always/if 块原文) |
| `trace impact` | — | — | semantic | fact | expensive | ✅ | ✅ | ✅ | 传递影响 + 风险分级 |
| `snapshot compare` | — | — | state | state | medium | ✅ | — | ✅ | 比较两个快照, 或两个 SV 文件 (文件模式 = 原 diff compare; --signal 看可达性差异) |
| `snapshot delete` | — | — | state | state | cheap | ✅ | — | ✅ | [iter_231] 已补 --json |
| `snapshot list` | — | — | state | state | cheap | ✅ | — | ✅ |  |
| `snapshot save` | — | — | state | state | medium | ✅ | ✅ | ✅ | [iter_239 1b] 默认写缓存目录 (~/.svq/cache/snapshots; 可用 SVQ_SNAPSHOT_DIR 覆盖) |
| `snapshot show` | — | — | state | state | cheap | ✅ | — | ✅ |  |

## `view` (13 个)

| 命令 | 兼容别名 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|---|
| `arch show` | — | — | render | presentation | expensive | — | ✅ | ✅ | [计划] 迁 VizData 统一渲染 |
| `design show` | — | — | render | presentation | expensive | — | ✅ | ✅ | [缺口] 仅 3 测试文件 |
| `trace overview` | — | — | render | presentation | expensive | ✅ | ✅ | ✅ | [计划] 归入 view/overview |
| `visualize chain` | — | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize compute` | — | — | render | presentation | expensive | — | ✅ | ✅ | [缺口] 仅 1 测试文件 |
| `visualize dataflow` | — | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize datapath` | — | — | render | presentation | expensive | — | ✅ | ✅ | [缺口] 0 测试 |
| `visualize gap` | — | — | render | presentation | medium | — | — | ✅ |  |
| `visualize graph` | — | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize module` | — | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize pipeline` | — | — | render | presentation | medium | ✅ | ✅ | ✅ |  |
| `visualize teach` | — | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize timed` | — | — | render | presentation | expensive | — | ✅ | ✅ | [缺口] 仅 1 测试文件 |

## `exp` (24 个)

| 命令 | 兼容别名 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|---|
| `exp backpressure analyze` | — | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `exp backpressure deadlock` | — | — | bus | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp handshake analyze` | — | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `exp handshake pair` | — | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `exp handshake scan` | — | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `exp protocol detect` | — | — | bus | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp protocol list` | — | — | bus | experimental | cheap | — | — | ✅ |  |
| `exp protocol semantics` | — | — | bus | experimental | medium | ✅ | — | ✅ |  |
| `exp protocol show` | — | — | bus | experimental | medium | — | — | ✅ |  |
| `exp cdc analyze` | — | — | struct | experimental | medium | ✅ | ✅ | ✅ | 算法可靠性待验证; 见 docs/EXP_NAMESPACE.md 晋升门槛 |
| `exp timing analyze` | — | — | struct | experimental | medium | ✅ | ✅ | ✅ | 算法可靠性待验证; 见 docs/EXP_NAMESPACE.md 晋升门槛 |
| `exp coverage analyze` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp coverage gap` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp coverage generate` | — | — | verif | experimental | medium | — | ✅ | ✅ |  |
| `exp coverage suggest` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp randomize extract` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp randomize list` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp randomize reachability` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp randomize trace` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp risk analyze` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp sva coverage` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp sva extract` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp sva timing` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp verify gap` | — | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |

## 兼容别名 (老名保留, 同一实现)

| 别名 | 规范名 |
|---|---|
| `trace fanin` | `drivers` |
| `trace fanout` | `loads` |

## 计划新增 (语义 core 缺口: instance 查询)

| 新命令 | 复用现有 API | 输出 |
|---|---|---|

