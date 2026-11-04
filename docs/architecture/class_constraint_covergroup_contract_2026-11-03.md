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

---

## P64：constraint 继承链 + rand 标记（2026-11-04）

### class member

`class <name>` / `class <name> --relations` 的 `members[]` 新增：

| 字段 | 语义 |
|---|---|
| `is_rand` | 是否 `rand` / `randc` |
| `rand_mode` | `Rand` / `RandC` / `None` |
| `type` | 声明类型文本（如 `int` / `bit[7:0]`） |

继承成员会从父类复制 `rand/type`；如果约束先把它建成了 SIGNAL
placeholder，继承传播会升级为 CLASS_PROPERTY。

### trace constraints

`constraints[]` 新增：

| 字段 | 语义 |
|---|---|
| `defined_in` | 约束块定义类；继承块为父类 |
| `inherited` | 是否来自父类 |
| `rand_vars` | 被约束的 rand 属性 |

例：

```json
{
  "block": "child.c_base",
  "vars": ["child.x"],
  "defined_in": "base",
  "inherited": true,
  "rand_vars": ["child.x"]
}
```

### 边界

- 继承约束按 class graph 的复制块报告；
- `super.c1` 调用仍只有 SUPER_CALL 边，不做执行语义；
- `rand_mode()` 运行时开关不建模；
- `randc` 只标 `rand_mode=RandC`，不建模周期状态。

---

## P65：UVM sequence/factory 静态关系（2026-11-04）

`class <name> --relations` 新增 `uvm` 字段：

```json
{
  "role": "sequence|sequence_item|component|object|null",
  "base_kind": "uvm_sequence",
  "is_uvm": true,
  "factory_registration": {
    "registered": true,
    "macro": "uvm_object_utils",
    "type": "my_seq",
    "line": 28,
    "confidence": "syntactic"
  },
  "factory_creates": [
    {
      "kind": "type_id_create",
      "target": "my_item",
      "instance_name": "req",
      "line": 11,
      "confidence": "syntactic"
    }
  ],
  "sequence_calls": [
    {"kind": "macro", "macro": "`uvm_do", "argument": "req",
     "line": 32, "confidence": "syntactic"}
  ],
  "p_sequencer": "my_sequencer",
  "source": {"file": "uvm_relations.sv", "line": 27}
}
```

### 语义

- role 由 class 祖先匹配 UVM 基类；
- registration / calls 从 **类源码文本** 提取（preprocessor 会把宏从 semantic syntax 去掉）；
- 所有 call/registration 都是 `syntactic`，不证明运行时实际执行。

### 不做

- factory override / config_db；
- phase/sequence 调度执行；
- UVM package 依赖分析；
- 动态 factory 字符串解析。
