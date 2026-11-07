# Iteration 396: snapshot D（P92）

**状态**: ✅
**日期**: 2026-11-07

## 实现

- snapshot 加载时补 PathResolver（MIG=None）；
- `paths --from-snapshot`；
- A fallback：`trace drivers/loads --prune` 自动回退完整 filelist。

## 实测

- AXI snapshot 18MB；save 27s；load fanin 0.54s；path 0.49s；
- SERV snapshot 4.5MB；save 3.46s；path 0.23s；
- `queries`/snapshot 结果与 live 一致。

## 边界

snapshot 不含 MIG，connections/instances/hierarchy 不支持；evidence 源码退化。
