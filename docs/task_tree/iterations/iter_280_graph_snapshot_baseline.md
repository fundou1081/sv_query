# Iteration 280: 图快照基线工具（PLAN P0.1）

**Metadata**:
- **Iteration #**: 280
- **Task Tree Level**: L2（[L1_graph_query_restructure](../tasks/L1_graph_query_restructure.md) / PLAN `P0.1`）
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "开始做吧"）
- **Outcome**: ✅ 完成（工具 + 6 基线 + 回归测试；全量 2321 passed）

## 🎯 目标

拆 `_trace_drivers_recursive`（P0.2）前，必须先能**证明行为没变**。
本迭代交付这个证明手段：SignalGraph 的规范化快照 + 逐项 diff。

## 🔧 交付

| 文件 | 内容 |
|---|---|
| `tools/graph_snapshot.py` | `capture` / `diff` / `verify` 三个子命令；只读；退出码 0/1/2 |
| `sim/tests/golden/graph_baseline/*.json` | 6 个 fixture 基线（合计 206 节点 / 463 边） |
| `sim/tests/regression/test_graph_baseline.py` | 6 基线回归 + 确定性 + 2 个 diff 自校验 + 绝对路径检查 |
| `sim/tests/fixtures/generate_forms/` | 新 fixture：for / if / case generate + 块内局部信号（覆盖 iter_274 修复点） |
| `TESTING.md` | 新增「图快照基线」使用说明 |

## 📐 快照内容

- **节点**：`id / kind / module / width / is_port / is_clock / is_reset / is_enable / parent / bit_range / modport_dir`
- **边**：`src / dst / kind / assign_type / condition / effective_condition / clock_domain / bit_slice / confidence / function_return / is_function_call / expression`
- **排除**：`file` / `line`（路径相关）、`extra`（可能含 AST）
- **归一化**：节点按 id、边按 (src,dst,kind,assign_type,condition) 排序；路径转仓库相对

## 🐛 过程中抓到的两个真问题

| # | 问题 | 后果 |
|---|---|---|
| 1 | 脚本 `sys.path` 里 `src` 位置不够靠前，被 **stdlib `trace.py`** 遮蔽 | `ModuleNotFoundError: 'trace' is not a package`；修法：无条件 `insert(0, src)` |
| 2 | `graph.edges()` 是 **networkx 的 (u,v) 元组**，不是 `TraceEdge` 对象 | 首版快照所有边字段为 `null`（46 条边全空）；修法：遍历 `graph._edge_data.values()` |

> 第二个问题说明工具的自校验（`test_diff_detects_*`）有价值：它在基线被提交前就暴露了空快照。

## 📊 基线规模

| fixture | 节点 | 边 |
|---|---|---|
| inst_demo | 17 | 20 |
| minimal_3module | 31 | 72 |
| minimal_arbiter | 17 | 43 |
| wrapper_chain | 34 | 54 |
| generate_forms | 34 | 46 |
| scheduler_minimal | 73 | 228 |
| **合计** | **206** | **463** |

## ✅ 验证

```bash
python3 -m pytest sim/tests/regression/test_graph_baseline.py -q   # 10 passed
python3 tools/graph_snapshot.py verify --snapshot <base> --filelist <fl>  # rc=0
python3 tools/graph_snapshot.py diff <a> <b>                        # 有差异 → rc=1
```

## 💡 对 P0.2 的用法

1. 改 `_trace_drivers_recursive` 前先跑一遍 `test_graph_baseline`（确认基线绿）
2. 拆完再跑：**零差异**才允许进入下一步
3. 若确实需要改语义 → 单独提交 + 重生成基线 + 本迭代记录写"为什么变"

## 🔗 相关

- 计划: [PLAN.md P0.1](../../../PLAN.md)
- 审计来源: [iter_278](iter_278_distance_and_audit.md)
