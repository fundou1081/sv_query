# Iteration 387: long-range 查询协议修复（P83）

**状态**: ✅
**日期**: 2026-11-07

## 修复

- T2 prompt 强制 `--depth 1` + `queries`；
- runner query-log 检查；
- 跑前 fact check；
- 修 paths direct envelope / SERV fact check；
- source prompt direct vs terminal。

## 结果

4 题 ×2 模型 ×2 臂 ×2 seed：

- source 11/16；
- T2 **16/16**；
- T2 0 high-confidence error；
- T2 query log 11/16（DeepSeek 5 个缺 query）。

## 结论

协议修复后 T2 在这组 direct tasks 上明显更好；  
仍是 4 题、direct query，不是通用 debug 结论。
