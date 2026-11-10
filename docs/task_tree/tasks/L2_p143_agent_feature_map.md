# Task: P143 agent feature inventory

**状态**: ✅ 完成
**日期**: 2026-11-09

## 交付

- `docs/agent/AGENT_FEATURE_MAP.md`；
- 40/40 core JSON 命令，按 workflow 分类；
- 每命令：解决问题、输入、result 字段、坑、示例；
- schema 合同规则 + 9 个 unresolved 歧义；
- worker 独立盘点，main 核对覆盖集合。

## 边界

只收 core 稳定 schema；不含 exp/view/dev/out；
不把未核实字段写成事实。
