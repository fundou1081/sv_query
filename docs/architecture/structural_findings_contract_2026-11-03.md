# `verify structural` findings 契约（P61）

**日期**: 2026-11-03
**状态**: 已实现（P61.1~P61.3）
**计划**: [structural_review_plan_2026-11-02.md](structural_review_plan_2026-11-02.md) §6

---

## 1. 命令

```bash
svq verify structural -f top.sv --json
svq verify structural -f top.sv --max-findings 100 --json
```

当前只实现一个 check：

```text
symmetry.port_set
```

语义：

> 同一 parent、同一 module type 的 sibling 实例，某个直接子端口只在一部分 sibling 上有 CONNECTION。

这是**结构候选**，不是功能证明；不假设不同 parameter 实例的端口宽度必须相同。

---

## 2. 返回

```json
{
  "ok": true,
  "command": "verify_structural",
  "params": {...},
  "result": {
    "findings": [],
    "total": 0,
    "truncated": false,
    "checks": [
      {"check": "symmetry.port_set", "status": "pass", "checked": 3, "findings": 0}
    ]
  },
  "errors": []
}
```

finding：

```json
{
  "id": "symmetry.port_set:b:top.u0",
  "check": "symmetry.port_set",
  "severity": "warning",
  "confidence": "medium",
  "message": "1/2 sibling instance(s) missing port 'b'",
  "seeds": ["top.u0", "top.u1"],
  "expected": {"port": "b", "connected_instances": ["top.u0"]},
  "actual": {"missing_instances": ["top.u1"]},
  "evidence": [
    {"src": "top.b", "dst": "top.u0.b", "kind": "CONNECTION",
     "condition": "", "expression": ""}
  ],
  "subgraph": {
    "seeds": ["top.u0", "top.u1"],
    "depth": 1,
    "direction": "both",
    "edge_kinds": ["connection", "driver"]
  }
}
```

规则：

- 每条 finding 必须带证据；
- `subgraph` 是 **参数**，不是图数据；可直接喂给 `graph subgraph`；
- `confidence=medium`：同 parent/module 的端口集合差异是强结构信号，但未连接端口可能是设计意图；
- `status=fail` 只表示发现候选，不是功能错误；
- `max-findings` 是硬上限，`truncated` 显式。

---

## 3. 边界

- 不做 width/source/name 启发式（parameter 不同可能合法）；
- 不做功能等价/时序等价；
- 不覆盖 generate 之外的全局命名约定；
- 后续可扩展：`symmetry.source_pattern`、`connection.width`、`typo.candidate`。

---

## 4. 与其它 verify 的关系

| 命令 | 语义 |
|---|---|
| `verify consistency` | 图结构不变量（全图/bit/connection） |
| `verify claim` | 单条 claim 可反驳验证 |
| `verify structural` | 局部模式/对称性候选 |
