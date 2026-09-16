# CLI 能力清单 (生成物 — 请勿手改)

> **生成方式**: `python3 tools/gen_cli_surface.py`  (数据源: `src/cli/_registry.py` + typer introspection)
> **生成日期**: 2026-09-17  |  **漂移校验**: `python3 tools/gen_cli_surface.py --check`
> **分层检查**: `python3 tools/check_cli_layers.py` (R1~R6)

## 总览

- 叶子命令总数: **65**
- 按层: `core`=23, `dev`=3, `exp`=24, `out`=2, `view`=13
- core 内分组: `semantic`=8, `locate`=7, `state`=6, `diagnose`=2

| 层 | 消费者 | 稳定性 | 只读 | 必须 JSON | schema | 说明 |
|---|---|---|---|---|---|---|
| `core` | agent | stable | ✅ | ✅ | 1 | agent 一等公民: 只读 + JSON + 稳定 schema |
| `view` | human | stable | ✅ | — | — | 人眼面 (图/叙述); 默认含于 capabilities, 后续重点开发 |
| `exp` | none | unstable | ✅ | — | — | 降级区: 无 schema 承诺, 只修 bug 不加功能; --include-exp 才列出 |
| `dev` | dev | none | ✅ | — | — | 开发者内部调试, 不进用户文档 |
| `out` | none | none | ✅ | — | — | 移出 CLI (会写 RTL/项目文件) → tools/; 不算产品命令 |

## `core` (23 个)

| 命令 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `fix report` | — | diagnose | diagnosis | cheap | ✅ | ✅ | ✅ | [计划] 改名 diagnose report (去 fix 暗示) |
| `fix widths` | — | diagnose | diagnosis | cheap | ✅ | ✅ | ✅ | [计划] 改名 diagnose widths |
| `capabilities` | — | locate | primitive | cheap | ✅ | — | ✅ | 本清单自身 (agent 应先读它再决定调什么) |
| `graph dump` | — | locate | primitive | cheap | ✅ | — | ✅ | [缺口] 只支持 --file 单文件 |
| `graph edges` | — | locate | primitive | cheap | ✅ | — | ✅ | [缺口] 只支持 --file 单文件 |
| `graph find` | — | locate | primitive | cheap | ✅ | — | ✅ | [缺口] 只支持 --file 单文件 |
| `graph nodes` | — | locate | primitive | cheap | ✅ | — | ✅ | [缺口] 只支持 --file 单文件, 真实项目(filelist)不可用 |
| `search` | — | locate | primitive | cheap | — | — | ✅ ⚠️缺JSON | [缺口] 无 --json; 文本 grep |
| `stats` | — | locate | primitive | cheap | ✅ | ✅ | ✅ |  |
| `controlflow analyze` | — | semantic | fact | medium | ✅ | ✅ | ✅ | 信号的驱动条件分析 |
| `controlflow conditions` | — | semantic | fact | medium | ✅ | ✅ | ✅ | 信号的全部驱动条件 |
| `controlflow list-conditioned` | — | semantic | fact | expensive | ✅ | ✅ | ✅ | 列出所有带条件驱动的信号 (枚举, 用于找入口) |
| `dataflow analyze` | — | semantic | fact | medium | ✅ | ✅ | ✅ | 源→目标路径 |
| `trace evidence` | — | semantic | fact | medium | ✅ | ✅ | ✅ | 源码证据 (always/if 块原文) |
| `trace fanin` | drivers | semantic | fact | medium | ✅ | ✅ | ✅ | 谁驱动这个信号 (上游; DRIVER 边反向遍历) |
| `trace fanout` | loads | semantic | fact | medium | ✅ | ✅ | ✅ | 这个信号被谁使用 (下游; DRIVER 边正向遍历) |
| `trace impact` | — | semantic | fact | expensive | ✅ | ✅ | ✅ | 传递影响 + 风险分级 |
| `diff compare` | — | state | state | medium | ✅ | — | ✅ | [计划] 并入 snapshot compare |
| `snapshot compare` | — | state | state | medium | ✅ | — | ✅ | graph 差异 (diff compare 计划并入这里) |
| `snapshot delete` | — | state | state | cheap | — | — | ✅ ⚠️缺JSON |  |
| `snapshot list` | — | state | state | cheap | ✅ | — | ✅ |  |
| `snapshot save` | — | state | state | medium | — | ✅ | ✅ ⚠️缺JSON | [缺口] 无 --json; 默认写 .svq/ (应迁 $SVQ_CACHE_DIR) |
| `snapshot show` | — | state | state | cheap | ✅ | — | ✅ |  |

## `view` (13 个)

| 命令 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `arch show` | — | render | presentation | expensive | — | ✅ | ✅ | [计划] 迁 VizData 统一渲染 |
| `design show` | — | render | presentation | expensive | — | ✅ | ✅ | [缺口] 仅 3 测试文件 |
| `trace overview` | — | render | presentation | expensive | ✅ | ✅ | ✅ | [计划] 归入 view/overview |
| `visualize chain` | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize compute` | — | render | presentation | expensive | — | ✅ | ✅ | [缺口] 仅 1 测试文件 |
| `visualize dataflow` | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize datapath` | — | render | presentation | expensive | — | ✅ | ✅ | [缺口] 0 测试 |
| `visualize gap` | — | render | presentation | medium | — | — | ✅ |  |
| `visualize graph` | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize module` | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize pipeline` | — | render | presentation | medium | ✅ | ✅ | ✅ |  |
| `visualize teach` | — | render | presentation | expensive | — | ✅ | ✅ |  |
| `visualize timed` | — | render | presentation | expensive | — | ✅ | ✅ | [缺口] 仅 1 测试文件 |

## `exp` (24 个)

| 命令 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `backpressure analyze` | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `backpressure deadlock` | — | bus | experimental | medium | ✅ | ✅ | ✅ |  |
| `handshake analyze` | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `handshake pair` | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `handshake scan` | — | bus | experimental | medium | — | ✅ | ✅ |  |
| `protocol detect` | — | bus | experimental | medium | ✅ | ✅ | ✅ |  |
| `protocol list` | — | bus | experimental | cheap | — | — | ✅ |  |
| `protocol semantics` | — | bus | experimental | medium | ✅ | — | ✅ |  |
| `protocol show` | — | bus | experimental | medium | — | — | ✅ |  |
| `cdc analyze` | — | struct | experimental | medium | ✅ | ✅ | ✅ | 算法可靠性待验证; 见 docs/EXP_NAMESPACE.md 晋升门槛 |
| `timing analyze` | — | struct | experimental | medium | ✅ | ✅ | ✅ | 算法可靠性待验证; 见 docs/EXP_NAMESPACE.md 晋升门槛 |
| `coverage analyze` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `coverage gap` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `coverage generate` | — | verif | experimental | medium | — | ✅ | ✅ |  |
| `coverage suggest` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `randomize extract` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `randomize list` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `randomize reachability` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `randomize trace` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `risk analyze` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `sva coverage` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `sva extract` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `sva timing` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |
| `verify gap` | — | verif | experimental | medium | ✅ | ✅ | ✅ |  |

## `dev` (3 个)

| 命令 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `expression build` | — | internal | debug | cheap | ✅ | — | ✅ |  |
| `expression cond` | — | internal | debug | cheap | ✅ | — | ✅ |  |
| `expression func` | — | internal | debug | cheap | ✅ | — | ✅ |  |

## `out` (2 个)

| 命令 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `fix imports` | — | mutating | mutating | cheap | ✅ | ✅ | ✅ | --write 会写 filelist → tools/ |
| `fix timescale` | — | mutating | mutating | cheap | — | ✅ | ✅ | --apply 会改 RTL (.sv) + .bak 备份 → tools/fix_timescale.py |

## 计划新增 (语义 core 缺口: instance 查询)

| 新命令 | 复用现有 API | 输出 |
|---|---|---|
| `instances` | UnifiedTracer.get_instances() | [{full_path,name,module_type,parent}] |
| `instance` | get_instances() + 端口/参数 | {full_path,module_type,ports[],param_overrides[],src_file,src_line} |
| `connections` | trace_module / trace_port | {inputs[],outputs[],internals[],cross_module[],confidence,caveats} |
| `hierarchy` | module_instance_graph (MIG) | {path,module_type,children[]}  ← arch show 的机器面 |

