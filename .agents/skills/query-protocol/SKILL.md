# query-protocol — RTL 查询入口与命令选择

## 1. Use when / Do NOT use when

**Use when**

- 需要用 `sv_query` 回答 RTL 结构/层级/驱动/路径/verify 问题；
- 需要决定“该用哪个稳定命令”，而不是猜命令名；
- 需要把查询结果交给后续 agent 消费。

**Do NOT use when**

- 需要修改 RTL/filelist/工程文件 → 停手；
- 需要功能正确性证明或形式化验证 → 不在 `sv_query` 范围；
- 只是维护本仓库代码 → 用 `add-component` / `debug-fault` / `code-cleanup`。

## 2. Preconditions

- 有 `--file` 单文件或 `--filelist`；filelist 必须用 `--filelist`，禁止用 `-f` 传。
- 需要 snapshot 时先确认 tag 存在；`snapshot list` 可查。
- 不假设命令存在；先读生成物。

## 3. Command selection

1. 先跑：
   ```bash
   sv_query capabilities --json
   ```
2. 读生成的能力表：
   ```text
   docs/agent/CAPABILITIES_GENERATED.md
   .agents/skills/query-protocol/references/capabilities.md
   ```
3. 按 `group` / `envelope` / `recommended` 选择稳定 core 命令；
   不把 `exp` 当稳定入口。

> 能力表是生成物，禁止手改；漂移由 `tools/gen_agent_skill.py --check` 抓。

## 4. Query protocol

- 成功判断：先看 `ok`，再看退出码；`found=false` 是数据，`ok=false` 是失败。
- 所有查询加 `--json`；需要稳定字段时以 `JSON_CONTRACT` 为准。
- 批量/逐信号失败：区分 operational failure（rc=1）与文档化的 hybrid 例外。
- 不把 `sample` / `truncated` / `unknown` 写成 `verified`。
- 不跨 FIFO/自定义语义边界自动推断；需要显式 boundary map。

## 4b. Bit-select hints

总线查询可能只回答 bus 节点；当 JSON 带以下字段时，**不要**把 false/empty 直接读成“无影响”：

```json
"has_bit_select_drivers": true,
"bit_nodes": [{"id": "...[7:4]", "parent_bus": "...", "bit_range": {...}}]
```

```json
"bit_node_paths_exist": true,
"bit_node_paths": [{"from": "...[7:4]", "path_count": 1}]
```

协议：

1. bus 级 false/empty 先看 hint；
2. 有 `bit_nodes` 就查对应 slice 的 `drivers` / `controlflow analyze --evidence`；
3. dataflow 的 `is_reachable=false` 仍是 false，不改成 unknown；
4. 结论用 `verify claim` 钉死；
5. 大项目用 snapshot 复用图。

## 5. Output interpretation

| 现象 | 含义 |
|---|---|
| `ok=true` / 空数组 | 查询成功，确实没有匹配 |
| `ok=false` / `found=false` | 目标不存在或未解析，不能当空结果 |
| `truncated=true` | 结果被预算截断，不能声称完整 |
| `status=unknown` | 证据不足，不能声称 verified |

## 6. Hard stop

- 需要写用户 RTL / 工程文件；
- 命令不在 capabilities 中；
- 失败被要求隐藏或降级；
- 结果被要求写成比证据更强的结论。

## 7. Self-check

- [ ] 先读了 `capabilities --json`；
- [ ] 命令来自生成表，不是猜的；
- [ ] 用 `--filelist` 传 filelist；
- [ ] 用 `ok` / `found` / `truncated` 正确解释；
- [ ] 没有把 unknown/partial 写成 verified。
