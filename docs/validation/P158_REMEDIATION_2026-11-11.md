# P158 review remediation (wave 1)

**日期**: 2026-11-11
**状态**: P158.1–P158.6 完成；P158.7–P158.12 待做

---

## P158.1 数据边契约

新增唯一实现：

```text
src/trace/core/graph/contracts.py
DATA_EDGE_KINDS = {DRIVER, CONNECTION}
CONTROL_EDGE_KINDS
STRUCTURAL_EDGE_KINDS
```

`PathResolver` / `DataFlowGraph` / `verify` 共用：

```text
paths --directed          data only
verify claim type=path    data only
dataflow analyze          data only
paths (无向)              structural connectivity, mode="structural"
```

### 修复前 / 后

```text
paths top_minimal.sa1.clk top_minimal.sa1.ready_q --directed
before: found=true, 1 hop, path [clk, ready_q]
after:  found=false, mode=data

verify claim type=path 同一对
before: verified
after:  contradicted

dataflow analyze 同一对
before: is_reachable=true, latency=1
after:  is_reachable=false, paths_count=0
```

真实数据对仍通过：

```text
top_minimal.valid_i -> top_minimal.sa1.valid_i
found=true / verified
```

回归：`test_p158_data_edge_contract.py`，含 mutation（放宽 DATA_EDGE_KINDS 必须让 guard 变红）。

---

## P158.2 有界路径枚举

`PathResolver.find_all_paths_detailed`：

```text
max_expansions (work budget)
deadline (wall-clock)
truncated / truncation_reason / expansions
```

CLI：

```text
paths --max-expansions N --timeout S
```

结果不再静默截断，也不把预算耗尽伪装成 found:false。

SPI 7.6k 节点：

```text
before: >30s / 无输出
after:  0.6s, found=true, truncated=true,
        truncation_reason=max_expansions_reached
```

---

## P158.3 构建确定性

根因：

```text
SemanticAdapter._genvar_context / _primitive_genvar_context
用 id(pyslang wrapper) 作 key。
pyslang wrapper 是临时对象；GC 复用地址后不同 AST 节点撞 key，
genvar/scope context 错位 → 同一输入建出不同图。
```

原 worker 尝试用源码位置做 key，但 generate-for 的多个展开项共享源码位置，
导致 genvar context 全变成同一个值（测试 18 failed）。已回退该方案。

最终修复：

```text
登记 context 时同时持有 wrapper 引用（_ast_ctx_refs），
使 id() 在 context 生命周期内唯一；不改变原有 per-entry id 语义。
```

结果（同一 SPI 源/filelist，连续 3 次）：

```text
before: 7618/7620 nodes, 12375/12377 edges
after:  7621 nodes, 12377 edges（三次一致）
```

回归：`test_determinism.py` + `test_ast_identity.py`（失败路径为 id-keyed context 回归）。

---

## P158.4 SPI corpus runner

新增：

```text
tools/agent/run_spi_corpus.py
sim/tests/regression/test_spi_corpus_runner.py
```

9 tasks / 9 pass；runner 真实执行 CLI，错误 expected 会失败，malformed task 不会被跳过。

T2/T7 在 P158.1 后按数据路径重新定标：

```text
T2: 4 hops / 2 candidates -> 3 hops / 1 candidate
T7: 2 hops / 2 candidates -> 1 hop / 1 candidate
```

原因：ternary select 是 control edge，不再是数据 segment；真实 RTL oracle 仍是
`spi_host.sv:160` 的 mux，但数据路径只算 DRIVER/CONNECTION。

---

## P158.5 / P158.6

- `filelist prune --output` 默认 dry-run；`--apply`；只允许 `.f/.fl`；
  已存在需 `--force` + `.bak`。
- `verify consistency` 顶层 `verified` 要求 `coverage_complete`，sample/truncated
  时返回 `verified:false`、`partial_checks`。

---

## 验证

```text
2665 passed / 0 skipped / 141 deselected / 0 failed
```

SPI snapshot：

```text
nodes = 7621
edges = 12377
MIG = present
```

corpus：

```text
9/9 pass
```
