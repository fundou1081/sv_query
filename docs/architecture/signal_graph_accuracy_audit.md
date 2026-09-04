# Signal Graph 准确性审计清单 (2026-09-03)

> **维护**: 在语义边界前提 (Semantic-only 限 RTL 顶层域; SVA/procedural/inline =
> hybrid 例外域, 见 `inline_constraint_semantic_unavailable.md`) 下, 逐条验证
> signal graph 结果不准确处。**每条 = 可复现现象 + 源码位置**。
> **规则**: 修复后把条目移到"已修复"并注明迭代; 新发现在此登记。

---

## 🐛 未修复

### A1. 无 target_module 时 generate 实例内部逻辑缺失 (严重)

**现象**: `build_graph(target_module=None)` (CLI `--module` 缺省) 时, generate-for
实例内部的 assign/always 不提取 — 实例内部信号只在 connection 层 (端口自环)。
**证据** (cordic fixture `golden_dataflow_39`):
- `target=None`: 542→365 节点, rotator 内部 DRIVER 150→75 (75 全是 connection 端口自环, 真内部 0)
**源码位置**:
- `src/trace/core/graph_builder.py:68` — `_configure_instance_paths` 仅在
  `if self.target_module:` 下跑; None 时 driver 无实例路径
- `src/trace/core/driver_extractor.py:1287` — `if self._instance_paths:` 为假 →
  else 旧路径按模块类型名提取 (generate 内实例从不作为 (path,module) 处理)
**触发**: CLI `visualize dataflow` 不传 `--module` (默认 None,
`src/cli/commands/visualize.py:260`)、或任何 API 调用不设 target。
**修复方向**: target=None 时自动选首 top 作为 target (等价 `target_module=tops[0]`),
或 CLI 缺省补 module。已在 iter_113/114 修 driver 下钻, 只差"默认启用"。
**影响**: 真实项目无 module 参数时, 图缺整棵子实例内部逻辑 (darkriscv/picorv32 等)。

### A2. 子模块输出总线直连顶层总线位时, 顶层位无 DRIVER (中)

**现象**: `sub u_sub(.y(y))` 且 sub 输出总线位由内部 assign 驱动, 顶层 `y[3]`
查询"谁驱动" = ∅ (真源 `top.a[3]` 链: a[3]→u_sub.a[3]→(assign)→u_sub.y[3]→
(CONNECTION 总线)→top.y[3] 不贯通)。
**证据** (两模块 bus passthrough fixture):
- `top.y[0..3]` 位驱动全空; `top.u_sub.y ← {u_sub.a, u_sub.y(自环)}`; 只有
  `('top.u_sub.y','top.y')` 总线级 CONNECTION, 无位级 CONNECTION/DRIVER
**源码位置**:
- `src/trace/core/connection_extractor.py:567-577` (边2) — instance port →
  parent wire 只按**总线名** (inst_port_id/parent_signal 是 `...y` 非 `...y[3]`),
  不做位展开
- 位级查询依赖 bit nodes 的 BIT_SELECT + DRIVER, 跨实例位→位无桥
**修复方向**: 总线级 CONNECTION 两侧按端口位宽展开为位对位 CONNECTION
(或查询层把 bus CONNECTION + 位宽传播作为 fanin 一跳)。
**影响**: "顶层输出总线某位谁驱动" 回答为空 — 门级/总线直连真实设计 (KS 加法器等)。

### A3. 端口 DRIVER 自环计入驱动源 (轻微, 设计标记)

**现象**: 实例输出端口节点自带 DRIVER 自环 (`...u_sub.y -DRIVER-> ...u_sub.y`,
"模块内部驱动"标记 [FIX 2026-07-08])。fanin(端口) 会把它自身列为一个源;
按 DRIVER 集合相等断言的场景需手动排除 (本项目 truth 测试都写了排除)。
**源码位置**: connection/driver 端口处理 — 自环标记 (connection_extractor 边1
`src=child_signal_id dst=inst_port_id DRIVER internal` 邻域 / port 自环创建处)。
**性质**: 设计内 (标记内部驱动存在), 但作为"驱动源"语义易误读 — 建议查询层
排除自环或改走独立 marker 边。

---

## ✅ 已修复 (历史, 防止复发复登)

| 条目 | 修复迭代 | 位置 |
|---|---|---|
| generate RHS 位选丢索引 (总线当源) | iter_118 | semantic_adapter `_extract_signals_from_expr` |
| 索引段加倍假节点 | iter_117 | connection_extractor `get_path` gen_block 去重 |
| generate 实例连接 per-entry 丢失 (legacy 覆盖/key 碰撞) | iter_119/120 | connection_extractor 逐实例路径 |
| RangeSelect (+:) 连接命名恒 '?' | iter_119 | semantic_adapter `_conn_expr_to_signal` |

---

## 🔭 待验证候选 (未实测, 勿当结论)

- inout / 双向端口建模 (驱动器归属)
- struct/union 字段驱动 (member-level)
- interface/modport 信号 (iter_121 option 污染同区, 信号侧未审)
- 派生时钟 / 多时钟域提取 (clock domain)
- 顶层输入端口 fanin 语义 (外部驱动, 图内无源 — 属预期但需文档)
