# Iteration 329: canonical signal identity（PLAN P33.1）

**Metadata**:
- **Iteration #**: 329
- **Task Tree Level**: L2（PLAN `P33.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "按这个方向推进"）
- **Outcome**: ✅ 完成（7 新测试；2642 passed）

## 🎯 目标（产品方向 P0 grounding 第一步）

避免 agent 把“拼写错/歧义”误读成“无驱动/无路径”。

## 🔧 实现

| 能力 | 行为 |
|---|---|
| exact | 完整 id 命中 |
| relative | 唯一后缀：`u.a` → `top.u.a` |
| bit_base_fallback | `top.y[3]` 无位节点但有 `top.y` → found，保留位查询回退 |
| not_found | `ok=false` + `E_SIGNAL_NOT_FOUND` + suggestions |
| ambiguous | `ok=false` + `E_SIGNAL_AMBIGUOUS` + candidates |

- 新公共 helper：`resolve_signal` / `resolution_fields` / `resolution_error_message`
- 接入：`trace fanin` / `fanout` / `impact` / `evidence`
- 输出新增：`resolved_signal` / `resolution` / `candidates` / `suggestions` / `error`
- error_code 映射支持异常显式 `error_code`

## 📊 效果

```bash
trace fanin top.nope --json
→ ok=false, E_SIGNAL_NOT_FOUND

trace fanin a --json            # top.a / top.u.a
→ ok=false, E_SIGNAL_AMBIGUOUS, candidates

trace fanin u.a --json
→ ok=true, resolution=relative, resolved_signal=top.u.a

trace fanin top.y[3] --json     # 只有总线 y
→ ok=true, resolution=bit_base_fallback
```

## 🧪 测试

新增 `test_signal_resolution.py`（7）：
exact / relative / ambiguous / not_found / impact+evidence / batch partial / bit fallback。

同步更新旧“静默空”断言：
- `test_trace.py` 未知信号 human 输出改为 error；
- `test_trace_cache_error.py` 4 个静默空测试改为显式 not_found；
- adversarial/schema 测试改用真实信号；
- golden 重新生成（新增 resolution 字段）。

## ✅ 验证

- 全量 **2642 passed / 0 failed**
- 契约字段同步（trace_signal / impact_signal / evidence_signal）
- `test_trace_schemas` 的 dynamic id regex 放宽以覆盖 `mem[wr_ptr_q[$clog2-1:0]]`

## ⚠️ 边界

- 相对名匹配是**后缀唯一匹配**，不是完整作用域推导；歧义时要求 agent 给更长路径。
- `bit_base_fallback` 的 `resolved_signal` 是完整位 id（可能不是图节点），
  由查询层保留原回退语义。
- `paths` / `dataflow` 已有独立 not_found 错误，不在本迭代改动范围。

## 🔗 相关

- 计划: [PLAN.md P33.1](../../../PLAN.md)
- 产品方向: [product_direction_2026-10-31](../../architecture/product_direction_2026-10-31.md)
