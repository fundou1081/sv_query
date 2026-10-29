# Iteration 314: `--bits` 范围与显式映射（PLAN P18.3）

**Metadata**:
- **Iteration #**: 314
- **Task Tree Level**: L2（PLAN `P18.3`）
- **Created**: 2026-10-29 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "按顺序做1 2 3"）
- **Outcome**: ✅ 完成（范围 + `src=/dst=`；2572 passed）

## 🎯 需求

P15 的 `--bits` 只支持单 bit、按位置：
```
--bits 1,5          # 只能单 bit
--bits 7:4,3:0      # 不支持
--bits src=1,dst=5  # 不支持（位置写错就查错端点）
```

## 🔧 实现（`cli/core/semantic/_bit_args.py`）

| 类型 | 说明 |
|---|---|
| `BitRange(hi,lo)` | 归一化 `hi>=lo`；`7:4` / `4:4`；范围节点 id 同时尝试 `[hi:lo]` 与 `[lo:hi]` |
| `BitSpec` | `positional` 与 `named` 互斥；显式名字按命令校验 |
| `parse_bits(raw, names)` | `paths/dataflow` 用 `src,dst`；`impact` 用 `signal`；重复/缺名/混用报错 |
| `normalize_endpoint` | 单 bit → precision=bit；切片 → precision=bus；缺失 → 总线 + `coarse_fallback=true` |

输出新增 `requested_range`（`"7:4"`）与 `kind`；`paths` 现在**始终**输出 `bits.coarse_fallback`
（之前只在 true 时出现，消费方要区分“没有字段”和 false）。

## 📊 用法

```bash
# 范围（切片节点存在时精确到切片；否则回落总线并标记）
svq paths top.a top.y --bits 7:4,7:4 --directed
# src_resolved=top.a[7:4], dst_resolved=top.y[7:4], precision=bus, coarse=false

# 显式映射，避免位置错误
svq paths top.a top.y --bits src=1,dst=5
svq dataflow analyze top.a top.y --bits src=7:4,dst=7:4

# impact 单信号范围
svq trace impact top.a --bits 7:4
# 或显式：--bits signal=7:4
```

## 🧪 测试

`test_bit_endpoint_args.py` +8（共 15）：
范围精确 / 显式单 bit / 显式范围 / 范围缺失回落 / 缺端点失败 / 混用失败 /
dataflow 范围 / impact 范围。原有单 bit 测试全部保持通过。

## ✅ 验证

- 全量：2564 → **2572 passed / 0 failed**
- 无图结构变化；无缓存版本变更
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿

## 📌 边界

- 范围只支持**纯静态** `hi:lo`；`+:`/`-:`、变量范围不做
- 范围精确依赖图上已有切片节点；没有则回退总线（显式 `coarse_fallback`）
- explicit 名字固定（paths/dataflow: `src,dst`；impact: `signal`）

## 🔗 相关

- 计划: [PLAN.md P18.3](../../../PLAN.md)
- 前序: [iter_313 函数诚实标记](iter_313_function_call_honesty.md)
