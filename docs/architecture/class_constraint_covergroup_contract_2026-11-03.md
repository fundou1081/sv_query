# class / constraint / covergroup 语义契约（P63）

**日期**: 2026-11-03
**状态**: 已实现（P63.1~P63.3）

---

## 1. class relations 增强

```bash
svq class packet --relations -f top.sv --json
```

新增字段：

| 字段 | 语义 |
|---|---|
| `constraint_blocks[]` | 约束块详情：id/vars/conditions/expr_count |
| `covergroups[]` | 该类（含祖先）定义的 covergroup 摘要 |

`covergroups[]`：

```json
{
  "name": "cg_env",
  "in_class": "tb_env",
  "clock": "",
  "coverpoints": ["cp_p"],
  "crosses": [],
  "instance_rule": "ctor_new",
  "file": "",
  "line": 0
}
```

---

## 2. `trace constraints <property>`

```bash
svq trace constraints packet.addr -f top.sv --json
svq trace constraints top.e.p.addr -f top.sv --json
```

- 类型级和实例级都支持；
- 不进入数据 fanin；
- 输出：

```json
{
  "result": {
    "property": "top.e.p.addr",
    "resolved": "top.e.p.addr",
    "count": 1,
    "constraints": [
      {
        "block": "packet.c_addr",
        "vars": ["packet.addr"],
        "conditions": [],
        "expr_count": 1
      }
    ]
  }
}
```

- 未知属性 → 非 0 + `ok=false`；
- 约束是声明式关系，不是“驱动”。

---

## 3. covergroup 命令

```bash
svq trace covergroups -f top.sv --json
svq trace covergroups --class tb_env -f top.sv --json

svq trace coverpoints top.e.p.addr -f top.sv --json

svq trace covergroup cg_env --instance top.e -f top.sv --json
svq trace covergroup cg_env --instance top.e --rand -f top.sv --json
```

### Q1 sampling

```json
{
  "result": {
    "mode": "sampling",
    "samples": [
      {
        "coverpoint": "cp_p",
        "signal_raw": "p.addr",
        "sampled": ["top.e.p.addr"],
        "drivers": ["top.din"],
        "missing": []
      }
    ]
  }
}
```

### Q2 reverse

```json
{
  "matches": [
    {
      "covergroup": "cg_env",
      "coverpoint": "cp_p",
      "in_class": "tb_env",
      "host_module": "",
      "ref_name": "p.addr",
      "select": "",
      "instance": "top.e"
    }
  ]
}
```

### Q3 rand → constraint

```json
{
  "result": {
    "mode": "rand",
    "links": [
      {
        "covergroup": "cg_env",
        "coverpoint": "cp_p",
        "property": "top.e.p.addr",
        "constraints": [
          {"block": "packet.c_addr", "vars": ["packet.addr"],
           "conditions": [], "expr_count": 1}
        ]
      }
    ]
  }
}
```

---

## 4. 边界

- covergroup 是观察域，不是数据流；采样链通过既有 fanin 委托；
- class cg 的 `--instance` 是数据端点；module cg 可省略；
- class cg 的 `ctor_new` / `uninstantiated` 静态判定沿用 CovergroupExtractor；
- inline constraint 仍不支持（见既有决策）；
- UVM factory/多态不做；
- 不修改 RTL/工程文件。
