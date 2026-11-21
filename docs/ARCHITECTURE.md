# sv_query architecture

> **状态**: 当前架构概览（2026-11-21）
> **入口**: agent 先读 [README](../README.md) → 本文 → [USER_GUIDE](USER_GUIDE.md)

## 1. 分层

```text
RTL / filelist / snapshot
  │
  ├─ pyslang semantic AST        src/sv_query/trace/core
  │    parser → semantic adapter → extractors
  │
  ├─ SignalGraph + MIG           src/sv_query/trace/core/graph
  │    nodes/edges: data, control, structural
  │
  ├─ query layer                 src/sv_query/cli/core
  │    drivers/loads, paths, dataflow, verify, scope, snapshot
  │
  └─ CLI / Session               src/sv_query/cli, src/sv_query/session.py
       JSON envelope, capabilities, stable error codes
```

CLI 与 Python Session 共用同一 registry 和 JSON contract；`sv_query` console
entry 是 `sv_query.cli._entry:main`。

## 2. 命令面

```text
45 canonical listed commands
39 default-visible
2 aliases
6 experimental (exp/)
32 standard envelopes / 13 direct envelopes
```

权威来源：

- [`capabilities --json`](agent/CAPABILITIES_GENERATED.md)
- [`src/sv_query/cli/_registry.py`](../src/sv_query/cli/_registry.py)
- 命令面变更 gate：`tools/check_command_surface.py --check`

core/exp 边界：

- `core`：只读、JSON、稳定 schema；
- `exp`：实验能力，不承诺兼容；
- 业务失败与调用失败使用不同的 rc/ok/error_code 约定，见
  [ENVELOPE_FAILURE_CONTRACT](dev/ENVELOPE_FAILURE_CONTRACT.md)。

## 3. 语义契约

数据边、路径、`verified` / `unknown`、snapshot 行为以
[SEMANTIC_CONTRACTS](dev/SEMANTIC_CONTRACTS.md) 为唯一真相源。

关键不变量：

- CLOCK/RESET 是时序注解，不是数据边；
- 搜索预算耗尽 → `is_reachable=null` / `unknown`，不写 false；
- sample/truncated 不得标成 `verified`；
- 位级追踪只在已建模算子/连接上成立；比较/变量移位等仍是总线粒度；
- 输出证据分级见 [CLAIMS](dev/CLAIMS.md) 与 [KNOWN_LIMITATIONS](KNOWN_LIMITATIONS.md)。

## 4. 代码布局

```text
src/sv_query/trace/core/      parser / semantic adapter / extractors / graph
src/sv_query/trace/core/graph/models.py    SignalGraph
src/sv_query/trace/core/graph/contracts.py edge 分类唯一实现
src/sv_query/cli/core/        CLI query implementations
src/sv_query/cli/_registry.py command/JSON contract registry
src/sv_query/session.py       Python Session contract
sim/tests/                    canonical + integration + usage tests
docs/                         contracts, validation, user docs
```

## 5. 证据与验证

- [CLAIMS](dev/CLAIMS.md)：公开能力与 gate 对应关系；
- [TESTING](../TESTING.md)：canonical 命令与测试语义；
- [docs/validation/](validation/)：真实验证证据（CVA6 案例、release、snapshot 等）；
- `tools/run_gates.sh`：提交前全门禁。

## 6. 历史文档

旧架构快照已从公开树移除，保存在私有归档；本文不再维护“已过期”正文。
