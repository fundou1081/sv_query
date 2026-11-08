# Iteration 419: Contract regression（P113）

**状态**: ✅
**日期**: 2026-11-08

## 发现

- 普通 path 模型主动传 granular，导致绕路；
- setup 的 source root 对 AXI 推断错误；
- worker review 发现 F1-F4。

## 修复

- `deep_path` intent；path 永远最短；
- setup 从 filelist 推导 common source root；
- F1-F4 contract fixes。

## 结果

10/10 exact；false-confident 0；false-found 0。
