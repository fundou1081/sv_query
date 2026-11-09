# P138 Project adaptation policy

**日期**: 2026-11-09
**决定**: 方案 A——core 不允许自动识别项目特定 FIFO
**结果**: 删除自动 FIFO 推断；保留通用 bit 聚合；提供外部 adapter 模板

---

## 1. 删除

- `src/trace/core/fifo_bridge.py`
- `src/trace/core/edge_visibility.py`
- `EdgeKind.FIFO`
- `UnifiedTracer.build_graph(include_fifo_edges=...)`
- `paths --through-fifo`
- FIFO 自动识别测试/fixture

因此：

```text
core 不再根据 module_type/instance 名包含 "fifo" 建边
core 不再按 wdata/rdata 端口名猜测
cross-FIFO 不在 core 承诺内
```

## 2. 保留

父总线 fanin 的 bit-slice 聚合保留（通用、不产生图边）：

```text
drivers(fmt_fifo_wdata) -> bit drivers
```

它是查询级聚合，不是自动 FIFO 语义。

## 3. 外部 adapter

模板：

```text
examples/project_adaptations/
  README.md
  opentitan_fifo/
    boundary_map.json
    validate_map.py
```

契约：

```json
{
  "src": "...",
  "dst": "...",
  "kind": "fifo_state",
  "evidence": "RTL file:line",
  "confidence": "medium"
}
```

要求：

- 显式调用；
- 不进入 `src/trace`；
- 有 source evidence；
- 不自动发现；
- 不修改 RTL。

## 4. 理念

新增 `AGENTS.md` 铁律 12 与
[PROJECT_ADAPTATION](../dev/PROJECT_ADAPTATION.md)：

> 项目适配不进 core 自动推断；core 只保留通用、可复核事实。

## 5. 验证

```text
check_semantic_regex ✅
check_docs / check_plan / check_cli_layers / check_crap ✅
无 FIFO 自动识别测试
父总线 bit 聚合测试保留
```
