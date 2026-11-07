# Inline skill prompt pilot（P97）

**日期**: 2026-11-07
**范围**: 3 cells ×2 条件 ×DeepSeek-Flash ×seed1
**性质**: skill 内容直接注入 prompt 的 A/B 试验

---

## 1. 条件

- `prompt`：原有 A+D prompt；
- `inline`：把 `.dsh/skills/svq-query-protocol/SKILL.md` 的 body
  直接追加到 prompt，并给出源路径。

相同：

- snapshot 预构建；
- source 存在；
- A+D runner；
- 3 cells：AXI araddr / SERV clk path / Pico mem_valid fanout。

---

## 2. 结果

| cell | prompt | inline |
|---|---:|---:|
| AXI araddr | 26.6s ✅ | 102.4s ✅ |
| SERV clk path | 123.8s ✅ | 38.6s ✅ |
| Pico mem_valid | 84.4s ✅ | 194.3s ✅ |

均值：

```text
prompt: 78.3s
inline: 111.8s
```

准确率：

```text
prompt 3/3
inline 3/3
```

工具调用数：

| cell | prompt | inline |
|---|---:|---:|
| AXI | 6 | 15 |
| SERV | 12 | 7 |
| Pico | 14 | 16 |

---

## 3. 结论

```text
inline 没有稳定收益；
一个 cell 变快，两个变慢；
工具调用没有一致下降；
准确率不变。
```

这说明：

- skill 内容进入上下文不等于模型会按协议收敛；
- prompt 变长可能增加探索；
- 单 seed 方差很大，不能下强结论；
- 但至少没有证据支持“inline skill 默认开启”。

## 4. 决策

- 不扩 24 cells；
- inline 只保留为实验模式；
- 不把 skill 作为默认；
- 如果继续，应先做 harness allowlist，再测 skill。

## 5. 边界

- 1 模型、1 seed、3 cells；
- prompt/inline 长度不同；
- 没有统一 protocol audit；
- 不声称 skill 完全无效，只声称当前样本无收益。
