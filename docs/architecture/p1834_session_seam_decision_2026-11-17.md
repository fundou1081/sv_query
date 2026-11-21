# P183.4 Session seam — full-dispatch decision (2026-11-17)

**状态**: 决策（ADR），D15 收口  
**范围**: 是否把 CLI 的 Typer `run()` 全量重写为 `Session.execute` dispatch  
**结论**: **不重写**。保留现有 Session seam + read-only runner + hidden `session` 命令；
完整 dispatch 在有新的 transport/常驻调用需求前不立项。

---

## 1. 背景

P183.4 的原始评审建议：

```text
Session.execute(request: dict) -> response: dict
run() 降为它的 CLI adapter
RequestContext / BuildOptions 取代 sys.argv / _QUIET / _ACTIVE_CONFIG
```

D10–D14 已交付的内容：

| 子项 | 交付 |
|---|---|
| D10 | `sv_query.Session.execute`，version op，结构化错误 |
| D11 | `Session(handlers=...)`；capabilities 命令经 Session |
| D12 | 层中立错误码 + CLI 单一 failure adapter |
| D13 | 唯一只读 runner (`run_session`) |
| D14 | hidden `session --request JSON` transport adapter |

## 2. 选项

### A. 全量重写 Typer `run()` 为 Session dispatch

- 需要把 40+ 条 Typer 命令的 argv 解析、全局态、错误信封、help/surface 全部迁移；
- `capabilities` / `CLI_SURFACE` / 分层门禁依赖 Typer introspection；
- 目前没有第二个 transport 消费者（无 serve/MCP/batch 计划）；
- 一次重写会同时改 CLI 成功/失败契约，违反 D10–D14 子项验收及 CLAIMS C-24/C-25 的逐字节承诺。

**成本**: 高；**收益**: 当前零消费者下的理论统一；**风险**: 大范围回归。

### B. 保留 seam，按需扩展（采纳）

- Session 保持 transport-agnostic；
- 只读命令通过单 runner 接入；
- hidden `session` 命令是通用入口，可用于测试/未来 transport；
- 全量 Typer dispatch 只在出现真实需求时另立计划；
- RequestContext / `_QUIET` / `_ACTIVE_CONFIG` 统一同理推迟，已登记到 `KNOWN_LIMITATIONS §3.17`。

**成本**: 已支付的是 Session seam 与 adapter 管道；**未支付**的是 38 条 core 命令的查询面暴露与 `RequestContext/BuildOptions` 全局态收敛。**收益**: 可用的库层 + CLI adapter；**风险**: 两套入口共存，需要文档和约束。

## 3. 决策

采纳 **B**。

具体边界：

1. `Session` 是库层请求/响应契约；不 import CLI；
2. CLI 读取路径统一走 `cli._session_runner.run_session`（当前 capabilities）；
3. hidden `session --request` 是 transport adapter，不是 Typer 的替代入口；
4. 全量 `run()` 重写不进入 P183.4；若未来需要 serve/MCP/常驻调用，另立计划；
5. RequestContext 全局态收敛不在本计划内。

## 4. 可观察后果

| 场景 | 现状 |
|---|---|
| 库调用 | `Session(...).execute({...})` 可用，无 CLI 依赖 |
| CLI 现有命令 | 仍走 Typer；成功输出不变 |
| capabilities 失败 | 经唯一 `fail_from_session`；畸形 Session 响应更严格 |
| hidden session | 可执行 version/capabilities；不进入 capabilities/help/counts；`request_id` 当前未透传 |
| 库查询面 | 当前只覆盖 `version` / `capabilities`，38 条 core 命令尚未经 Session 暴露 |
| 错误容器 | **本次裁决**：库 dict / CLI string 按 transport 保留分叉，暂不统一；后果是同一失败在两层可见不同 `error` 类型 |
| 全局态 | `_QUIET` / `_ACTIVE_CONFIG` 仍存在，未收敛；完整 CLI 命令仍受进程全局态影响（Session 的 version/capabilities 自身不读它们） |

## 5. 开放项（D15 明确留给后续）

| 项 | 处置 |
|---|---|
| `request_id` 在 hidden session 成功响应中被丢弃 | 若 future transport 需要关联，补 `run_session`/response 透传；不属于 D15 |
| hidden dev 命令物理位于 `src/sv_query/cli/core/locate/`，但登记为 dev | 分层工具的目录判定与 registry 语义不一致；D15 记录，未来整理 CLI 目录时处理 |
| `Session` 第二个构造点（capabilities 与 session_cmd） | D15 保留；抽出 `build_session()` 可减少重复 |
| `run_session` 的 Session Protocol / 畸形响应裸 TypeError | D15 记录；未来 transport 扩展时统一 |
| 全量 38 条 core 命令的 Session 查询面 | 未支付；只有出现 serve/MCP/常驻调用需求时才立项 |

## 6. 后续触发条件

只有在以下任一条件成立时才重新评估全量 dispatch：

- 需要 serve/MCP/batch 或非 CLI transport；
- 需要多请求 Session 生命周期/隔离；
- CLI 命令数或入口形态发生结构性变化；
- 有明确的 agent 端到端用例要求统一入口。

## 7. 证据

- `docs/dev/CLAIMS.md` C-23/C-24/C-25；
- `agents/review-minimax/reviews/R-D10.md` … `R-D14.md`；
- `src/sv_query/session.py`、`src/sv_query/cli/_session_runner.py`、`src/sv_query/cli/core/locate/session_cmd.py`；
- canonical 3015 (current) passed（D14 收口）。
