# Task: P158 review remediation

**状态**: 待做
**日期**: 2026-11-11

## 输入

- [全面复盘/P158 账本](../../validation/REVIEW_2026-11-11.md)
- 4 个只读 worker：架构 / 产品 / 测试 / 性能

## 原则

- 一次只修一个语义契约；
- 每个修复必须有反事实测试和独立 oracle；
- 不把“0 skipped / 全绿”当完成标准；
- 真实项目 corpus 必须可执行。

## 顺序

1. 数据边策略 + CLOCK/RESET；
2. 路径 budget/timeout；
3. 确定性 + SPI corpus runner；
4. 写入安全 / truncated verified / snapshot 构造；
5. 测试真实性 / legacy / schema / CI；
6. 性能与清理。
