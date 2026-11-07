# 受限 svq_query 工具 pilot（P98）

**日期**: 2026-11-07
**范围**: 3 个代表 cell ×2 模型；DeepSeek 完成，MiniMax 因配额 429 未完成
**性质**: 工具接口 pilot，不是模型排名

---

## 1. 实现

新增 DSH 工具：

[tools/agent/svq-query-tool](tools/agent/svq-query-tool)

参数：

```text
intent: fanin | fanout | neighbors | path
snapshot: prebuilt tag
signal / dst
depth
```

工具内部：

- 只调用 `sv_query`；
- 不接受 shell / source / filelist；
- fanin/fanout 返回紧凑 ID 列表；
- `neighbors` 一次返回 drivers+loads；
- path 返回 canonical path 和 hop count。

配套 patch：

[tools/agent/svq_query.patch.yml](tools/agent/svq_query.patch.yml)

同时禁用：

```text
bash / read / grep / skill
```

所以 agent 只剩 `svq_query` 可用。

---

## 2. 结果：DeepSeek

| cell | 原版 T2 | 工具 |
|---|---:|---:|
| AXI araddr | 65.9s ✅ | **4.1s ✅** |
| SERV clk path | 46.9s ✅ | **6.2s ✅** |
| Pico adapter fanout | 22.9s ✅ | **4.4s ✅** |

工具每 cell 只调用一次：

```text
axi:  svq_query intent=neighbors
serv: svq_query intent=path
pico: svq_query intent=fanout
```

DSH session 中没有 bash/read/grep 调用。

准确率：

```text
3/3 exact
```

---

## 3. MiniMax

3 个 cell 都是：

```text
RATE_LIMIT: 429 Token Plan 用量上限
```

不是语义失败。  
当前无法完成 MiniMax 对照。

---

## 4. 解释

这次不是“prompt 更好了”，而是：

```text
工具面收窄
→ 没有搜索空间
→ 一次调用完成
```

对比之前：

- A/D prompt：agent 搜索、读 JSON、反复试探；
- skill/inline：模型仍探索；
- 受限工具：直接调用，4–6s。

## 5. 边界

- 1 模型、1 seed、3 cells；
- DeepSeek 结果；MiniMax 配额阻塞；
- 原版 T2 是“source 可见 + CLI 自由”的接口，不是完全同输入；
- 快照由外部预构建；
- 只覆盖 fanin/fanout/neighbors/path；
- 不支持 connections/instances（快照无 MIG）；
- 不能据此做模型排名。

## 6. 下一步

1. MiniMax 配额恢复后跑同一 3 cells；
2. DeepSeek 扩到 12 cells；
3. 若 12 cells 稳定，考虑把它作为默认 agent 接口；
4. 不再做 prompt/skill 变体。
