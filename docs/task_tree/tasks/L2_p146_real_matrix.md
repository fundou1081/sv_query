# Task: P146 real-project agent matrix

**状态**: 进行中
**日期**: 2026-11-10

## 目标

在真实 OpenTitan UART/I2C 任务上验证 P139–P145 能力和 schema，收集 agent 使用问题。

## 分工

- P146.1 I2C：已有 3 个 frozen 任务 + frontier/boundary 场景；
- P146.2 UART：已有 5 个 frozen 任务 + deep path/unknown；
- P146.3 schema/UX adversarial；
- P146.4 issue triage。

## 边界

worker 只读；不自动推断 FIFO；真实 OpenTitan snapshot 是外部 fixture。
