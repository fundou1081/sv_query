# Iteration 424: OpenTitan UART real-project pilot（P118）

**状态**: ✅（负结果）
**日期**: 2026-11-09

## Worker

standalone `opentitan-pilot`（MiniMax-M3）建图 `hw/ip/uart`：
60 files，4803 nodes，0 elaboration errors，7.6s。

## Agent

5 tasks ×2 模型：6/10 exact；T1/T2/T4 成功。

## 核心问题

- T3 evidence 返回 node declaration line43，而不是 assignment line306；
- T5 题目 schema 歧义；
- path canonical 歧义；
- 依赖闭包需手工整理。

## 结论

真实项目可建图；edge-level evidence 是核心阻塞。
