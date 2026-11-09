# Iteration 441: Module/instance architecture graph（P133）

**状态**: ✅
**日期**: 2026-11-09

## 实现

- 从 MIG ports + SignalGraph CONNECTION 边构建 module/instance 图；
- 同 parent net 聚合端口，按 output/input 方向生成边；
- `architecture graph` 输出 JSON/DOT/SVG；
- 默认折叠 prim_*、隐藏 clock/reset/boundaries，可显式打开。

## 验证

- synthetic pair: 1 real net edge；
- OpenTitan I2C `i2c_core --depth 1`: 5 instances / 37 connections；
- `test_architecture.py`: 2 passed。

## 边界

不是全信号图；参数化端口/多驱动/inout 仍受连接提取边界影响。
