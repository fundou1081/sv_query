# Task: long-range 查询协议修复（P83）

**状态**: 已完成
**目标**: 修 P82 的 T2 direct-query 失误，并验证。

## 修复

- T2 prompt 强制 `--depth 1`；
- 最终 JSON 强制 `queries`；
- runner 检查 query log；
- 跑前确定性 fact check；
- 修 `paths` direct envelope / SERV fact check；
- source prompt direct vs terminal。

## 结果

- 4 题 × 2 模型 × 2 臂 × 2 seed；
- T2 16/16；source 11/16；
- T2 0 high-confidence error；
- T2 query log 11/16（DeepSeek 5 个答案对但没报 query）。
