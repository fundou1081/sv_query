# Constrained verify claim（P117）

**日期**: 2026-11-08
**状态**: 完成
**结果**: 3 claims ×2 模型 = 6/6，单次 verify 调用

---

## 1. Core：snapshot 上的 verify

`sv_query verify claim` 新增：

```text
--from-snapshot TAG
```

与 `--file/--filelist` 互斥；不重新解析 SV，直接加载 snapshot graph。

测试：

```text
pytest -q sim/tests/cli/test_verify.py
12 passed
```

覆盖：

- verified；
- contradicted；
- unknown；
- snapshot 路径；
- 双向 path；
- bit/connection。

## 2. Tool：intent=verify

```json
{
  "intent": "verify",
  "snapshot": "p111_axi",
  "claim": {
    "type": "driver",
    "signal": "axi_adapter.s_axi_awready",
    "driver": "axi_adapter.axi_adapter_wr_inst.s_axi_awready"
  }
}
```

输出：

```json
{
  "ok": true,
  "status": "ok",
  "verify_status": "verified|contradicted|unknown",
  "claim": {},
  "reason": "",
  "evidence": [],
  "counterevidence": []
}
```

注意：

- `status` 是工具运行状态，固定 `ok`；
- `verify_status` 是 claim 结论，保留三态；
- contradicted/unknown 不是 tool error。

## 3. Claim pilot

任务文件：

[tools/benchmark/verify_claims_2026-11-08.json](../../tools/benchmark/verify_claims_2026-11-08.json)

3 个 claim：

1. true driver；
2. false driver；
3. missing signal。

结果：

| 模型 | exact | false-confident |
|---|---:|---:|
| MiniMax-M3 | 3/3 | 0 |
| DeepSeek-Flash | 3/3 | 0 |

```text
6/6 exact
每 cell 1 次工具调用
```

## 4. 过程问题

首轮 4/6：

```text
missing signal claim
→ tool verify_status=unknown
→ prompt 的通用 fallback 要求 found:false/reason:not_found
→ 模型把 verify unknown 改写成 not_found
```

这是 **benchmark prompt 问题**，不是工具错误。  
修正 prompt：verify 任务必须把 `verify_status`（含 unknown）保留，不能改成 found:false。  
重跑后 6/6。

## 5. 边界

- 3 个 claim，仅 driver 类型；
- 没有 connection/bit/path claim 的 agent 验证；
- 没有 CDC two-flop 这类真实 refutation；
- 仍是 snapshot-only；
- 不能证明通用 debug。

## 6. 结论

```text
query → evidence → verify 的 agent 闭环第一次打通。
verify 现在是受限工具的一等 intent。
```

## 7. 下一步

- 用 connection/bit/path 各 1 个 claim 做扩展；
- 或做 CDC anti-hallucination claim：two-flop synchronizer claim 应 contradicted/unknown。
