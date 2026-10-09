# CLI 能力清单 (生成物 — 请勿手改)

> **生成方式**: `python3 tools/gen_cli_surface.py`  (数据源: `src/cli/_registry.py` + typer introspection)
> **生成日期**: 2026-10-09  |  **漂移校验**: `python3 tools/gen_cli_surface.py --check`
> **分层检查**: `python3 tools/check_cli_layers.py` (R1~R6)

## 总览

- 叶子命令总数: **74**
- 按层: `core`=34, `dev`=3, `exp`=24, `view`=13
- core 内分组: `semantic`=17, `locate`=7, `state`=6, `diagnose`=4

| 层 | 消费者 | 稳定性 | 只读 | 必须 JSON | schema | 说明 |
|---|---|---|---|---|---|---|
| `core` | agent | stable | ✅ | ✅ | 1 | agent 一等公民: 只读 + JSON + 稳定 schema |
| `view` | human | stable | ✅ | — | — | 人眼面 (图/叙述); 默认含于 capabilities, 后续重点开发 |
| `exp` | none | unstable | ✅ | — | — | 降级区: 规范入口 svq exp <组> <子> (老路径为别名); 无 schema 承诺, 只修 bug; --include-exp 才列出 |
| `dev` | dev | none | ✅ | — | — | 开发者内部调试, 不进用户文档 |
| `out` | none | none | ✅ | — | — | 移出 CLI (会写 RTL/项目文件) → tools/; 不算产品命令 |

## `core` (34 个)

| 命令 | 兼容别名 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|---|
| `diagnose imports` | `fix imports` | — | diagnose | diagnosis | cheap | ✅ | ✅ | ✅ | 找 UndeclaredIdentifier 的定义来源; **只读** —— 写新 filelist 用 tools/fix_imports.py (老名 fix imports) |
| `diagnose report` | `fix report` | — | diagnose | diagnosis | cheap | ✅ | ✅ | ✅ | [规范入口] 按错误码给出修复方向; 只读 (老名 fix report) |
| `diagnose timescale` | `fix timescale` | — | diagnose | diagnosis | cheap | ✅ | ✅ | ✅ | 列出缺 timescale 的文件; **只读** —— 写文件用 tools/fix_timescale.py --apply (老名 fix timescale) |
| `diagnose widths` | `fix widths` | — | diagnose | diagnosis | cheap | ✅ | ✅ | ✅ | 用 syntax tree + pyslang.clog2 解析 typedef 真实位宽; 只读 (老名 fix widths) |
| `capabilities` | — | — | locate | primitive | cheap | ✅ | — | ✅ | 本清单自身 (agent 应先读它再决定调什么) |
| `graph dump` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | [缺口] 只支持 --file 单文件 |
| `graph edges` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | [缺口] 只支持 --file 单文件 |
| `graph find` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | [缺口] 只支持 --file 单文件 |
| `graph nodes` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ | [缺口] 只支持 --file 单文件, 真实项目(filelist)不可用 |
| `search` | — | — | locate | primitive | cheap | ✅ | — | ✅ | 文本/正则搜索; [iter_231] 已补 --json |
| `stats` | — | — | locate | primitive | cheap | ✅ | ✅ | ✅ |  |
| `class` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | class 成员(类型级) + 实例(实例级); --member 查某成员的实例节点 |
| `classes` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | 列出编译域内 class 名 |
| `connections` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 连接: 实例→端口↔内部信号 / 模块→四类边+置信度 (输出带 resolved_as) |
| `controlflow analyze` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 信号的驱动条件分析 |
| `controlflow conditions` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 信号的全部驱动条件 |
| `controlflow list-conditioned` | — | — | semantic | fact | expensive | ✅ | ✅ | ✅ | 列出所有带条件驱动的信号 (枚举, 用于找入口) |
| `dataflow analyze` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 源→目标路径 |
| `drivers` | `trace fanin` | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 谁驱动这个信号 (上游; DRIVER 边反向遍历); 兼容别名 trace fanin |
| `hierarchy` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 实例层级树 (机器可读版 arch show) |
| `instance` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [规范入口] 单实例详情: 类型/父/子/端口(方向+位宽+内部信号) |
| `instances` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [规范入口] 列出模块实例 (full_path/module_type/parent); 支持 --filelist |
| `loads` | `trace fanout` | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 这个信号被谁使用 (下游; DRIVER 边正向遍历); 兼容别名 trace fanout |
| `params` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [规范入口] 实例的**生效**参数值 (含 is_overridden: 区分 override 与默认) |
| `paths` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | [规范入口] 图上路径 (跨模块端口跳转; --all 枚举全部, 有上限) |
| `ports` | — | — | semantic | fact | cheap | ✅ | ✅ | ✅ | [规范入口] 模块端口总览 (方向/位宽/入边数/出边数) |
| `trace evidence` | — | — | semantic | fact | medium | ✅ | ✅ | ✅ | 源码证据 (always/if 块原文) |
| `trace impact` | — | — | semantic | fact | expensive | ✅ | ✅ | ✅ | 传递影响 + 风险分级 |
| `diff compare` | — | — | state | state | medium | ✅ | — | ✅ | [计划] 并入 snapshot compare |
| `snapshot compare` | — | — | state | state | medium | ✅ | — | ✅ | graph 差异 (diff compare 计划并入这里) |
| `snapshot delete` | — | — | state | state | cheap | ✅ | — | ✅ | [iter_231] 已补 --json |
| `snapshot list` | — | — | state | state | cheap | ✅ | — | ✅ |  |
| `snapshot save` | — | — | state | state | medium | ✅ | ✅ | ✅ | [iter_231] 已补 --json; 默认写 .svq/ (P2 迁 $SVQ_CACHE_DIR) |
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
| `exp backpressure analyze` | `backpressure analyze` | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `exp backpressure deadlock` | `backpressure deadlock` | — | bus | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp handshake analyze` | `handshake analyze` | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `exp handshake pair` | `handshake pair` | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `exp handshake scan` | `handshake scan` | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `exp protocol detect` | `protocol detect` | — | bus | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp protocol list` | `protocol list` | — | bus | experimental | cheap | — | — | ✅ |  |
| `exp protocol semantics` | `protocol semantics` | — | bus | experimental | medium | ✅ | — | ✅ |  |
| `exp protocol show` | `protocol show` | — | bus | experimental | medium | — | — | ✅ |  |
| `exp cdc analyze` | `cdc analyze` | — | struct | experimental | medium | ✅ | ✅ | ✅ | 算法可靠性待验证; 见 docs/EXP_NAMESPACE.md 晋升门槛 |
| `exp timing analyze` | `timing analyze` | — | struct | experimental | medium | ✅ | ✅ | ✅ | 算法可靠性待验证; 见 docs/EXP_NAMESPACE.md 晋升门槛 |
| `exp coverage analyze` | `coverage analyze` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp coverage gap` | `coverage gap` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp coverage generate` | `coverage generate` | — | verif | experimental | medium | — | ✅ | ✅ |  |
| `exp coverage suggest` | `coverage suggest` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp randomize extract` | `randomize extract` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp randomize list` | `randomize list` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp randomize reachability` | `randomize reachability` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp randomize trace` | `randomize trace` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp risk analyze` | `risk analyze` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp sva coverage` | `sva coverage` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp sva extract` | `sva extract` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp sva timing` | `sva timing` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `exp verify gap` | `verify gap` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |

## `dev` (3 个)

| 命令 | 兼容别名 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|---|
| `expression build` | — | — | internal | debug | cheap | ✅ | — | ✅ |  |
| `expression cond` | — | — | internal | debug | cheap | ✅ | — | ✅ |  |
| `expression func` | — | — | internal | debug | cheap | ✅ | — | ✅ |  |

## 兼容别名 (老名保留, 同一实现)

| 别名 | 规范名 |
|---|---|
| `backpressure analyze` | `exp backpressure analyze` |
| `backpressure deadlock` | `exp backpressure deadlock` |
| `cdc analyze` | `exp cdc analyze` |
| `coverage analyze` | `exp coverage analyze` |
| `coverage gap` | `exp coverage gap` |
| `coverage generate` | `exp coverage generate` |
| `coverage suggest` | `exp coverage suggest` |
| `fix imports` | `diagnose imports` |
| `fix report` | `diagnose report` |
| `fix timescale` | `diagnose timescale` |
| `fix widths` | `diagnose widths` |
| `handshake analyze` | `exp handshake analyze` |
| `handshake pair` | `exp handshake pair` |
| `handshake scan` | `exp handshake scan` |
| `protocol detect` | `exp protocol detect` |
| `protocol list` | `exp protocol list` |
| `protocol semantics` | `exp protocol semantics` |
| `protocol show` | `exp protocol show` |
| `randomize extract` | `exp randomize extract` |
| `randomize list` | `exp randomize list` |
| `randomize reachability` | `exp randomize reachability` |
| `randomize trace` | `exp randomize trace` |
| `risk analyze` | `exp risk analyze` |
| `sva coverage` | `exp sva coverage` |
| `sva extract` | `exp sva extract` |
| `sva timing` | `exp sva timing` |
| `timing analyze` | `exp timing analyze` |
| `trace fanin` | `drivers` |
| `trace fanout` | `loads` |
| `verify gap` | `exp verify gap` |

## 计划新增 (语义 core 缺口: instance 查询)

| 新命令 | 复用现有 API | 输出 |
|---|---|---|

