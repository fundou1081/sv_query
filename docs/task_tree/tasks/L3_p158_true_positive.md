# Task: P158.8 true-positive / legacy tests

**状态**: ✅ 完成
**日期**: 2026-11-11

## 结果

- bit_mapping 增加真实宽度/range 不一致的 true-positive；
- reciprocity 增加真实不对称的 true-positive（fake tracer）；
- legacy snapshot（strip `module_graph`）显式 unknown 回归恢复；
- 数据边 mutation 测试已在 P158.1 添加。
