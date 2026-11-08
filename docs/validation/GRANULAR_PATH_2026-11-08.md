# Granular path（P104）

**日期**: 2026-11-08
**范围**: `svq_query intent=path` + deep_chain 复测
**结果**: path/hop/register/mux/combinational 修复；xor_node 仍缺

---

## 1. 实现

`path` 不再只取最短路径：

```text
sv_query paths <src> <dst> --all --max 20 --directed --from-snapshot ...
```

compact 规则：

```text
选择节点数最多的变体；
节点数相同按字典序 tie-break；
返回 path / count / variants / truncated。
```

Node tests：23/23。

## 2. deep_chain 复测

3 个固定调用后：

```json
{
  "path": [
    "top.din",
    "top.u_mid.d",
    "top.u_mid.u_stage.d",
    "top.u_mid.u_stage.u_leaf.d.ternary_sel",
    "top.u_mid.u_stage.u_leaf.d",
    "top.u_mid.u_stage.u_leaf.q",
    "top.u_mid.u_stage.leaf_q",
    "top.u_mid.u_stage.mixed",
    "top.u_mid.u_stage.q",
    "top.u_mid.q",
    "top.mid_q",
    "top.dout"
  ],
  "hop_count": 11,
  "register": "top.u_mid.u_stage.u_leaf.q",
  "xor_node": null,
  "mux_control": "top.u_mid.u_stage.sel",
  "mux_node": "top.u_mid.u_stage.u_leaf.d.ternary_sel",
  "combinational": false
}
```

对比：

| 字段 | 期望 | 实际 |
|---|---|---|
| path | 12 nodes / 11 hops，含 ternary | ✅ |
| hop_count | 11 | ✅ |
| register | `...u_leaf.q` | ✅ |
| mux_control | `...u_stage.sel` | ✅ |
| mux_node | `...u_leaf.d.ternary_sel` | ✅ |
| combinational | false | ✅ |
| xor_node | `...u_stage.mixed` | ❌ null |

## 3. 剩余问题

`mixed` 在图中是 SIGNAL，工具没有表达式/op 类型，无法从现有结果识别它是 XOR。  
这不是 path 粒度问题，而是 **表达式语义** 缺口。

## 4. 回归

3-cell tool smoke：

```text
6/6 exact
MiniMax 3.8–6.8s
DeepSeek 4.2–4.5s
```

## 5. 结论

```text
granular path 修复了 deep_chain 的 path/hop/register/combinational；
xor_node 仍需表达式语义，不能靠路径解决。
```

下一步：
1. 若要 xor_node，给工具加 `expression_kind` 或 `node_detail`；
2. 否则把 deep_chain 的 xor 字段视为未支持；
3. 继续用 worker 补 Node 测试。
