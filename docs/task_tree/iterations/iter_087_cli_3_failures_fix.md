# Iteration 087: cli 层 3 个 pre-existing 失败修复 (1 序列化根因 + 1 断言 + 纪律)

**Metadata**:
- **Iteration #**: 087
- **Task Tree Level**: L1
- **Parent Task**: Test_Assets_ABC → B 组复查后续 (iter_086 顺带发现)
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "把新发现的3个也改一下吧")
- **Outcome**: ✅ 成功 (unit+cli 全绿)

## 🎯 本次目标

iter_086 全量回归时发现 3 个 pre-existing cli 失败 (与 B 组改动无关, 被旧
"4 沙箱 env 失败" 记录掩盖)。方豆拍板一起修:
1. test_picorv32_validation::test_fanin_push_data_i — rc=1 `'NoneType' object is not iterable`
2. test_picorv32_validation::test_fanout_pop_data_o — 同上 (fanout)
3. test_visualize_compute::test_compare_greater_appears — DOT→SVG 过时断言

## 📊 当前状态 / 预期结果

- 3 failed / 1481 passed (unit+cli, iter_086 实测基线)
- 预期: 3 个转绿, 无回归

## 🔬 实际结果

### 根因 1: AST cache 序列化崩溃 (models.py) — 真 bug, 影响面大

`build_graph(use_cache=True)` 序列化图到缓存时:
- `models.py to_dict()`: `"width": list(node.width)` → 节点 width=None 时
  `TypeError: 'NoneType' object is not iterable`
- 触发节点: strict_uart fifo 的**内存位选** `sync_fifo.mem[wr_ptr_q[$clog2(SIZE)-1:0]]`
  (width 提取失败 → graph_builder.py:681/695 显式传 width=None 的合法 sentinel)
- 后果: **所有开 cache 的 CLI subprocess 测试**在解析含内存位选的模块时 rc=1 —
  不只是这 2 个测试, 是整类命令 (trace fanin/fanout 等) 的隐藏炸弹
- from_dict 同样: `tuple(None)` 会崩

**修复 (根因层, models.py)**:
- to_dict: `list(node.width) if node.width is not None else None` — 显式保留 None
- from_dict: 显式 `null` → None; 旧格式缺 width 键 → 保持 (0,0) 回退 (不改变历史行为)
- 不伪造 (0,0): None = "未知宽度" 是诚实状态, 伪造会污染下游 (AGENTS.md 纪律)

**回归测试**: test_snapshot.py 新增 test_roundtrip_width_none_preserved —
width=None 往返保留 None 且不崩溃。

### 根因 2: test_compare_greater_appears 断言过时 (同 darkriscv 类)

V100 SVG 渲染把比较条件分解为独立 `&gt;` op 节点 + `?: (a, b)` 标签,
不再是 DOT 时代的连写边标签 'a > b'。断言改为校验 SVG 结构
(裸 op 符号 `&gt;` + ternary 标签 `?: (a, b)`), 跟随同文件 '+' / '&amp;' 约定。

### 纪律修复: 删测试内 --no-strict

- test_picorv32_validation.py: 5 处 --no-strict → --strict (类名本就叫 TestStrict*)
- test_visualize_compute.py: 1 处 (共享 helper)
- 实测 strict 模式下两文件全绿 (19 passed) — fixture 干净, 无需降级

## 💡 关键发现 / 决策

1. **cache 序列化是 CLI subprocess 测试的隐藏依赖**: to_dict 崩溃会以
   `Error: 'NoneType' object is not iterable` 形式冒到 CLI 顶层, 极易被误判为
   "环境问题" 或 "信号无驱动" — iter_086 的 cli "4 沙箱 env 失败" 记录掩盖了它。
2. **width=None 是合法状态**: graph_builder 显式用它表示"宽度提取失败",
   序列化契约必须支持 None 往返, 不得伪造 (0,0) (伪造 = 假数据)。
3. **width 提取缺口 (遗留, 非本次)**: 内存位选 `mem[wr_ptr_q[$clog2(SIZE)-1:0]]`
   的宽度无法解析 (应为元素宽度) — 属 width 提取器功能缺口, 已记录, 待评估。
4. **决策**: 根因修序列化契约 (方案 A), 不修 width 提取器 (方案 B, 超范围)。

## 📌 状态

- ✅ models.py to_dict/from_dict 支持 width=None 往返 (根因)
- ✅ test_compare_greater_appears 断言更新 (SVG 结构)
- ✅ 两测试文件 --no-strict → --strict (纪律)
- ✅ 新增序列化回归测试 (test_snapshot +1)
- 验证: 两文件 19 passed; snapshot 8 passed; unit+cli 全量全绿
