# Iteration 209: R4-1 落地 — filelist 内容经 `-f` 传入给明确提示

**Metadata**:
- **Iteration #**: 209
- **Task Tree Level**: L2 (CLI 可用性)
- **Parent Task**: iter_208 (上一轮"未生效"的结论**被本轮推翻**)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 修复落地 + 3 条回归测试

## 🎯 本次目标

上一轮 (iter_208) 我判断"守卫消息被吞掉"并回退了修复。本轮回敬核实并落地。

## 🔬 实际结果

### 关键澄清: 上一轮的"未生效"结论是**我的调试打印造成的假象**

我用 `SVQ_DEBUG=1` 看真实异常, 又用**完整长度**打印 stderr 行, 结果是:

```
Error: <path>: 内容看起来是 filelist (特征行 '+incdir+inc'), 不是 SystemVerilog 源码 — 请用 --filelist 传入该文件
```

守卫**当时就是生效的**! 之前"只看到路径"是因为我自己的调试打印写了 `l[:100]` 而
**路径本身就 ~100 字符** —— 消息被我的截断吃掉了。教训: 诊断输出不要截断到可能
与内容等长的长度 (本次路径 100 字符 / 截断 100 字符, 恰好把正文切没)。

同时修正上一轮对 `handle_compilation_error` 的判断: 它**没有**吞消息
(单行消息完整打印, 多行打前 10 行)。

### 真正剩下的问题: 提示自相矛盾

`stats -f <filelist>` 会先打印"看起来是 filelist, 请用 --filelist", **紧接着**又打印
`Hint: ... Use --no-strict to analyze the partial AST ...` —— 后者是"RTL 不完整"场景的
建议, 对"传错文件类型"是误导。

修复: `handle_compilation_error` 区分错误类型 —— 当消息含 `请用 --filelist`
(输入类型错误) 时**不再**打印 filelist/--no-strict 提示。

### 最终实现 (含 iter_208 的两条教训)

`SVCompiler._reject_non_design_unit(tree, fname, source)`:
1. 保留原有"表达式根 → SIGTRAP 防护";
2. 新增 filelist 内容识别: 扫描**前 20 个有效行** (不能只看首行 —— 预处理器会在顶部
   注入 `` `timescale ``), 命中 `+incdir+`/`+define+`/`+libext+`/`-f `/`-F `/`-y `/`-v `
   或**裸路径** (无空白 + 无分号 + 源码扩展名结尾; 避免 `endmodule // x.v` 误判) → 抛明确错误。

### 验证

| 用例 | 修复前 | 修复后 |
|---|---|---|
| `stats -f <非 .f filelist>` | rc=1 + 下游 UndeclaredIdentifier + 误导 `--no-strict` | rc=1 + **"看起来是 filelist, 请用 --filelist"** (无 --no-strict) |
| `stats -f inst_demo.sv` | rc=0 | rc=0 |
| `stats -f cordic_pipeline.v` | rc=0 | rc=0 (不被误判) |

回归测试: 3 条 (误用必须明确提示且无 `--no-strict`; 两个合法语料不得误判) →
`test_json_contract_adversarial.py` 共 19 条; 连同 parity 文件 35 passed。

## 💡 关键发现 / 关键技术 / 决策

1. **截断诊断输出会制造假结论**: 我把 stderr 行截到 100 字符, 而路径恰好 100 字符 →
   误判"消息被吞"。调试时要么打印全文, 要么先在文本里搜关键字 (我后一版就是这么做的)。
2. **回退也要复核**: iter_208 的回退是基于错误判断做出的。本轮先用 `SVQ_DEBUG=1` +
   全文输出复核, 才发现守卫一直有效 —— **"回退"本身也可能需要再验证**。
3. **错误提示不能自相矛盾**: 同一个错误同时给"你传错类型"和"建议用 --no-strict 降级"
   两条互相冲突的建议。按错误类型分支是正解。

## 📎 关联

- 修复: `src/trace/core/compiler.py` (`_reject_non_design_unit` 扩展)、
  `src/cli/_common.py::handle_compilation_error` (提示分支)
- 测试: `sim/tests/cli/test_json_contract_adversarial.py` (R4-1 × 3)
- 前序: `iter_204` (发现) / `iter_208` (尝试与回退, 含两条判据教训)
