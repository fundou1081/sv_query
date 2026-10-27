# 信号追踪能力评审（2026-10-27）

> **性质**: 阶段性能力盘点 + 缺口 backlog。不改代码，只记录证据与优先级。
> **触发**: 方豆"先停在这，更新文档。记录下来。然后再整体看，信号追踪功能还有什么需要加强。"
> **基线**: `main@9ada505`（iter_300），全量 **2489 passed / 0 failed**，35 命令（core 25 / view 10）。

## 1. 现在能做什么（已锁定契约）

| 能力 | 入口 | 状态 |
|---|---|---|
| 上游 driver（按位） | `svq drivers` / `trace fanin` | ✅ 位精确（见 §2） |
| 下游 load（按位） | `svq loads` / `trace fanout` | ✅ 位精确（见 §2） |
| 深度/跨模块/时钟/复位/控制边 | `--depth` / `--allow-cross-module` / `--include-clock|reset|control` | ✅ |
| 条件驱动 | `controlflow analyze` / `trace evidence` | ✅ |
| 实例层级/端口/参数 | `hierarchy` / `ports` / `instances` / `params` | ✅ |
| 图路径 | `paths` / `dataflow analyze` | ⚠️ 节点级（位节点 id 可工作，但无位过滤/保证） |
| 批量追踪 | `drivers/loads --batch` | ✅ JSON + 截断标记 |
| 设计体检 | `audit`（10 项，带 confidence） | ✅ |
| 图规模/缓存 | `stats` / 自动缓存（热 ~0.2s） | ✅ |

## 2. 位精确性矩阵（静态可判定部分，P5–P12）

| 形态 | 精度 | 证据 |
|---|---|---|
| 显式位赋值/位选/寄存器位/struct 成员位/generate | ✅ 位精确 | `test_bit_precision.py` |
| 切片 LHS/RHS/偏移/slice→slice | ✅ 位精确 | `test_bit_select_truth.py`、F3 |
| 位负载 fanout | ✅ 位精确 + 无负载回退 | `test_bit_precision.py` C3 |
| 总线端口/直接拷贝 | ✅ `one` 默认；纯总线 `full` 可选 | `test_bit_bridge_f4.py` |
| 表达式：位运算/加减乘/常量移位/Slice | ✅（位节点存在时；缺失回落总线） | `test_expr_bit_mapping.py` |
| 纯拼接/直接拷贝/常量源/常量位 | ✅ 位精确 | `test_bit_precision_p7.py`、`p8` |
| 有符号字面量/信号扩展 | ✅ 符号位/零扩展正确 | `test_signedness.py` |
| `integer/int/byte/shortint/longint/time` 宽度 | ✅ | `test_integer_width.py` |
| packed struct/union 聚合 + 成员位段 + 成员位桥 | ✅（`p.a[1]` → `p[5]`） | `test_packed_struct.py` |

## 3. 发现的缺口（按优先级）

### P0 — 静默错误（必须先修）

**C1. 图缓存 key 不含 `SVQ_BIT_BRIDGE` 模式** —— ✅ 已修（iter_302 / P13.1）
- 现象（实测）：默认 `one` 建图后，切 `full` 用同一份缓存 → 仍是 5 节点（应 37）；
  反方向 `full`→`one` 会拿到过度展开的图。
- 根因：`UnifiedTracer._graph_cache_key` = 内容 hash + `-v2-t{target}`，模式未入 key。
- 影响：同一工程切换模式后查询结果**静默错误**（不是慢，是错）。
- 修法：key 加 `-bb{one|full}`；补回归测试；无需再 bump `CACHE_VERSION`（key 变化自然失效）。
- 代价：小（1 行 + 1 测试）。

**C2. 粗粒度回退没有显式标记** —— ✅ 已修（iter_303 / P13.2）
- 现象：位查询在"位节点不存在/不支持"时回落总线，输出与位精确结果同形，agent 无法区分
  `fanin(p.a[1])` 返回 `{p}` 是"总线粒度回退"还是"真的只有总线驱动"。
- 影响：agent 可能把粗粒度答案当精确答案用。
- 修法：CLI JSON 每个 driver/load 加 `precision: "bit"|"bus"|"unknown"`（或结果级 `warnings`）；
  内部已有落点（`_expr_source_bits` 的 `None`/缺失分支）。
- 代价：中（需要标注传播，输出 schema 变更需版本策略）。

### P1 — 位精确性可继续推进

**A1. 深层 packed 成员节点（`o.inner.a`）** —— ✅ 已修（iter_305 / P13.4）
- 现象：成员补齐只到一层；`fanin(o.inner.a[1])` 空答。
- 修法：`_apply_packed_member_layout` 递归成员类型，建 `o.inner.a` 并挂 parent 链；
  查询层 `_packed_parent_step` 已支持多级。
- 代价：小~中（布局递归 + 测试）。

**A2. 三元/case 分支按位映射** —— ✅ 已修（iter_306 / P13.5，源位节点存在时）
- 现象（实测）：`s = c ? a : b; y=s[3]` → `fanin(y) = {s[3], a, b}`（分支总线级）；
  case 分支同样只到部分位。
- 修法：对同宽分支，`s[i]` 映射到 `a[i]`/`b[i]`（条件经 BRANCH/CONTROL 边保留）；
  不同宽/聚合分支保持总线。
- 代价：中（OP_TERNARY/BRANCH 边模型 + 测试）。

**A3. 静态 memory/数组的位精度**
- 现象：`mem[1]` 能作为元素节点（`fanin(y)={mem[1],d}`），但位查询 `y[3]` 停在校验层；
  动态索引 `mem[i]` 只能粗粒度。
- 修法：静态索引元素按普通信号参与现有位桥；动态索引显式标 `unknown`（见 C2）。
- 代价：中（元素节点宽度/位节点建图 + 动态标记）。

**A4. 多驱动语义**
- 现象：`assign y=a; assign y=b;` → `drivers(y[3])={a,b}`，无 `multi_driver` 标记/冲突提示。
- 修法：结果加 `driver_count` / `multi_driver: true`（不做 SV 解析求解，只暴露事实）。
- 代价：小。

### P2 — 查询面/可发现性

**D1. `capabilities` 缺位精确性契约** —— ✅ 已修（iter_304 / P13.3）
- agent 先读 `capabilities`，但不知道"哪些位查询可信、哪些会回落"。
- 修法：加 `bit_precision` 段（precise/coarse/env 模式/已知边界），与本文档同步生成。
- 代价：小。

**D2. 追踪输出缺 signedness/位段字段** —— ✅ 已修（iter_304 / P13.3）
- `_node_to_dict` 只有 id/kind/module/width/distance；P9 的 `is_signed`、packed 成员的
  `parent/bit_range` 未暴露，agent 无法判断扩展方向。
- 修法：输出加 `is_signed`/`parent`/`bit_range`（schema 版本 +1）。
- 代价：小。

**D3. 位级路径/影响分析**
- `paths`/`dataflow`/`impact` 是节点级；传位节点 id 可工作（实测 `a[1]→y[5]`），
  但没有 `--bits` 便捷入口，也不保证位节点存在（纯总线拷贝时）。
- 修法：加 `--bits` 归一化（缺失则显式 `precision=bus`）；impact 支持位过滤。
- 代价：中。

**D4. 环路/截断元数据**
- 遍历用 `seen` 防环，但结果不报告"遇到环"；长链无 `max_depth` 提示。
- 修法：结果加 `cycles_detected` / `truncated_by_depth`（与 `--max-results` 截断区分）。
- 代价：小~中。

### P3 — 已知限制/暂不做

- 比较/逻辑/归约：所有位都可能影响，位级不可分（保持总线粒度）。
- 变量移位 / 动态 part-select / 动态 memory 索引：运行期决定（显式 `unknown` 即可，不做求解）。
- 函数调用返回值：黑盒；可选做法是 inline（已有 `SubroutineExpander`，未接入查询）。
- `SVQ_BIT_BRIDGE=full` 超过 30000 新节点会部分展开（warning）；建议加 `graph_complete` 标记。
- 有符号算术/比较语义：位依赖规则不变，暂不建模。
- integer 算术逐位（进位链）：按方豆决定暂不做。

## 4. 建议执行顺序

| 顺序 | 项 | 理由 |
|---|---|---|
| 1 | C1 缓存 key 模式 | 唯一的"静默错误"，改动最小 |
| 2 | C2 粗粒度标记 + D1 capabilities 契约 | 让 agent 能正确解读结果，防止误用 |
| 3 | A4 多驱动标记 + D2 输出字段 | 小改动，直接提升可解释性 |
| 4 | A1 深层成员 / A2 三元分支 | 位精确性最后两块静态可做项 |
| 5 | A3 静态 memory / D3 位级路径 | 场景扩展 |
| 6 | P3 各项 | 视需求 |

## 5. 决策记录

- `SVQ_BIT_BRIDGE` 默认 `one`（2026-10-26 方豆拍板）——纯总线位精确需显式 `full`。
- integer 算术逐位暂不做（2026-10-27 方豆："算术逐位先不做"）。
- 本次评审只记录，不启动 P13 实现；`PLAN.md` 已登记 backlog，等方豆挑项开工。

## 6. 复核方式

```bash
# 全量门禁
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly
# 缓存模式 bug 复现（修复后应得到 37）
SVQ_CACHE_DIR=$(mktemp -d) python3 - <<'PY' ...
PY
```

（复现脚本见本次会话记录 / 迭代 `iter_301`。）
