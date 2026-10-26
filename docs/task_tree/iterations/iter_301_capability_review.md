# Iteration 301: 信号追踪能力评审 + 文档收敛（P13 backlog 登记）

**Metadata**:
- **Iteration #**: 301
- **Task Tree Level**: L1（能力评审 / 文档）
- **Created**: 2026-10-27 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "先停在这，更新文档。记录下来。然后再整体看，信号追踪功能还有什么需要加强。"）
- **Outcome**: ✅ 完成（无代码改动；P0 bug 登记；P13 backlog 入 PLAN）

## 🎯 动作

1. 停止位精确性实现（P5~P12 收尾）。
2. 刷新 [CURRENT_TODO.md](../../../CURRENT_TODO.md)：P0~P12 完成、P13.1 为下一项。
3. 新增能力评审 [trace_capability_review_2026-10-27](../../architecture/trace_capability_review_2026-10-27.md)：
   现状矩阵 + 位精确性矩阵 + 缺口 P0~P3 + 执行顺序。
4. `PLAN.md` 登记 **P13**（6 项 backlog，全部 `待做`），`current item = P13.1`。
5. `KNOWN_LIMITATIONS §3.7` 登记 P0；`INDEX`/`overview`/`WORKFLOW` 同步。

## 🔍 评审关键发现

### P0（静默错误）: 缓存 key 不含 `SVQ_BIT_BRIDGE`

复现（实测）：

```
one 建图 → 5 节点；切 SVQ_BIT_BRIDGE=full 再 build(use_cache=True)
→ 仍 5 节点（full 应为 37）→ 同一份缓存串模式
```

根因：`UnifiedTracer._graph_cache_key` = `{content_hash}-v2-t{target}`，模式未入 key。
影响：切换模式后查询 **静默错误**（不是慢）。修复登记 P13.1。

### P1/P2 摘要

| 缺口 | 证据 | 影响 |
|---|---|---|
| 粗粒度回退无标记 | 位查询缺失时回落总线，输出同形 | agent 可能误当精确答案 |
| 深层 packed 成员（`o.inner.a`） | 只补一层成员节点 | 查询空答 |
| 三元/case 分支 | `s=c?a:b; y=s[3]` → `{s[3], a, b}` | 分支总线级 |
| 多驱动 | `y=a; y=b` → `{a,b}` 无标记 | 无法识别冲突 |
| 静态 memory 位 | `mem[1]` 元素级可追，位查询停住 | 位精度不完整 |
| capabilities/输出字段 | 无 bit_precision；`is_signed`/位段不输出 | agent 无法判断精度/扩展 |

## 📊 状态

- 全量门禁：**2489 passed / 0 failed**（未变，本轮无代码）
- 检查：check_docs / check_plan / check_cli_layers / check_except_pass 全绿
- 计划树：P0~P12 完成，P13 六项 backlog `待做`

## 🔗 相关

- 评审文档: [trace_capability_review_2026-10-27](../../architecture/trace_capability_review_2026-10-27.md)
- 计划: [PLAN.md P13](../../../PLAN.md)
- 前序: [iter_300](iter_300_packed_member_bit_bridge.md)
