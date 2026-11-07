# Iteration 395: top-aware filelist 裁剪（P91 / A）

**状态**: ✅
**日期**: 2026-11-07

## 实现

- `trace/core/top_prune.py`：保守文本扫描 + top 闭包；
- `sv_query filelist prune`：JSON / 显式 `--output`；
- 注释/string/单引号 literal 处理；
- 5 个测试。

## 实测

- AXI：55→3，first query 27.3s→0.84s；
- SERV：24→17，path 3.4s→1.23s；
- AXI/SERV 8 个任务结果一致。

## 边界

文本扫描，不处理 macro 生成模块/bind/config；显式 opt-in，失败应回退完整 filelist。
