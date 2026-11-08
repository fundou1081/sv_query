# Tool evidence 默认关闭回归（P106）

**日期**: 2026-11-08
**范围**: 12 题 ×2 模型，evidence=false 默认
**数据**: [tool_pilot_12_evidence_default_2026-11-08.json](tool_pilot_12_evidence_default_2026-11-08.json)

---

## 1. 目的

确认 evidence intent / source_context 加入后：

- 默认输出不变；
- 不增加 token/延迟；
- direct 任务仍 24/24。

## 2. 结果

| 模型 | exact | mean wall |
|---|---:|---:|
| MiniMax-M3 | **12/12** | **5.1s** |
| DeepSeek-Flash | **12/12** | **4.0s** |

合计：

```text
24/24 exact
```

没有 evidence 字段被默认返回。

## 3. 对比

之前工具 pilot：

```text
MiniMax 9.0s
DeepSeek 4.7s
```

本次：

```text
MiniMax 5.1s
DeepSeek 4.0s
```

差异是模型/运行方差；准确率保持。

## 4. 结论

```text
evidence 默认关闭成立；
direct 任务不受影响；
需要复核时才用 intent=evidence。
```

## 5. 边界

- 1 次运行；
- 与 9.0s 不是严格同 seed；
- 未测 evidence=true 在这些 direct 任务上的 token 成本；
- 不作模型排名。
