# Iteration 121: SVA 对抗缺口修复 — 参数/序列/局部/函数/generate/option 污染

**Metadata**:
- **Iteration #**: 121
- **Task Tree Level**: L2 (方豆 "constraint covergroup sva 对抗" → 开工)
- **Parent Task**: 对抗验证缺口修复 (backlog 1-6)
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (6/6 SVA 缺口; constraint inline / covergroup cross 排 iter_122)

## 🎯 本次目标

修对抗验证发现的 SVA 提取缺口 1-6 (sva_extractor):
formal 参数替换 / sequence 引用展开 / local var / 用户函数 / generate 内断言 /
covergroup option 污染。

## 🔬 实际结果

### 探查 (语法树结构)

SVAExtractor 全程 syntax 树 + 裸 IdentifierName 收集 → 4 类泄漏同源:
- formal/local 在 AssertionItemPortSyntax/DeclaratorSyntax 的 .name Token (非
  IdentifierNameSyntax 子节点) — 旧收集漏 → x,y,tmp 留在 signals
- property 引 sequence / 函数调用都是 **InvocationExpressionSyntax** — callee
  名被当信号 (s_seq/f), sequence 内部信号不展开
- y[i] 的 base 'y' 是 IdentifierSelectNameSyntax 的 Token 子节点 (selector i 是
  BitSelect IdentifierName) — 旧逻辑收 i 丢 y
- covergroup option/type_option (ClassProperty) 被 'Property' in kind 子串匹配
  误当 property
- generate 内断言经 ProceduralBlock → ConcurrentAssertionMemberSyntax 包装,
  _walk 不下钻 generate + member 不解包 → 0 提取

### 修复 (sva_extractor 6 处)

| # | 改动 |
|---|---|
| 1/3 | _collect_decl_identifiers: 收 AssertionItemPortList/LocalVariableDeclaration 下 DeclaratorSyntax + AssertionItemPortSyntax 的 .name Token → formal/local 从 signals 剔除 |
| 1b | _capture_invocation_args: assert property(p(a,b)) 实参记入; post-pass 并入 property signals; _find_property_ref 识别 Invocation callee |
| 2 | _resolve_refs_and_args post-pass: sequence 名 → 展开其 signals (fixpoint, 环保护); property.sequences 记录; assertion 并入 property 展开集 |
| 2b/多时钟 | EventControl/SignalEvent 子树不进信号 (时钟走 clock 字段) |
| 4 | Invocation 分支跳过 callee IdentifierName, 只递归实参 |
| 5 | _walk 下钻 GenerateBlockArray/GenerateBlock; _parse_assertion_syntax 解包 ConcurrentAssertionMember; _extract_signals_from_syntax: IdentifierSelectName 收 base Token + 跳 selector, 'Select' 节点只收 .value |
| 6 | Sequence/Property kind 收窄为精确 SymbolKind 匹配 (不再子串) |

### 验证 (对抗 6 场景 → 全绿)

| 场景 | 修复前 | 修复后 |
|---|---|---|
| p_arg(a,b) | [x,y,c] (formal 泄漏) | [a,b,c] + ref=top.p_arg |
| p_loc tmp | [tmp,a,b,out] | [a,b,out] |
| p_fn f(data) | [f,data,a,b] | [data,a,b] |
| p_multi (s_seq) | [s_seq,clk2,c] | [a,b,c] |
| generate ×4 | 0 断言 | 4 断言 signals={a,y} ref='' |
| interface cg | option/type_option 假 property | 只剩 p_req |

- 新 unit 8 (test_sva_adversarial: 6 类); SVA 既有 83 passed 零回归
- 全量回归结果见 commit

## 💡 关键发现 / 决策

1. SVAExtractor 语法树行走的 4 类泄漏同根: "syntax 裸 IdentifierName = 信号"
   假设对 formal/local/函数/callee/base 全不成立 — 按节点型语境区分 (容器
   Token / Invocation callee / IdentifierSelectName base)。
2. option 污染来自 kind 子串匹配 ('Property' in kind) — 精确匹配是通用纪律
   (此前 RTL 侧多次同型教训)。
3. generate 内断言是 ProceduralBlock 包装 ConcurrentAssertionMember —
   与 RTL generate 修复同理需显式下钻 + 解包。

## 📌 状态

- ✅ 6 缺口修复 + unit 8; 全量回归见 commit; backlog 剩 constraint inline /
  covergroup cross (iter_122 候选)
