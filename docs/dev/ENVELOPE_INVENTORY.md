# Envelope Inventory — P182.1a (read-only) + P182.1b canary + P182.1c matrix

> **状态**: P182.1a 只读盘点；P182.1b phase 1 在其上增加 7-case canary gate；
> P182.1c phase 1 增加 26 个 core standard 成功矩阵（`paths` 已归 direct）。
> 当前树矩阵结果：**26 PASS + 0 FAIL**；`filelist prune` 成功路径已补 `errors`。
> `paths` 已从 standard 归到 direct。truncated（P182.1d）、direct（P182.1e）、exp 仍未覆盖；
> 失败输入盘点见 [ENVELOPE_FAILURE_INVENTORY](ENVELOPE_FAILURE_INVENTORY.md)（只读、非 gate）。
> **计数来源**: `python3 tools/check_envelope_contract.py --inventory --json`
> **实际根来源**: A 阶段人工采样（§3 注明命令/fixture；不是工具输出）
> **日期**: 2026-11-18

## 1. 总量

```text
列出命令 (listed): 45
  core:   39
  exp:     6
  (另有 1 条 hidden dev `session`，不进入盘点)
信封计数按 listed 45 条：
  standard: 32 = core standard 26 + exp standard 6
  direct:   13（全部 core）
别名:      2 (trace fanin → drivers, trace fanout → loads)
```

## 2. standard 信封

32 个 standard 命令预期：

```json
{"ok": true, "command": "...", "params": {}, "result": {}, "errors": []}
```

失败路径应带 `ok:false` 和 `error_code`/`errors`；具体矩阵在 P182.1d 验证。
部分命令按 contract 带 `optional_top_level`：`graph subgraph` 的 `seeds`、
`trace evidence` 的 `evidence`、`controlflow list-conditioned` 的 `subcommand`；
P182.1c 的严格键集断言放行这些合法键（只要求必备键存在，不要求键集相等）。

## 3. direct 信封（13 个）

| 命令 | 静态契约 | 已知实际根 |
|---|---|---|
| `instances` | `fields/item_fields/error_fields` | object（ok/count/module/instances） |
| `connections` | `fields/item_fields/error_fields` | 未在 A 阶段采样 |
| `hierarchy` | `fields/node_fields` | 未在 A 阶段采样 |
| `params` | `fields/item_fields/error_fields` | 未在 A 阶段采样 |
| `ports` | `fields/item_fields` | 未在 A 阶段采样 |
| `class` | `fields/instance_fields/member_fields` | 未在 A 阶段采样 |
| `search` | `fields/file_fields/line_fields` | object（keyword/target/files） |
| `capabilities` | `result_fields` | object（schema_version/layers/...） |
| `paths` | `envelope=direct`（registry + contract 一致） | direct：根含 ok/src/dst/...，无 command/params/result/errors |
| `snapshot save` | `result_fields` | 未在 A 阶段采样 |
| `snapshot list` | `result_fields` | **list**（契约与根类型不一致） |
| `snapshot compare` | `result_fields` | 未在 A 阶段采样 |
| `snapshot delete` | `result_fields` | 未在 A 阶段采样 |

**已发现的不一致**：

- `snapshot list --json` 实际根是 `list`，但静态契约写 `result_fields`；
- direct 命令并非一种形状：有 object、有 list，也有带/不带 `ok` 的 object；
- `capabilities` 没有 `ok`，但有 `schema_version`；
- `drivers`/`loads` 未知 signal：`ok=false` + `E_SIGNAL_NOT_FOUND`，但 **rc=0**（P182.1c 未 gate）。

这些必须在 P182.1d/P182.1e 决定：补 `ok`、改契约，还是显式 allowlist。

## 4. 使用边界

```bash
# 只读盘点；不执行命令、不改输出
python3 tools/check_envelope_contract.py --inventory
python3 tools/check_envelope_contract.py --inventory --json

# P182.1b phase 1 canary：执行 7 条固定用例（scheduler_minimal），违规 exit 1
python3 tools/check_envelope_contract.py --canary

# P182.1c phase 1 矩阵：26 个 core standard 成功路径（显式 manifest），违规 exit 1
python3 tools/check_envelope_contract.py --matrix-core

# P182.1d phase 1 失败盘点：26 个命令各一条失败输入；只读观测，恒 exit 0
python3 tools/check_envelope_contract.py --failure-inventory
python3 tools/check_envelope_contract.py --failure-inventory --json

# P182.1f 失败契约 gate：严格 rc1+okfalse + 4 条 hybrid allowlist，违规 exit 1
python3 tools/check_envelope_contract.py --matrix-failure
```

canary 覆盖：`stats` / `drivers` / `loads` / `graph nodes` / `graph edges` /
`controlflow analyze` 的成功信封，以及 `stats --file <nonexistent>` 的失败信封。

matrix-core 覆盖全部 26 个 core standard 命令的成功路径，每条 case 固定
`command + argv + fixture`；fixture 均为仓库既有文件，argv 取自现有测试/文档。
成功断言：rc=0、根 object、含 `ok/command/params/result/errors`、`ok=true`、
`errors` 为 list。`trace tb-join` 需要快照，矩阵在临时目录内先执行
`snapshot save`（setup），不复用用户快照。

当前树真实结果（2026-11-18）：

| 结果 | 数量 | 说明 |
|---|---|---|
| PASS | 26 | 全部 core standard |
| FAIL | 0 | — |

`filelist prune` 成功路径已补 `errors: []`；`paths` 的 registry 已改为
`envelope=direct`，由 P182.1e 处理，不混入 standard 矩阵。

它不是 failure/unknown/truncated 矩阵，也不覆盖 direct / exp。

## 5. 不能从这个盘点得出的结论

- 不能据此声称“所有命令成功路径一致”；
- 不能据此做 rc/ok 一致性 gate；
- 不能把 7-case canary 当成 26 个 core standard 的全量 gate；
- 不能把 direct 的 static contract 当成实际输出；
- 不能用它替代真实 fixture 的 P182.1c 矩阵。

下一步（P182.1e）：失败盘点在
[ENVELOPE_FAILURE_INVENTORY](ENVELOPE_FAILURE_INVENTORY.md)（只读），严格失败契约与
4 条 hybrid 例外在 [ENVELOPE_FAILURE_CONTRACT](ENVELOPE_FAILURE_CONTRACT.md)；
exp 6 条按降级通道；13 个 direct 例外逐个裁决（含 `paths` 与 `snapshot list` 双根）。
