# Task distribution 2026-11-09

**性质**: 对我们已有 frozen task corpus 的分类，不是用户研究
**范围**: 6 个任务文件，38 个 task instances
**目的**: 决定下一步是否做 discovery、fault localization 或停止扩任务

---

## 1. 分类结果

| operation | total | signal given | discovery |
|---|---:|---:|---:|
| direct_neighbors | 19 | 17 | 2 |
| path | 4 | 4 | 0 |
| evidence | 2 | 2 | 0 |
| verify | 6 | 6 | 0 |
| unknown/abstain | 2 | 2 | 0 |
| multi_step_debug | 5 | 5 | 0 |
| **合计** | **38** | **36** | **2** |

项目类型：

```text
fixture:      30
real-project: 8  (UART 5 + I2C 3)
```

其他：

```text
requires_verify: 6
requires_search: 2   (UART T1, I2C T1)
fault localization: 0
patch generation: 0
```

> 修正 worker survey 的一处错误：它写成 `requires_search=0`，但同一张表里
> UART/I2C 的 T1 是 `signal_given=false`。实际是 2，不是 0。

## 2. 这组分布说明什么

### 最大类别是 direct neighbors

```text
19/38 = 50%
```

我们花了大量任务测“给定 ID，查 1-hop 邻居”，这是核心能力，但已经过度采样。

### verify 只有 6/38

verify 是产品差异化能力，但样本少于 direct neighbors。

### real project 只有 8/38

只有两个 block（UART、I2C），且两个 T1 都是同一类 reggen INTR_TEST 问题。

### discovery 只有 2/38

两个 T1 需要从描述找信号。它们是真 discovery，但只有 2 个，且都是同一模式。

### fault localization / patch = 0

没有任何“给 symptom，找 root cause”或“propose fix”的任务。

## 3. 不能从这组分布得出的结论

这 38 个任务是**我们自己 authored/frozen** 的：

- ground truth 大多由 `sv_query` CLI 反向产生；
- 任务选择反映我们知道怎么问的内容；
- 唯一一次 tool 与 source 不一致时，修正的是 task 而不是 tool；
- 没有用户日志、issue、DV failure 的真实分布。

所以它不能证明：

```text
用户最需要 discovery
用户不需要 fault localization
真实任务 50% 是 direct neighbors
```

它只能证明：

```text
我们的 benchmark 目前 50% 是 direct neighbors；
real-project 和 verify 样本不足；
discovery 只有 2 个，且模式单一。
```

## 4. 决策

### 不做什么

```text
不因为 direct neighbors 占 50% 就继续加 direct 任务
不因为 discovery 只有 2 个就马上做 search/discovery 功能
不因为 fault localization 是 0 就扩到自动 debug
```

### 下一步

先做 **independent task intake**：

```text
P124: 从 OpenTitan DV testplan / checklist / verification intent
      提取 3 个真实任务，而不是我们自造任务
```

要求：

- 任务来自外部文档/验证意图，不来自我们现有 frozen corpus；
- ground truth 由 spec/source 手工确认，不能只用 sv_query 生成；
- 至少 1 个 unknown/abstain；
- 先只做 3 个，分类后再决定是否做 discovery 或 fault localization。

如果 3 个真实任务里 discovery 反复出现，再做 search；
如果出现 symptom→cause，再谈 fault localization；
如果两者都没有，说明核心 query/verify 已经够，应该停止扩功能。

## 5. 结论

```text
当前 corpus 是 query benchmark，不是用户 task distribution。
它证明 direct query 已充分覆盖；
它不足以证明 discovery 或 fault localization 是下一步。
```

下一步不是加功能，而是换任务来源：

```text
从我们自造的任务
→ 到 OpenTitan DV testplan / checklist 的真实 verification intent
```
