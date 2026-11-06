# Long-range 统一 runner（P81）

**日期**: 2026-11-06
**状态**: runner + 单题 smoke 完成
**路径**: [tools/benchmark/run_long_range.py](../../tools/benchmark/run_long_range.py)

---

## 1. 目标

把 P69 的 12 题从“inline workflow + 临时目录”变成可重复 runner：

- source / T2 两边 hard sandbox；
- workspace 只含 RTL + 本地 filelist；
- T2 不能读 task JSON / ground truth / 旧 pilot artifact；
- source 不能读 repo / `/tmp/lr_pilot` / 执行 `sv_query`；
- source/T2 同 prompt、同 max query budget；
- 输出兼容 `score_long_range.py`。

## 2. 隔离

source：

- `source.sb`；
- deny repo、`/tmp/lr_pilot`、`/private/tmp/lr_pilot`；
- deny `sv_query` 执行。

T2：

- 新 `t2_long.sb`；
- deny `/tmp/lr_pilot`；
- deny repo `tools/benchmark`（task JSON/runner）和 `docs/validation`（答案文档）；
- 允许 repo `src/cli`（editable install 需要）和 `sv_query`。

实测：

```text
source: cat README.md                  -> Operation not permitted
source: sv_query --help                -> execvp ... Operation not permitted
t2:     cat tools/benchmark/...json    -> Operation not permitted
```

## 3. Workspace

每个 task/arm/seed 独立：

```text
/tmp/lr_long_hard/<model>/<task>/<arm>-s<seed>/
  axi/ or serv/ or picorv32.v
  <design>.f      # 本地绝对路径
  model.patch.yml # 从 repo 复制到 sandbox 内
```

filelist 不再指向 `/tmp/lr_pilot`。  
T2 的 `SVQ_CACHE_DIR` 也指向 workspace，避免旧缓存。

## 4. Smoke

任务：

```text
axi_araddr_neighbors
```

模型：DeepSeek-Flash；arms：source/T2；1 seed；budget 8。

| arm | result | seconds |
|---|---|---:|
| source | ✅ exact | 76.6 |
| t2 | ✅ exact | 86.5 |

两边答案：

```json
{
  "drivers": ["axi_adapter.axi_adapter_rd_inst.m_axi_araddr_reg"],
  "loads": ["axi_adapter.m_axi_araddr"]
}
```

source 额外输出了 `path/count`，但 scorer 只比较 required fields，仍为 exact。

## 5. 边界

- 只有 1 题 / 1 模型 / 1 seed；
- budget=8 只是 prompt 约束，未做硬 tool-call 限制；
- 尚未跑 12×3；
- `score_long_range.py` 仍是 exact-only；双评分未做；
- source 是“源码 + 本地 filelist”，不是人工标注；
- T2 仍可读 repo 的非 benchmark 源码（CLI 需要），需继续审计。

## 6. 下一步

先跑 4 个代表任务：

```text
axi_araddr_neighbors
serv_clk_path
pico_adapter_mem_valid_fanout
pico_adapter_rdata_fanin
```

2 模型 × 2 臂 × 2 seed = 32 agents，先验协议。

通过后再决定 12×3。
