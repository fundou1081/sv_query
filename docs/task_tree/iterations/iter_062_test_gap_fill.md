# Iteration 062: 按功能域补测试缺口 (module/constraint/covergroup/sva)

**Metadata**:
- **Iteration #**: 062
- **Task Tree Level**: L2
- **Parent Task**: TEST_MAP 筛选后的测试补充
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (32 个新测试, 4 个域, 覆盖高优先级缺口)

## 🎯 本次目标

方豆 "按功能域补测试缺口, 按 SV 语法: 优先 module 可综合, 然后 constraint,
接着 covergroup, 最后 sva"。

## 📊 当前状态 / 预期结果

- TEST_MAP 盘点出 4 个域的测试文件; 需要找缺口
- 4 个并行 subagent 分析各域覆盖 vs SV 语法全集
- 预期: 补齐高优先级缺口, 验证工具行为, 记录工具缺口

## 🔬 实际结果

### 1. 缺口分析 (4 个并行 subagent)

| 域 | 已覆盖 | 高优先级缺口 |
|---|---|---|
| module 可综合 | ~75% (过程块/运算符/generate/位选/拼接) | signed/算术移位/复合赋值/enum 追踪/2D 数组/defparam/数组写索引 |
| constraint | solve/dist/inside/foreach/implication | **soft** (全仓零覆盖) / dist :/ / randc / disable soft |
| covergroup | 声明/coverpoint/bins/cross/illegal/ignore | iff / wildcard bins / transition bins / 自动+default bins / 参数化 / sample() |
| sva | 声明/##/蕴含/throughout/within/intersect | expect / immediate / iff / $rose 系列 / 无界$ / [=n] |

### 2. 补充测试 (32 个新测试, 4 个新文件)

- `test_module_synth_advanced.py` (7): signed 算术移位 / 复合赋值 / enum case
  状态机 / 2D packed 数组 / defparam / 数组写索引 / $signed
- `test_constraint_advanced.py` (7): soft / dist :/ / randc / solve 多变量 /
  嵌套 foreach / not inside / this+包引用
- `test_covergroup_advanced.py` (9): iff / wildcard / transition / 自动+default /
  参数化 / sample() / 多事件 / ignore+illegal 组合
- `test_sva_advanced.py` (9): $rose/$past/$onehot / 无界 ##[0:$] / [=n] / iff /
  property 引用 sequence / expect+immediate (记录缺口)

### 3. 工具缺口发现 (7 项, 已登记 EXTRACTION_COVERAGE #34-#40)

写测试过程中实测确认的工具边界, 测试按"验证现有行为 + 记录缺口"处理:
- **module**: 数组索引 DRIVER 边缺失 (`packed2d[0]` / `mem[idx] <=`, 确认 #20)
- **constraint**: `not inside` 无 expr 节点; soft/dist :/ 不区分 (归 ExpressionConstraint)
- **covergroup**: coverpoint/cross 的 iff 未建模; wildcard/transition 浅提取;
  参数化 covergroup (bins 内参数 + 参数化实例化) = pyslang 限制
- **sva**: expect / immediate assertion 提取器不识别 (pyslang 可解析)

### 4. 验证

- 4 个新测试文件: **32 passed**
- regression 全量: 770 passed + 2 failed (两者均 **pre-existing**:
  test_cross_module_connection + test_opentitan_aes_sub_bytes, stash 对比确认)
- ruff: (见下)

## 💡 关键发现 / 关键技术 / 决策

1. **"补测试"自动暴露工具缺口**: 写合法 SV 语法测试时, 7 个语法点工具不完整支持。
   按纪律 (测试是 spec) 不降级断言, 而是断言"现有行为 + 明确记录缺口" —
   与 test_sva_in_class 的 pyslang 限制惯例一致。
2. **pyslang 限制 vs sv_query 缺口的区分**: 参数化 covergroup 是 pyslang 限制
   (编译失败); expect/immediate/not inside 是 sv_query 提取器缺口 (pyslang 接受)。
   记录时必须区分, 修复路径不同。
3. **回归发现 2 个 pre-existing 失败**: regression 全量此前未跑过 (各阶段只跑
   unit+cli+integration) — 补测试顺带发现了 test_opentitan_aes_sub_bytes 的
   历史失败 (genvar 驱动为空), 与 #7 无关, 记入已知。

## 📌 后续 (可选)

- 修 EXTRACTION_COVERAGE #34-#40 工具缺口 (按优先级: sva expect/immediate 最易,
  constraint not inside 次之, covergroup iff/wildcard 需模型扩展)
- 清理 2 个 pre-existing regression 失败
