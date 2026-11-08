# Iteration 417: Snapshot/evidence 一键化（P111）

**状态**: ✅
**日期**: 2026-11-08

## 完成

- `setup_snapshot.py`：snapshot + meta + env + optional install；
- AXI/SERV/Pico 新 snapshot；
- 5 任务 e2e 10/10，false-confident 0。

## 发现

第一次 e2e 因 runner 固定旧 `/tmp/lr_ad_snaps` 而 not_found；加 `snapshot_dir` 后通过。

## 下一步

P112 unknown/abstention/confidence 合同。
