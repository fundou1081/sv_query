# Iteration 291: F3 切片赋值按位展开（PLAN P5.4）

**Metadata**:
- **Iteration #**: 291
- **Task Tree Level**: L2（[L1_bit_precision](../tasks/L1_bit_precision.md) / PLAN `P5.4`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "构建针对性计划，开始修复"）
- **Outcome**: ✅ 完成（切片→逐位节点+偏移映射；2402 passed）

## 🎯 问题

F1 只保证"不串位"，但切片仍是**切片粒度**：

```
assign y[7:4] = a[3:0];
fanin(top.y[5]) = [top.a]          ← 期望 a[1]
assign y = a[7:4];
fanin(top.y[2]) = [top.a[7:4]]     ← 期望 a[6]
```

根因：图里只有 slice 节点（`y[7:4]`）+ 一条总线 DRIVER，没有逐位节点。

## 🔧 方案：新 pass `_expand_slice_bit_nodes`（建图层）

在 `bit_nodes` 之后执行（pipeline 声明式插入）：

| 形态 | 映射规则（低位对齐，与 iter_143 一致） |
|---|---|
| LHS 切片 `X[hi:lo] = S` | `X[lo+k] ← S[k]`（S 为 bus 或 slice） |
| RHS 切片 `B = S[hi:lo]` | `B[k] ← S[lo+k]` |

保护措施：

| 风险 | 处理 |
|---|---|
| 造假节点 | 只对**显式切片**建点（id `[hi:lo]`、hi>lo）；纯总线直连仍不建（iter_126 契约不变） |
| 图爆炸 | 新节点上限 20000，超限 `logger.warning` 停止（不静默截断） |
| 父总线提升污染 | 逐位节点**不加 BIT_SELECT 聚合边**（iter_143 教训） |
| 常量/运算源 | 跳过（`4'h0` / op node 的值位映射不在本版） |
| 源比切片窄 | 只映射 `min(width, src_width)` 位（SV 高位零扩展，不造不存在的 bit） |
| 重复边 | 同 `(src,dst)` 已有 DRIVER 则不重加（幂等） |

## 📊 效果

| 场景 | 修复前 | 修复后 |
|---|---|---|
| `y[7:4]=a[3:0]` → `y[5]` | `{a}` | **`{a[1]}`** |
| `y = a[7:4]` → `y[2]` | `{a[7:4]}` | **`{a[6]}`** |
| `y[7:0]=a; y[3:0]=b` → `y[5]` | `{a}` | **`{a[5]}`** |
| 同上 → `y[2]` | `{a,b}` | **`{a[2], b[2]}`**（真多驱动） |
| `y[7:4]=a`（a 4-bit）→ `y[5]` | `{a}` | **`{a[1]}`** |
| 切片外悬空位 `y[3]` | `{}` | `{}`（不变） |

## 📈 代价（实测）

| 设计 | 节点 | 边 |
|---|---|---|
| verilog-axi | 13,629 → **13,801**（+1.3%） | 27,302 → **27,577**（+1.0%） |
| array_index fixture | 24 → 104（教学用途，切片密集） | — |
| 6 个图基线 fixture | **零差异**（无切片赋值） | — |

## 🧪 测试

- `test_bit_precision.py` 19 → **25**（新增 F3 组 6 个：LHS 偏移 / bus 源 / RHS 偏移 /
  slice→slice / 无聚合边守卫 / 窄源不造位）
- 更新 2 个 **1:1 truth** 测试（`test_bit_select_truth.py`）：节点集新增逐位节点，
  是有意变更，注释写明 iter_291 原因
- 全量：**2402 passed / 0 failed**

## 📌 未覆盖（明确记录）

- 常量源切片（`y[3:0]=4'h0`）不做值位映射
- `[base +: width]` 动态 part-select（`bus[?:?]`）不展开
- load 方向位精度（`fanout(a[i])`）仍是总线粒度 → PLAN **P5.6**

## 🔗 相关

- 计划: [PLAN.md P5.4](../../../PLAN.md)
- 前序: [iter_289 审计](iter_289_bit_precision_audit.md) / [iter_290 F1+F2](iter_290_bit_precision_fix.md)
- 历史位桥: `docs/architecture/signal_graph_accuracy_audit.md` A2 iter_137/143
