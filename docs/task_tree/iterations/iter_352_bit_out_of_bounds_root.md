# Iteration 352: 位选越界源头调查/修正（PLAN P51）

**Metadata**:
- **Iteration #**: 352
- **Task Tree Level**: L2（PLAN `P51`）
- **Created**: 2026-11-02 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "调查一下这些越界的源头"）
- **Outcome**: ✅ 完成（3 个根因修正；2717 passed）

## 🎯 目标

解释并修掉 `verify consistency --checks bit` 的 parent 越界来源。

## 🔎 根因

### 1. Indexed part-select 语义错位（主因）

源代码：

```systemverilog
assign out = bus[32 +: 32];
```

pyslang 的 RangeSelect 对 `+:` / `-:` 的 `.left/.right` 是 **base/width**，
不是 msb/lsb。旧实现直接拼成 `bus[32:32]`：

- `_common.iter_bit_selects`：`msb=left, lsb=right`；
- `get_signal`：同样；
- `_expr_range_select`：同样。

修复：

- `+:` → `[base+width-1 : base]`；
- `-:` → `[base : base-width+1]`；
- `base_chain` 的末位同步用规范化 full_id；
- graph cache `v11 → v14`（位选 ID/语义变化）。

### 2. multi-top 前缀共用

`GraphBuilder._create_hierarchical_bit_nodes` 对 filelist 中所有 top 都用
**第一个 top** 的 `instance_path`，导致 `axi_crossbar` 的位选被挂到
`axi_adapter.m_axi_araddr`，出现 `[63:32]` / `[127:96]` 越界。

修复：每个 top 使用自己的 `hierarchicalPath/name`。

### 3. 直接表达式位展开

`_expand_slice_bit_nodes` 把：

```systemverilog
full = (... && wr_ptr_reg[ADDR_WIDTH-1:0] == ...)
```

的 leaf edge `wr_ptr_reg[4:0] -> full` 当成 `full = wr_ptr_reg[4:0]`，
展开出 `full[0..4]` 假位节点。

修复：只有 `edge.expression` 是直接拷贝（`src`/短名）才展开。

## 📉 结果

| 项目 | 修正前 | 修正后 |
|---|---:|---:|
| verilog-axi parent 越界 | 269 | **12** |
| picorv32 | 2 | **2** |

剩余 12 条：

```
axi_vfifo.axi_vfifo_enc_inst.out_hdr_next[10..]
parent = out_hdr_next
parent width = [1:0]  ← 应为 HDR_WIDTH=18
```

这不是 child bit 越界，而是 **parent width 元数据错误**（dynamic bit
select 族，parent width 只从首批位节点推断）。单独记为 P52 候选。

picorv32 `mem_done[1]` 同类：`mem_done` 是 1-bit wire，parent width `[0:0]`，
bit1 来自另一条未知位展开路径；待 P52 深挖。

## 🧪 测试

- `test_indexed_part_select_normalized`；
- `test_multi_top_bit_prefix`；
- 全量 **2717 passed / 0 failed**。

## ⚠️ 边界

- 本次修 ID/namespace/直接展开；
- 未修 parent width 推断；
- 全图位检查仍有 12+2 条，属于 parent metadata。

## 🔗 相关

- 计划: [PLAN.md P51](../../../PLAN.md)
