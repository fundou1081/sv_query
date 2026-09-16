# Iteration 228: `check_regression.py` L1/L4 改为硬失败 (方豆拍板)

**Metadata**:
- **Iteration #**: 228
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_zero_red_and_policy_followups.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

iter_226 把 `check_regression.py` 的阈值收紧 (L1/L4 50%→30%, flakiness 0.7→1.0),
但如实指出: **L1/L4 越界历来只产生 ⚠️ 警告, 不改变退出码** —— 所以那轮真正的收紧
只是 flakiness (硬失败), L1/L4 的数字收紧只让警告更早出现。当时把它登记为待决项。

**方豆决策 (本轮)**: **"1 改成硬失败"** → L1/L4 越界也 `exit 1`。

## 🔬 改动

### 1. `tools/benchmark/check_regression.py`

```python
# L1
if drop_pct > max_drop:
    passed = False                       # ← 新增 (此前只 append 警告)
    messages.append(f"❌ L1_instances: dropped {drop_pct:.1f}% ...")

# L4
if drop_pct > max_drop:
    passed = False                       # ← 新增
    messages.append(f"❌ L4_edges: dropped {drop_pct:.1f}% ...")
```

- 消息前缀 `⚠️` → `❌` (报告里不再有歧义: 六个维度语义统一)
- 提示语从"may be memory flakiness, manual review needed"改为
  "非预期下跌; 若确认是输入/配置变化, 请重生成 baseline"
  —— **不能再用"可能是内存 flakiness"当借口**: 那个真因 (SourceManager 生命周期)
  已在 iter_185 修掉, 实测 stdev=0.0 / deterministic_ratio=1.0
- 文档字符串: 按"沿革"写明 iter_226 (阈值) 与 iter_228 (硬失败) 两步,
  并说明**为什么当初只警告** (受 flakiness 影响会误报) 与**为什么现在可以硬** (真因已修)

### 2. 阈值表 (最终)

| 维度 | 阈值 | 越界后果 |
|---|---|---|
| L2 nodes / edges / IM | 跌 > 30% | ❌ exit 1 |
| L1 instances | 跌 > 30% | ❌ **exit 1** (本轮变更) |
| L4 edges | 跌 > 30% | ❌ **exit 1** (本轮变更) |
| flakiness `deterministic_ratio_im` | < 1.0 | ❌ exit 1 |

### 3. 测试 `sim/tests/integration/test_benchmark_regression.py`

- `test_l1_35_pct_drop_fails` / `test_l4_35_pct_drop_fails`:
  断言 `❌ ...` + `max_drop=30.0%` + **`returncode == 1`**
  (从上一轮的"警告 + rc=0"改过来 —— 语义变了, 断言必须跟着变)
- **新增** `test_l1_l4_within_threshold_still_pass`: L1/L4 各跌 ~20% (< 30%) → 仍 `✅` + rc=0
  —— 防止"改硬失败"变成过度触发 (硬失败也要有下界)
- 模块 docstring 增补 iter_228 说明
- 结果: **15 passed** (opensource 标记, 用 `-m opensource` 定向跑)

### 4. `tools/benchmark/README.md`

原文 "CI regression check (PR6) 应该 focus 在 L2 数据, **L1/L3/L4 作为辅助参考**"
已**过期** → 加更新块, 写明六维度全部硬失败及其沿革。

## 📊 验证

| 项 | 结果 |
|---|---|
| benchmark regression 套件 | **15 passed** |
| 全量 canonical (`-m "not opensource"`) | **3317 passed / 0 failed** (exit 0) |
| 抽查 (真实 CLI) | 20% 下跌 → `✅` + rc=0; 35% 下跌 → `❌` + rc=1 |
| `check_docs.py` / `check_except_pass.py` | ✅ / 0 |

> 说明: 本工具与它的测试都是 `opensource` 标记, 不在 canonical 门禁的选择集内
> (canonical 里 167 deselected)。所以**必须**定向跑 `-m opensource` 才算验证过 ——
> 这一点已写进本轮记录, 避免下次只看 canonical 绿灯就以为覆盖了。

## 💡 关键发现 / 决策

1. **"收紧阈值"有两种含义**: 改数字 (iter_226) vs 改判定 (iter_228)。
   前者在 L1/L4 上只影响输出文本, 后者才真正拦截回归 —— 不写清楚就是自欺。
   (iter_226 的选择: 只做前者 + 把后者标为待决; 本轮补齐后者。)
2. **硬失败必须有下界测试**: 加了硬失败就要同时锁"阈值内的正常波动仍放行"
   (新增 20% 下跌 PASS 用例), 否则阈值一收紧就可能把正常波动变成 CI 误报。
3. **历史理由会过期**: "L1/L4 只警告"的注释里写的是 flakiness 原因, 而 flakiness
   已在 iter_185 修掉 —— 注释里的理由必须跟着事实复核, 否则它会永久为宽松辩护。

## 📎 产物

- `tools/benchmark/check_regression.py` (L1/L4 → 硬失败 + 沿革文档)
- `tools/benchmark/README.md` (过期结论更正)
- `sim/tests/integration/test_benchmark_regression.py` (15 passed: 2 个硬失败断言 + 1 个下界)
