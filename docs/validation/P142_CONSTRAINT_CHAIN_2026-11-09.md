# P142 random variable constraint chain

**日期**: 2026-11-09
**状态**: ✅

## 命令

```bash
sv_query trace constraint-chain rnd_item.a rnd_item.d \
  -f constraint.sv --json
```

## 语义

两个 random 变量之间的最短 **constraint co-membership** 链：

```text
variable
→ constraint block
→ variable
→ ...
```

不是 solver 证明，不是数据流。

## 输出

```json
{
  "found": true,
  "source": "rnd_item.a",
  "target": "rnd_item.d",
  "rand": {"rnd_item.a": true, "rnd_item.d": true},
  "hop_count": 3,
  "chain": [
    {"kind": "variable", "id": "rnd_item.a"},
    {"kind": "constraint_block", "id": "rnd_item.c_ab",
     "from": "rnd_item.a", "to": "rnd_item.b", "via": "var"},
    {"kind": "variable", "id": "rnd_item.b"},
    "..."
  ],
  "blocks": ["rnd_item.c_ab", "rnd_item.c_bc", "rnd_item.c_cd"],
  "note": "constraint co-membership only; not a solver proof"
}
```

## 规则

- 端点必须是 `rand`；否则 `endpoint_not_random`；
- 无连接 → `no_constraint_path`；
- 条件变量边标 `via="condition"`；
- 支持 type 级和可解析的实例级属性；
- 输出链和 block 列表，不只给一个布尔值。

## 测试

```text
test_constraint_chain.py: 5 passed
```

覆盖多跳、condition 边、非 random 端点、无路径、未知端点。
