# Envelope Inventory — P182.1a (read-only)

> **状态**: P182.1a 只读盘点；不是 gate。成功/失败/未知/截断矩阵留给 P182.1b。
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
  standard: 33 = core standard 27 + exp standard 6
  direct:   12（全部 core）
别名:      2 (trace fanin → drivers, trace fanout → loads)
```

## 2. standard 信封

33 个 standard 命令预期：

```json
{"ok": true, "command": "...", "params": {}, "result": {}, "errors": []}
```

失败路径应带 `ok:false` 和 `error_code`/`errors`；具体矩阵在 P182.1b 验证。
部分命令按 contract 带 `optional_top_level`：`graph subgraph` 的 `seeds`、
`trace evidence` 的 `evidence`、`controlflow list-conditioned` 的 `subcommand`；
P182.1b 的严格键集断言必须放行这些合法键。

## 3. direct 信封（12 个）

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
| `paths` | `envelope=direct`（contract）vs registry `standard` | **非 standard：根含 ok/src/dst/...，无 command/params/result/errors**（实测 scheduler_minimal） |
| `snapshot save` | `result_fields` | 未在 A 阶段采样 |
| `snapshot list` | `result_fields` | **list**（契约与根类型不一致） |
| `snapshot compare` | `result_fields` | 未在 A 阶段采样 |
| `snapshot delete` | `result_fields` | 未在 A 阶段采样 |

**已发现的不一致**：

- `paths`：registry 写 `envelope=standard`，但 `JSON_CONTRACT` 写 `direct`，
  实测根也不是 standard（无 `command/params/result/errors`）；工具用
  `envelope_mismatches: ["paths"]` 暴露，不在 A 阶段改 registry；
- `snapshot list --json` 实际根是 `list`，但静态契约写 `result_fields`；
- direct 命令并非一种形状：有 object、有 list，也有带/不带 `ok` 的 object；
- `capabilities` 没有 `ok`，但有 `schema_version`。

这些必须在 P182.1b 决定：补 `ok`、改契约，还是显式 allowlist。

## 4. 使用边界

```bash
# 只读盘点；不执行命令、不改输出
python3 tools/check_envelope_contract.py --inventory
python3 tools/check_envelope_contract.py --inventory --json
```

## 5. 不能从这个盘点得出的结论

- 不能据此声称“所有命令成功路径一致”；
- 不能据此做 rc/ok 一致性 gate；
- 不能把 direct 的 static contract 当成实际输出；
- 不能用它替代真实 fixture 的 P182.1b 矩阵。

下一步：P182.1b 先对 **core 的 27 个 standard** 做成功/失败 gate；
exp 6 条按降级通道单独处理；12 个 direct 例外逐个裁决（含 `paths` 与 `snapshot list` 双根）。
