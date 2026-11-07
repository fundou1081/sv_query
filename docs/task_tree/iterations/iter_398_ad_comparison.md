# Iteration 398: A+D vs 原版模型对比（P94）

**状态**: ✅
**日期**: 2026-11-07

## 运行

- A+D：pruned filelist → snapshot → T2 `--from-snapshot`；
- 12 题，2 模型，seed1，24 cells；
- source/原版 T2 复用 P87。

## 结果

- T2 准确率：原版 24/24，A+D 24/24；
- mean wall：MiniMax 68.6→239.4s，DeepSeek 32.5→74.4s；
- A+D 更慢；
- 部分 agent 直读 snapshot JSON / repo run_cli.py，协议不干净。

## 结论

A+D 不提升准确率，也不降低总延迟；保持显式工具，不设为默认。
