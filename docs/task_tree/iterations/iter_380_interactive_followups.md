# Iteration 380: 交互式 debug 后续修复（PLAN P76）

**Metadata**:
- **Iteration #**: 380
- **Task Tree Level**: L2（PLAN `P76`）
- **Created**: 2026-11-06 GMT+8
- **Outcome**: ✅ canonical path / control unknown / class hints

## 🎯 来源

[interactive debug pilot](iter_379_interactive_debug.md) 发现的三个问题。

## 🔧 修复

### 1. `paths --canonical`

- 新增 `--canonical`；
- 枚举候选，按 `max_nodes_then_lexicographic` 选唯一路径；
- 输出 `canonical_policy/candidate_count/candidate_truncated`；
- 与 `--all` 互斥；
- deep_chain：11 节点 / 10 hops。

### 2. 未建模 control

- `wrapper_passthrough` 且无 condition → `controlflow analyze`：
  - `condition_status="unknown"`；
  - warning `unmodeled_control: ... source check required`。
- 不假装“无条件”，也不伪造 mux 边。

### 3. class 提示

- `trace constraints p.addr` → hint canonical / suggestions；
- `scope top.e` → class instance 提示；
- `trace coverpoints` 0 match → instance-qualified 提示。

## 🧪 测试

新增 `sim/tests/cli/test_interactive_followups.py`：

- canonical 11 节点/10 hops；
- controlflow unknown；
- class relative/scope/coverpoint hints。

全量 **2538 passed / 0 failed**。

## ⚠️ 边界

- 三元 mux 仍只标 unknown，未生成真实 control edge；
- `paths --canonical` 是 max-node 策略，不是语义上唯一真实路径；
- M3.1/DeepSeek pilot 仍是单 seed。
