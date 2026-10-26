# Iteration 297: signedness 建模与符号扩展（PLAN P9）

**Metadata**:
- **Iteration #**: 297
- **Task Tree Level**: L2（[L1_signedness](../tasks/L1_signedness.md) / PLAN `P9`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "要开这个"）
- **Outcome**: ✅ 完成（signedness 入图 + 符号扩展；2464 passed）

## 🎯 背景

P8 之后只剩有符号字面量（`4'shF`）落在常量总线：扩展方向（符号 vs 零）需要
signedness 信息，而 SignalGraph 不建模。本轮补图元数据 + 查询层扩展规则。

## 🔧 P9.1 图元数据

| 项 | 实现 |
|---|---|
| 节点字段 | `TraceNode.is_signed: bool \| None`（None = 未建模/未知） |
| 提取 | `SemanticAdapter.extract_data_signed` / `extract_port_signed`：pyslang `type.isSigned`；syntax 声明回退 `type.signing` token（`integer` 默认 signed） |
| 落点 | 端口、net 声明（含 generate 展开）、变量声明、wire init |
| 序列化 | `to_dict`/`from_dict` 保留 `is_signed` |
| 缓存 | `CACHE_VERSION` 1.0 → 1.1（旧缓存无该字段 → 重建） |
| 图基线 | 快照字段加 `is_signed`，6 个 fixture **有意重生成** |

## 🔧 P9.2 查询层

| 场景 | 规则 |
|---|---|
| 有符号字面量 `4'shF` | 越界位 = 符号位（1）；`4'sh2` = 0 |
| 图里规范化的 `-4'sd1` | 解析负号/补码；literal 检测接受前导 `-` |
| 有符号信号加宽 | `fanin(y[5])` → `a[3]`（符号位节点） |
| 无符号信号/字面量加宽 | 越界位 = `1'b0`（常量） |
| fanout 符号位 | `a[3]` 驱动 `y[3..7]`（扩展高位） |
| 拼接内字面量 | 自决定宽度，**不**符号扩展（SV 语义） |
| `a & 4'shF` | 常量符号扩展位 = 1，信号位仍是依赖（不误判恒 0） |
| 1 位源广播 | `clk → out[i]`：位位置用**目标节点内相对位**（0），避免误判加宽 |

同时修了一个真 bug：表达式映射的位位置混用"绝对位/节点内相对位"，
导致 `out[i] = clk` 在 i≥1 时被当成零扩展、产出伪 `1'b0` 驱动。

## 📊 效果

| 场景 | 修复前 | 修复后 |
|---|---|---|
| `y=4'shF`；fanin(y[5]) | `-4'sd1` 常量总线 | `1'b1` |
| `y=4'sh2`；fanin(y[5]) | 常量总线 | `1'b0` |
| signed `a[3:0]`；`y=a`；fanin(y[5]) | `a`（总线） | `a[3]` |
| 同上 fanout(a[3]) | `{y}` 总线 | `{y[3..7], t}` |
| `a & 4'shF`；fanin(s[5]) | `a` 总线 | `{1'b1, a[5]}` |
| 无符号 `a`；fanin(y[5]) | `a` | `1'b0` |

## 🧪 测试（`test_signedness.py`，13 个）

- 图元数据：端口/变量/net/integer；JSON 往返
- 有符号字面量：负值符号扩展、正值零扩展、无符号对照
- 有符号信号：符号位 fanin、fanout 高位、无符号对照、非符号位同索引
- 拼接自决定；`&` 有符号常量保留信号依赖；无符号常量恒 0

## 📌 边界（KNOWN_LIMITATIONS §3.6 已更新）

- `integer` 位宽仍按 (0,0)/(1,0) 提取（signedness 已正确；宽度提取是既有缺口）
- packed struct/union 的 signedness 未建模（None → 保守）
- 有符号算术/比较语义不变（位依赖规则不变，signedness 只影响扩展方向）
- 变量移位/动态 part-select/函数调用仍本质不可静态逐位

## 🔗 相关

- 计划: [PLAN.md P9](../../../PLAN.md)
- 前序: [iter_296 常量位](iter_296_const_bit_precision.md)
