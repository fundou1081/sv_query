# SNAPSHOT_SURFACE — 快照能力面矩阵（P158.9.2，2026-11-11）

> 验收标准（arch_eval P0.2 采纳）：快照缺失的字段**要么补齐、要么显式声明不保证**，
> 不许中间态。本文档是快照能力面的**单一权威清单**；改动 to_dict/from_dict 或
> 命令的 snapshot 支持时必须同步本文档。
>
> 契约依据：[SEMANTIC_CONTRACTS §3](SEMANTIC_CONTRACTS.md)；测试锁定：
> `sim/tests/unit/test_p158_9_2_snapshot_surface.py`。

## 1. 字段级矩阵（SignalGraph 往返）

实测基线：`minimal_3module`（31 nodes / 72 edges，含 if 条件链、函数元数据、
port direction）。2026-11-11 实测损失面曾为：condition_chain 32/32 丢、
source 11/11 丢、node.extra 16 条丢 —— 本迭代已全部补齐。

| 字段 | 处置 | 说明 |
|---|---|---|
| TraceNode 全部标量字段 | ✅ 序列化 | id/name/module/kind/width/bit_range/file/line/is_*/parent/modport_dir/is_signed |
| TraceNode.extra | ✅ 序列化（JSON-safe 值） | `_filter_json_safe`：不可序列化值显式丢弃（运行期对象不持久化）；实测键 direction/width 均恢复 |
| TraceEdge 全部标量字段 | ✅ 序列化 | 含 2026-11-11 新增的 condition_chain / function_return / is_function_call / source / extra |
| TraceEdge.source（SignalSource） | ✅ 序列化 | `asdict` 全字段往返；派生 property（bit_slice/full_expression）随之恢复 |
| TraceEdge.effective_condition | 🔁 重算恢复 | `add_trace_edge` 在 from_dict 路径自动重算（实测 72/72 一致），不占快照体积 |
| TraceEdge.condition_ast | ❌ **显式不保证** | 运行期 AST 对象（pyslang 节点），不可 JSON 序列化。快照路径恒为 None；消费方仅 `driver_extractor`（build 期回填 source_location），查询路径不受影响 |
| TraceEdge.extra（非 JSON-safe 值） | ❌ **显式不保证** | 同 `_filter_json_safe` 策略 |
| MIG（module_graph） | ✅ 序列化 | `snapshot save` 恒随图保存（`state/snapshot.py:124`） |
| class hierarchy / covergroup | ❌ **显式不保证** | `load_snapshot` 显式置 None/[]（`unified_tracer.py:470`），不静默沿用陈旧状态 |

**旧格式兼容**：from_dict 对 2026-11-11 前的快照（无新键）保持默认值语义
（condition_chain=[]、function 标记 False），加载不炸。
**体积影响**：字段补齐使快照增大约 1/3（fixture 实测 33%）；默认上限 64MB
（`SVQ_SNAPSHOT_MAX_MB` 可调），超限 save 显式报错而非静默截断。

## 2. 命令级矩阵（--from-snapshot 支持面）

| 命令 | 快照依赖 | 快照下行为 |
|---|---|---|
| `snapshot save/list/compare/delete` | —（state 写入方） | graph+MIG 恒同存 |
| `trace fanin` / `trace fanout` | graph-only | 等价（字段补齐后含条件语义） |
| `trace impact`（exp） | graph-only | 等价；风险分未标定的限制与 live 相同 |
| `dataflow analyze` | graph 为主（MIG 可选增强） | 等价；条件语义依赖 condition_chain（已补齐，有 parity 测试） |
| `frontier` | graph-only | 等价 |
| `ports` | graph-only | 等价 |
| `instances`（含详情） | graph + MIG | 等价（save 恒带 MIG） |
| `connections` | graph + MIG | 等价 |
| `hierarchy` | graph（实例树来自图节点 parent 关系） | 等价 |
| `paths` | graph + MIG（path resolver） | 等价 |
| `tb_join` | RTL 侧快照（`--from-snapshot` 必填）+ **TB 源文件仍 live 读取** | RTL 免 parse；TB 侧仍需 `--tb-file` |
| `trace evidence` | graph + **源码文本（semantic adapter）** | **降级为 location-only**：source_location（file/line）完整，源码 snippets 不可用（快照不存源码文本）。实测确认（2026-11-11） |
| `verify consistency` / `verify claim` | graph + MIG | 等价（结构一致性检查不依赖源码文本） |

## 3. 不支持 --from-snapshot 的命令（现状记录）

其余 core 命令（loads、locate 系列、state diff 等）走 live parse；是否加快照
支持由使用证据驱动（agent 实际出现"parse 一次查多次"的 >2 跳探索再加，见
PLAN P165 方案 C 暂缓决策）。

## 4. 维护规则

1. to_dict/from_dict 增删字段 → 同步 §1 矩阵 + 跑
   `test_p158_9_2_snapshot_surface.py`；
2. 命令增删 --from-snapshot → 同步 §2 矩阵；
3. 任何"半保真"状态（字段有时在有时不在）都是 P0 级回归，验收口径见
   SEMANTIC_CONTRACTS §3。
