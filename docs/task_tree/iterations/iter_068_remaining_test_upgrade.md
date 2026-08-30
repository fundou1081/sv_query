# Iteration 068: 剩余测试升级 (11 文件) + strict 纪律冲突

**Metadata**:
- **Iteration #**: 068
- **Task Tree Level**: L2
- **Parent Task**: 测试升级 (方豆 "继续" — 升级剩余纯 AST 文件)
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手 (2 个并行 subagent)
- **Outcome**: ⚠️ 部分完成 (10 文件已提交; test_generate_real_world 有 strict 纪律冲突待方豆决策)

## 🎯 本次目标

继续升级剩余纯 AST 测试文件 (方豆 "继续")。2 个并行 subagent:
- Group A: test_case_extraction / case_multi_branch / class_method / class_oop / dpi / task_function (6 文件)
- Group B: test_always_ff / port_inout / interface_basic / modport_direction / generate_real_world (5 文件)

## 📊 当前状态 / 预期结果

11 个纯 AST 文件, 预期升级为含行为断言。

## 🔬 实际结果

### Group A (6 文件 18 测试, 全过)

- case: 条件 DRIVER 边断言 (sel == 2'b0 等 condition)
- class method/oop: CLASS_PROPERTY 节点 + CONSTRAINS 边 + IS_INSTANCE_OF/MEMBER_SELECT 边
- dpi: 断言 graph 无 DPI 信号节点 (外部接口, 期望行为)
- task_function: function 两段 DRIVER 链 (arg→func→lhs); task 输出参数缺口 (EmptyArgument 占位边)

**工具缺口登记** (EXTRACTION_COVERAGE #41-#44): class 方法内赋值无边 / task 输出参数占位边 / task 多语句无边 / DPI 调用无边

### Group B (5 文件 47 测试, 全过)

- always_ff: DRIVER (nonblocking) + CLOCK + RESET 边
- port_inout: 三态缓冲条件 DRIVER 边 (condition='en')
- interface/modport: 跨接口 DRIVER 边
- generate_real_world: 12 个新行为测试验证真实 ZipCPU DRIVER 边

### ⚠️ strict 纪律冲突 (待方豆决策)

**test_generate_real_world.py 用 `strict=False`** (line 153) — 与 AGENTS.md 核心
纪律 #1 (禁 --no-strict) 冲突。

**核实**: 原文件 (HEAD) 已用 `--no-strict` (line 85, Plan F1.5 遗留) — Group B
是延续既有违规, 非新引入。Group B 的辩护: "ZipCPU 文件含未知子模块,
strict=False 才能产出 partial AST, 与 CLI 同一条路径" — 但纪律明确禁止。

**选项** (待方豆):
a) 接受例外: 记录 TEMPORARY + 理由, 保留行为断言
b) 移除 generate_real_world 的新行为断言 (回退, 保留原 CLI 断言)
c) 修 fixture: 补完整 filelist 让 strict 编译过 (工作量大)

## 📌 最终处理 (方豆 "继续" — 按最干净纪律)

- 已提交: 10 个无争议文件 (A 组 6 + B 组 4) — 28 测试全过
- **test_generate_real_world.py 已还原** (git checkout): 移除新增 strict=False
  断言 (不引入新违规), 恢复原 25 个测试
- **原文件 --no-strict 遗留** (line 85, Plan F1.5): pre-existing 违规, 已登记
  EXTRACTION_FAILURES — 待后续单独决策 (修 filelist 或接受)
