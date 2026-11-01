# Iteration 346: 模拟 waveform 端到端（PLAN P45）

**Metadata**:
- **Iteration #**: 346
- **Task Tree Level**: L2（PLAN `P45`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "用模拟测试来串接"）
- **Outcome**: ✅ 完成（8 paths e2e；2700 passed）

## 🎯 目标

用一组模拟 waveform 完整路径串起：
`$root / generate / interface / modport / struct member / bit / not_found`。

## 🔧 修复

1. `resolve_signal` 支持 `$root.` 前缀（全局，不只是 lookup）；
2. packed struct 成员节点 name 只有成员名、parent 指向父总线时，
   type 解析走 parent member layout。

## 🧪 测试

`test_waveform_end_to_end.py`：
- manifest total=8，found=7，failed=1；
- `$root` canonical；
- generate/interface/modport/struct/bit；
- not_found profile=null；
- 全量 **2700 passed / 0 failed**。

## ⚠️ 边界

- 模拟 fixture，不是真实波形工具输出；
- `top.not_here` 是故意失败用例；
- 真实 vendor genblk/零填充仍需样例。

## 🔗 相关

- 计划: [PLAN.md P45](../../../PLAN.md)
