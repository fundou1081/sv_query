# Iteration 066: sva 域行为断言升级

**Metadata**:
- **Iteration #**: 066
- **Task Tree Level**: L2
- **Parent Task**: iter_062/063/064/065 测试质量改进
- **Created**: 2026-08-30 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (3 文件 11 测试全过, 行为断言补齐)

## 🎯 本次目标

按方豆指示升级 sva 域的 3 个测试文件, 让断言更严格 — 保留现有
AST/SyntaxKind 断言, **补充行为断言** (SVAExtractor 结构化视图):
- `sim/tests/regression/test_sva.py` (5 测试: sequence/property/assert/assume/cover 声明)
- `sim/tests/regression/test_sva_timing.py` (3 测试: ##延迟/repetition/goto)
- `sim/tests/regression/test_sva_timing_enhanced.py` (3 测试: throughout/within/intersect)

行为金标准: **SVAExtractor 提取 + signal_refs 索引查询**
(SVAPropertyNode.signals/operators/clock, SVASequenceNode.signals/timing_ops/clock,
SVAAssertionNode.kind/property_ref/message, SVAGraph.signal_refs/
get_assertions_for_signal) — 比 SyntaxKind 严格, 因为它验证"信号是否被
提取、操作符是否被记录、signal_refs 是否建立、property_ref 链路是否正确"。

## 📊 当前状态 / 预期结果

- 3 文件 11 测试, 原 11/11 passed (基线)
- 预期: 每测试在原 SyntaxKind 断言之上补 SVAExtractor 结构化行为断言
- 预期: 3 文件 11 passed (不退化)

## 🔬 实际结果

### 升级范围

| 文件 | 测试 | 行为断言新增 |
|---|---|---|
| test_sva.py | test_sequence_declaration | sequence id 'top.s1' 存在, signals {a,b}, timing_ops 含 ##1, clock=clk, signal_refs 索引 a/b→top.s1 |
| | test_property_declaration | property id 'top.p1' 存在, signals {a,b}, operators 含 |->, clock=clk, disable_iff 非空, signal_refs 索引 a/b→top.p1 |
| | test_assert_property | assertion kind='assert', property_ref='top.p1', message='fail' (来自 `else $error("fail")`), get_assertions_for_signal('a') 含 assert 类型 |
| | test_assume_property | assertion kind='assume', property_ref='top.p1', get_assertions_for_signal('b') 含 assume 类型 |
| | test_cover_property | assertion kind='cover', property_ref='top.p1', message='' (cover 无 else 分支) |
| test_sva_timing.py | test_delay_sequence | signals {a,b,c}, timing_ops 含 ##1 和 ##2, clock=clk, signal_refs 索引全 3 信号 |
| | test_repetition_sequence | signals 含 a, clock=clk, signal_refs 索引 a→top.s2 |
| | test_goto_sequence | signals {a,b}, clock=clk, timing_ops 含 ##1, signal_refs 索引全 2 信号 (注: [->2] 在当前提取器中不单独记为 timing_op, 这是 iter 实测行为, 不硬断言) |
| test_sva_timing_enhanced.py | test_throughout_sequence | signals {a,b,c}, clock=clk, timing_ops 含 ##1 (throughout 内的延迟), signal_refs 索引全 3 信号 |
| | test_within_sequence | signals {a,b,c,d}, clock=clk, timing_ops 含 ##1 (within 两侧延迟都被捕获), signal_refs 索引全 4 信号 |
| | test_intersect_sequence | signals {a,b}, clock=clk, signal_refs 索引全 2 信号 (intersect 是零延迟, 不必断言 timing_ops 含延迟) |

### 实测提取器行为细节 (写断言前实测)

- **module prefix**: SVAExtractor 用 module 名作为 prefix, sequence/property
  id 形如 `'top.s1'` / `'top.p1'` (不是孤立 `'s1'`)
- **timing_ops 去重**: ##1 a ##1 b 链路中 ##1 出现 2 次, 测试用 `assertIn('##1', ops_str)` 检查"含"而非长度
- **[->n] goto repetition**: 当前提取器对 [->2] 不单独记录为 timing_op
  (实测: `a [->2] ##1 b` → timing_ops `['##1', '##1']`), 故仅断言 ##1
  出现, 不硬断言 [->2]
- **throughout/within/intersect**: 提取器把内部信号全部提取, ##1 也被捕获,
  但 operators 不单独记录这些关键字 — 行为断言聚焦信号 + clock + timing_ops
- **cover 无 else 分支**: message 字段实测为 `''` (空字符串), 测试断言 message=''
- **assert 的 property_ref**: 实测 `top.p1` (含 prefix), 测试用
  `'top.p1'` 而不是 `'p1'`
- **get_assertions_for_signal 反查**: 信号 a/b 的 signal_refs 指向
  property id (`top.p1`), 而非 assertion id (`top.assert_0`), 但
  SVAGraph.get_assertions_for_signal 实现了"如果 ref 是 property_ref,
  也算关联"的查询, 所以可正确反查到 assertion

### 验证

- 目标 3 文件: `pytest sim/tests/regression/test_sva.py sim/tests/regression/test_sva_timing.py sim/tests/regression/test_sva_timing_enhanced.py -q`
- 结果: **11 passed in 0.12s** ✅
- regression 全量: 772 passed, 2 failed (pre-existing,
  test_cross_module_tracking.test_cross_module_connection + 
  test_opentitan_aes_sub_bytes.test_sub_bytes_genvar_iteration — 与
  本次 SVA 改动无关, git stash 验证 pre-existing)
- ruff: 未跑 (无 .py 结构性变更)

## 💡 关键发现 / 关键技术 / 决策

1. **行为金标准比 SyntaxKind 严格**: 原测试只断言"pyslang 解析出
   SequenceDeclaration / AssertPropertyStatement" — 这只能证明"语法合法",
   不能证明"提取器正确抽取语义"。新行为断言验证了提取器对**真实语义
   AST** 的结构化视图: 信号是否被识别、操作符是否被记录、property_ref
   链路是否正确、signal_refs 索引是否能双向反查。
2. **测试"实际行为"而非"理想行为"**: goto repetition [->2] / throughout /
   within / intersect 这些关键字在当前提取器实现中**不单独作为
   timing_op 记录**, 这是 iter_066 实测事实, 不强行硬断言 [->2]
   出现 — 测试断言的是"信号被提取 + ##1 被捕获 + clock 正确", 这已经
   比 SyntaxKind 严格, 同时不掩盖提取器的真实能力。
3. **测试断言 ID 命名规范**: SVAExtractor 用 module 名作为 prefix,
   sequence/property id 形如 `top.s1` / `top.p1`, 测试断言要按这个
   格式, 否则断言永远 fail。
4. **测试写法原则 (iter_064 沉淀的延续)**: 语法覆盖测试 = AST 断言 +
   行为断言. iter_064 做了 4 个域 (constraint/sva-advanced/covergroup),
   iter_065 做了 constraint_derivative, **iter_066 把 sva 域剩下的 3 个
   文件补齐**, 现在 sva 域 5 文件 (advanced + 3 个 + in_class) 行为断言
   全部到位。

## 🔄 Next Action

无 (sva 域行为断言全部到位)。后续可考虑:
- covergroup 域其他文件 (iter_064 已有 covergroup_advanced, 其他 covergroup
  测试可考虑同样升级)
- 模块化 SVA 测试: 多 module / 类内 SVA / sequence 引用等复杂场景
