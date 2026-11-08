# Deep chain tool probe（P103）

**日期**: 2026-11-08
**范围**: 受限 `svq_query` + deep_chain snapshot + 3-step protocol
**结果**: 工具协议执行成功，但语义答案错误

---

## 1. 协议

只允许 `svq_query`，固定 3 个调用：

1. `path top.din -> top.dout`
2. `neighborhood top.u_mid.u_stage.u_leaf.d depth=2`
3. `neighborhood top.u_mid.u_stage.mixed depth=1`

然后返回：

```json
path / hop_count / register / xor_node / mux_control / mux_node / combinational
```

## 2. 实际答案

```json
{
  "path": [
    "top.din",
    "top.u_mid.d",
    "top.u_mid.u_stage.d",
    "top.u_mid.u_stage.u_leaf.d",
    "top.u_mid.u_stage.u_leaf.q",
    "top.u_mid.u_stage.leaf_q",
    "top.u_mid.u_stage.mixed",
    "top.u_mid.u_stage.q",
    "top.u_mid.q",
    "top.mid_q",
    "top.dout"
  ],
  "hop_count": 10,
  "register": "top.u_mid.u_stage.u_leaf.q",
  "xor_node": null,
  "mux_control": "top.u_mid.u_stage.sel",
  "mux_node": "top.u_mid.u_stage.u_leaf.d.ternary_sel",
  "combinational": true
}
```

## 3. 与 ground truth 对比

| 字段 | 期望 | 实际 |
|---|---|---|
| path | 包含 ternary，11 hops | 绕过 ternary，10 hops |
| hop_count | 11 | 10 |
| register | `...u_leaf.q` | ✅ |
| xor_node | `...u_stage.mixed` | ❌ null |
| mux_control | `...u_stage.sel` | ✅ |
| mux_node | `...u_leaf.d.ternary_sel` | ✅ |
| combinational | false | ❌ true |

## 4. 解释

- `path` 工具返回最短路径，绕过了 ternary 节点；
- `neighborhood` 返回了 mux 节点和条件，但模型没有把三元节点插入路径；
- `xor_node` 未被识别为 XOR；
- 路径含 REG，但 `combinational=true` 是明确错误；
- 3 个调用本身执行成功，无 bash/JSON 访问。

## 5. 结论

```text
受限工具能执行协议；
但 deep_chain 不能只靠“path + neighborhood 原始结果”自动合成。
```

需要：

1. `path` 返回节点 kind / condition / 可选 granular 路径；
2. 或新增 `drive_chain` intent，由工具展开 ternary/reg；
3. 或返回 `paths --all` 变体，让工具选“最细粒度且合法”的路径。

## 6. 状态

```text
P103 deep_chain tool probe: 负结果
不设为默认接口
```
