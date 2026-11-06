# Iteration 382: P0 post-P77 deep_chain 行为验证（PLAN P78）

**状态**: ✅ 完成
**日期**: 2026-11-06

## 设置

- 3 模型 × 1 seed × deep_chain；
- 隔离 workspace；至少 4 轮 query。

## 结果

| 模型 | rounds | 结果 |
|---|---:|---|
| MiniMax-M3 | 7（clarify 后） | ✅ 12/11, mux_node, canonical control, comb=false |
| MiniMax-M3.1-Flash | 5 | ✅ |
| DeepSeek-Flash | 8 | ✅ |

第一次 M3 prompt 字段歧义（combinational=true / mux_control=sel / xor 表达式），
澄清后通过。P77 工具本身被 3 模型正确使用。

## 结论

- port ternary 从 unknown 升级为完整证据；
- `paths --canonical` 12 节点 / 11 hops；
- 字段契约必须明确；
- 仍单 seed，不宣称模型排名。
