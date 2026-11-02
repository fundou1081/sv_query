# Task: 取实例 width（P53）

**状态**: 已完成
**来源**: 方豆指出 "应该取实例的 width"；P52 目前用 module 定义 width 传播，parameter 不同会错。

## 可验证目标

1. 同一 module type 两个实例不同参数 → 两个实例节点 width 不同；
2. 优先从实例 body 的声明/端口提取 width；
3. module 定义 width 只作 fallback；
4. 测试 + 全量门禁 + 文档。
