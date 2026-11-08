# Contract blind validation（P113）

**日期**: 2026-11-08
**范围**: 5 个 contract 任务 ×2 模型，使用 P111 新 snapshot
**最终结果**: 10/10 exact，0 false-confident，0 false-found

---

## 1. 任务

1. unknown signal → found=false
2. empty driver list → found=true / count=0
3. path no route → found=false
4. valid 2-hop path
5. source evidence file/line/source_line

任务文件：[tools/benchmark/blind_contract_2026-11-08.json](../../tools/benchmark/blind_contract_2026-11-08.json)

## 2. 过程中发现的两个真实问题

### 2.1 path 仍可被模型主动设成 granular

DeepSeek 在普通 path 任务里主动传：

```json
{"intent":"path","granular":true}
```

结果选了 14 节点绕路路径，而不是 3 节点最短路径。

修复：

```text
intent=path      永远最短
intent=deep_path 才选最长
granular 参数标记 deprecated（对 path 不再生效）
```

### 2.2 setup 的 source root 推断错误

AXI 源文件在：

```text
/tmp/lr_ad_prep/axi/axi/
```

但 P111 meta 写成：

```text
/tmp/lr_ad_prep/axi/
```

导致 evidence source_line 为空。

修复：

- `setup_snapshot.py` 从 filelist 实际文件路径推导 common root；
- 显式 `--source-root` 仍可覆盖；
- 重建 p111 snapshot 后 evidence 正常。

### 2.3 Worker 合同 review

MiniMax worker 发现：

- F1：`compactPath` 没检查 `ok:false`，可能返回 `status:ok/found:true`；
- F2：`E_SIGNAL_AMBIGUOUS` 未映射 ambiguous；
- F3：数值 `err.code` 被当成错误码；
- F4：`evidence_error` 缺 `evidence_available:false`。

已修复并有 71 个 Node tests。

## 3. 最终结果

| 模型 | exact | false-confident | false-found | mean wall |
|---|---:|---:|---:|---:|
| MiniMax-M3 | **5/5** | **0** | **0** | 6.6s |
| DeepSeek-Flash | **5/5** | **0** | **0** | 6.0s |

合计：

```text
10/10 exact
0/10 false-confident
0/10 false-found
```

## 4. 说明

- 这是修复后的 **regression**，不是完全盲测；
- 任务集在修复前已看过；
- 仍只有 5 个任务，不是外部 fault set；
- evidence 任务只验证了 file/line/source_line，不是完整语义证明。

## 5. 结论

```text
P112 合同 + F1-F4 + deep_path + source-root 修复后，
5 个 contract 任务全部正确且没有 false-found。
```

## 6. 下一步

- 用新任务集再做一次真正未调的 blind；
- 或者进入 P114：真实结构 debug 任务。
