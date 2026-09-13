# Iteration 196: 可视化 flag 统一为 `--svg` (方豆决策执行)

**Metadata**:
- **Iteration #**: 196
- **Task Tree Level**: L2 (CLI 契约统一)
- **Parent Task**: 方豆决策 (2026-09-08): "可视化 flag 统一改为 svg, 不再支持 dot"
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ `--dot` 全仓清零 + 全量 3302 passed

## 🎯 本次目标

执行方豆决策: 可视化 flag 统一 `--svg`, **不再支持 `--dot`**; pipeline/timing 的验收
标准改为**文本结构化输出**, 可视化暂冻结。

## 📊 影响面 (实测, 先测后改)

| 面 | 数量 |
|---|---|
| CLI flag 定义点 (`--svg/--dot/-d` 别名) | 7 处 (graph/dataflow/pipeline/compute/timed/gap/chain) |
| 内部调用方 (`design.py` 传 `--dot`) | 2 处 |
| 测试引用 `--dot` | 57 处 / ≥12 文件 |
| 真 DOT 输出的 flag (与"不再支持 dot"冲突) | `visualize module/teach/datapath` + `timing` + `verify` |

**第一次试做时回退**: 只改 CLI 不同步测试 → 52 failed。本次一次做完"CLI + 测试 + 全量验证"。

## 🔬 实际结果

### 决策落地

| 命令类别 | 处理 |
|---|---|
| 输出 SVG 的 7 个子命令 | `--svg`/`--dot`/`-d` → **`--svg`**/`-d` (`--dot` 移除) |
| **真 DOT 输出**的命令 (`module`/`teach`/`datapath`/`timing`/`verify`) | `--dot` → **`--emit-dot`** (换名保留能力; 移出代替删除 — 若方豆要删可随时删) |
| 测试引用 | 按**命令边界**映射: 属 7 个 SVG 命令 → `--svg` (32 处); 属真 DOT 命令 → `--emit-dot` (3+22 处) |
| 文档 | README / docs 内示例同步 (17 处 `--svg` + 7 处 `--emit-dot`); **历史迭代记录不改** (时间点快照) |

结果: `grep '"--dot"' src sim/tests` = **0**; 全量 canonical **3302 passed / 0 failed**。

### 关键发现: `--svg` 被声明了两次 (潜伏 bug)

改完后 `test_visualize_chain.py` / `test_visualize_latency_golden.py` 等 9 个测试失败,
原因**不是**断言过时, 而是:

```python
# src/cli/commands/visualize.py (chain)
dot_output: str = typer.Option(None, "--svg", "--dot", "-d", help="Output SVG file (was DOT before V100...)")
...
svg_output: str = typer.Option(None, "--svg", help="Output SVG file (auto-call <engine> -Tsvg)")
```

`--svg` **声明两次** (内部渲染器 vs 外部 graphviz)。旧代码里 click 把 `--svg` 绑给
**后声明的** `svg_output`, 而测试一直用 `--dot` (deprecated 别名) 才能命中内部渲染器 ——
这正是"deprecated 别名"掩盖的真实缺陷: **主 flag 名指向了另一个实现**。
删除别名后行为立刻暴露。

修复: `svg_output` 的 flag 改名 **`--svg-graphviz`** (语义显式: 走外部 graphviz), `--svg`
唯一指向内部渲染器。→ 相关 44 个测试全绿。

### 未处理 (按方豆决策/边界)

- `src/trace/core/graph/signal_graph_viewer.py:848` 的 `--dot` (独立调试工具, 非 sv_query 主 CLI) — 保留, 已登记;
- PNG/SVG 断言: 按决策**冻结** (保持 iter_188 的 skip);
- 受影响测试文件里仍存在的被禁 `--no-strict` — **本次未清** (会牵动 fixture 语义), 单列后续任务。

## 💡 关键发现 / 关键技术 / 决策

1. **deprecated 别名会掩盖真缺陷**: `--dot` 别名"能用"这么久, 恰恰因为它绕开了
   `--svg` 的错误绑定; 删别名 = 让真问题可见。**删兼容层要留全量验证**。
2. **改名必须按"命令边界"映射**, 不能全局替换: 同名 flag 在不同子命令语义完全不同
   (7 个是 SVG 渲染, 5 个是真 DOT) —— 全局 sed 会静默改变行为。
3. **换名 vs 删除**: 真 DOT 输出的能力选择"换名保留"(`--emit-dot`), 符合项目
   "移出代替删除"的偏好; `--dot` 这个名字在全仓彻底消失, 满足决策。

## 📢 后续 (待方豆)

1. 文本结构化输出审计 (`pipeline`/`timing` 的 `--json` 覆盖与字段稳定性) — 这是决策里的新验收标准, 建议作为下一个主线;
2. 受影响测试文件的 `--no-strict` 清理 (AGENTS 纪律 1);
3. push (24 commit) / `check_regression.py` 阈值 / 上游 trap issue。

## 📎 关联

- 代码: `src/cli/commands/visualize.py`、`timing.py`、`verify.py`、`design.py`
- 测试: 12+ 文件 flag 同步 (`sim/tests/cli/**`, `sim/tests/usage/**`)
- 决策: `docs/architecture/ventus_viz_assertion_migration.md` (方豆决策节)
