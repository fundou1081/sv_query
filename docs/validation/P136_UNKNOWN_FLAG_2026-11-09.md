# P136.4 unknown machine-readable flag

**日期**: 2026-11-09
**问题**: `verify claim` 的 `unknown` 只有 reason 字符串，agent 无法机器区分
“端点不存在”与“无法证明”
**结果**: 增加 `machine.unknown_kind` / `machine.unresolved_endpoint`

---

## 1. Schema

当 `status == "unknown"` 时：

```json
{
  "status": "unknown",
  "reason": "signal '...' not_found",
  "machine": {
    "status": "unknown",
    "unknown_kind": "unresolved_endpoint",
    "unresolved_endpoint": true
  }
}
```

分类：

```text
unresolved_endpoint
  reason 含 not_found / not found / missing / does not exist

unverifiable
  其他 unknown（如 bit claim 只有父总线、无法判定）
```

`verified` / `contradicted` 不添加该字段，保持原 schema。

## 2. 代码

`_claim_result()` 统一生成：

```text
status/reason/evidence/counterevidence
machine (仅 unknown)
```

不改变 CLI 的人类输出。

## 3. 验证

```text
test_verify.py: 12 passed
unknown-bit claim 断言 machine.unknown_kind
```

## 4. 仍未做

`trace constraints` 的 `solve…before` / `dist` 权重尚未提取。
这不是 unknown flag 的一部分，单独列为 P136.5。
