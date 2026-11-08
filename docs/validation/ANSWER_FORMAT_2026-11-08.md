# Answer JSON format robustness（P116）

**日期**: 2026-11-08
**状态**: 完成
**目标**: 区分“答案内容错”和“最终 JSON 语法坏”

---

## 1. 问题

P115 唯一失败：

```text
DeepSeek seed1, p115_axi_s_axi_awready
{"task_id":'p115_axi_s_axi_awready', ...}
```

单引号导致 strict JSON parser 失败。  
内容正确，confidence=high，但不是 valid JSON。

## 2. 方案

新增 benchmark 层：

```text
tools/benchmark/answer_json.py
```

规则：

1. 先 strict JSON；
2. strict 失败时，只修复单引号字符串字面量；
3. 不推断缺失字段、不改字段值；
4. 返回 `(obj, repaired)`；
5. runner 记录 `json_repaired`。

这不是改 agent 输出，而是让评测能区分：

```text
semantic wrong
vs
syntax failure
```

## 3. 结果

P115 原始：

```text
39/40 valid JSON
```

用 parser 重放原始 raw：

```text
40/40 exact
1 repaired
```

误报仍为：

```text
0 false-confident
0 false-found
```

## 4. 测试

```text
python3 tools/benchmark/test_answer_json.py
4 tests passed
```

## 5. 边界

- 只修复单引号；
- 不修复缺失/错误字段；
- 不改变 agent 的最终输出，真实消费者仍需要 strict parser/重试；
- 修复后的 exact 不等于 raw-valid-JSON；
- 不能把 1 次修复说成模型完全稳定。

## 6. 结论

```text
P115 的内容质量是 40/40；
raw JSON 是 39/40；
format repair 后评测可继续。
```

下一步进入真实 debug 场景，而不是继续优化格式。
