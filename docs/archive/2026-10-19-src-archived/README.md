# 归档: `src/` 内的历史可视化渲染器 (2026-10-19)

**来源**: `src/trace/core/graph/viz/_archived/` + `src/trace/core/graph/viz/_archived_dot/`
**体积**: 19 文件 / 约 4,270 行
**原因**: [核心代码坏味道评审 A1](../../refactoring/2026-10-19_core_smell_review.md)

## 为什么归档

这两个目录在 `src/` 里已经存在许久，但：

1. **无任何 import**（唯一的例外是 `sim/tests/unit/test_viz_data.py` 里 4 条
   `render_dot` 测试，随本次归档一并删除——它们测的是已下线的 DOT 渲染器）
2. 却被 `pyproject.toml` 的 `packages.find include = ["src.*", ...]` **打进 wheel**
3. 占 `trace/core/graph/viz` 模块的 **40%**（viz 总计 8,226 行）

结果是"grep 到两套实现、度量失真、新同学改到死代码"。

## 里面是什么

| 目录 | 内容 | 说明 |
|---|---|---|
| `_archived/` | `control_tree.py` / `elk_svg_renderer.py` / `viz_dataflow_new.py` / `viz_signal_new.py` / `elk_render.js` | ELK 迁移期的旧渲染路径 |
| `_archived_dot/` | 12 个 `viz_*_renderer.py` + `viz_style.py` | Graphviz DOT 时代的渲染器（V6.7 起由 `VizData` + ELK 取代） |
| `function_expander.py` | 131 行 | 原本在 `src/trace/core/builder/`，全仓 0 引用（`builder/__init__.py` 也不导出） |
| `cli_dev/expression.py` | 255 行 | 原 `src/cli/dev/`；iter_252 移除 `expression build/func/cond` 三个命令（内部调试、0 测试、`--file` 路径从未实现），模块整体归档 |

| `signal_graph_viewer.py` | 895 行 | 原 `src/trace/core/graph/`；全仓 0 import，且**自带的 `__main__` 跑不通**：`render_dot` 读 `self.config["node_style"]["show_type"]`，而 `configure()` 从不设置该键 → `KeyError: 'show_type'`（实测，移动前就坏） |

## 现在的渲染路径

```
SignalGraph → build_viz_data() → VizData → viz_to_elk() → ELK 布局 → render_svg() → SVG
```

对应 `src/trace/core/graph/viz/` 下仍在用的模块（`viz_data_builder` / `viz_data_models` /
`elk_bridge` / `viz_engine`）。

CLI 侧仍有 DOT 输出能力（`trace fanin --format dot`、`visualize ... --dot`），
但它们由各自命令内联生成，**不依赖**本目录任何文件。

## 若要恢复

`git log --follow` 可追到移动前的历史；本目录保留原相对结构，可整体移回。
恢复前请先确认有真实调用方——归档的直接原因是"没有调用方"。
