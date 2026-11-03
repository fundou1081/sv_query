# Finding 局部 review artifact（P62.1）

**日期**: 2026-11-03
**状态**: 已实现（P62.1）；交互式 P62.2 未做

---

## 1. 命令

```bash
svq verify structural -f top.sv --json > findings.json

svq review render findings.json \
  --finding-id symmetry.port_set:b:top.u0 \
  -f top.sv \
  --svg out.svg \
  --html out.html \
  --json
```

- `review` 是 **exp / hidden**；不进入默认 capabilities；
- 输入必须是 `verify structural` finding（或直接 finding JSON）；
- `--finding-id` 省略时用第一条；
- 输出显式指定，不默认写文件；
- 无 `--svg/--html` 时把 SVG 打到 stdout。

## 2. 渲染原则

- 只消费 finding 的 `subgraph` 参数；
- 调 core `build_subgraph`，不重新实现遍历；
- 只画 finding 邻域（默认 ≤80 节点）；
- seed 蓝框；
- `actual.missing_instances` 生成红色虚线 synthetic stub（如 `top.u1.b`）；
- 标题包含 check/id/message；
- 简单分层布局，不依赖旧 VizData/ELK/Graphviz；
- 输出确定：两次同输入 SVG 字节一致。

## 3. 输出摘要

```json
{
  "ok": true,
  "command": "review_render",
  "finding_id": "symmetry.port_set:b:top.u0",
  "nodes": 6,
  "edges": 4,
  "missing": ["top.u1.b"],
  "svg": "out.svg",
  "html": "out.html"
}
```

## 4. 边界

- synthetic stub 只用于展示，不是图节点；
- 不做交互式展开；
- 不做全图/多 finding 拼图；
- 不做逻辑/时序证明；
- 布局是 review 辅助，不是 ELK 级可读性承诺。
