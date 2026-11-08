# svq_query 是否设为默认（P109）

**日期**: 2026-11-08
**决策**: **可选默认（opt-in profile），不做全局默认**

---

## 1. 支持设为默认的证据

- direct 12 题：24/24；
- tool-only，每 cell 1 次调用；
- wall 约 4–9s；
- mux 结构/条件正确；
- deep_chain 7/7（含 evidence 复核）；
- 默认关闭 evidence，成本不变；
- evidence=true 成本约 +2%。

## 2. 还不能全局默认的原因

- 需要预构建 snapshot；
- evidence 需要 `SVQ_SOURCE_ROOT`；
- 只覆盖 fanin/fanout/neighbors/path/neighborhood/evidence；
- 没有 MIG/connections/instances；
- 12 题是手工结构任务，不是真实 debug 全集；
- deep_chain/mux 是单例验证，不是批量 benchmark；
- 失败时仍可能语义错（不是协议错）。

## 3. 决策

```text
作为“结构查询 profile”的可选默认：
  - snapshot 可用；
  - 只做结构查询；
  - 需要 evidence 时显式开启。

不作为全局默认：
  - 不替代语法/编译/仿真；
  - 不替代真实 debug；
  - 不默认加载 evidence。
```

## 4. 落地

- 保留 [svq_query.patch.yml](../../tools/agent/svq_query.patch.yml) 作为 opt-in；
- 默认 CLI / 普通 agent 不变；
- README 明确适用条件；
- 后续有 3–5 个真实结构任务后再评估全局默认。

## 5. 结论

```text
现在可以推荐“在结构查询场景用 svq_query”，
但不能说“所有 agent 任务默认用它”。
```
