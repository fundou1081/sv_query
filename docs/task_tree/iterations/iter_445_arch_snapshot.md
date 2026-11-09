# Iteration 445: P136.2 architecture snapshot

**状态**: ✅
**日期**: 2026-11-09

## 实现

`architecture graph --from-snapshot TAG`：
- INSTANTIATED_MODULE → 节点；
- PORT_* → 端口方向；
- CONNECTION → 连接；
- 不 parse、不依赖 MIG。

## 验证

I2C 5 instances / 37 connections / 189 boundaries；
4 architecture tests passed。

## 边界

旧 snapshot 无新增 FIFO 边；snapshot 缺失端口不补。
