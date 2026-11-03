# Task: finding 局部 review artifact（P62.1）

**状态**: 已完成（P62.1）
**计划**: [structural_review_plan_2026-11-02.md](../../architecture/structural_review_plan_2026-11-02.md) §7

## 目标

- 读取 `verify structural --json` 的 finding；
- 用 finding.subgraph 参数调 `graph subgraph`；
- 只渲染 finding 邻域为 SVG/HTML；
- 高亮 seed、缺失端口 stub、finding 文本；
- 不恢复全设计图，不复制旧 VizData/ELK。

## 命令（暂定）

```bash
svq review render findings.json --finding-id <id> \
  -f top.sv --svg out.svg --html out.html
```

## 边界

- 不做交互式展开（P62.2 gate）；
- 不做全图布局；
- 只消费 subgraph 数据，不重新遍历图。
