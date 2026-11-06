# Task: 复杂 constraint / 复杂 mux 邻域场景（P84）

**状态**: 已完成
**目标**: 测试“追踪 + 提取信号图邻域信息”：
1. complex random constraint 关系；
2. complex RTL mux 关系。

## 交付

- 2 个 fixture；
- deterministic CLI truth + tests；
- agent interactive 场景；
- 1 seed pilot，记录邻域字段。

## 边界

- 先验证邻域提取，不扩全量；
- nested mux/constraint 若工具不支持，显式记录 unknown。
