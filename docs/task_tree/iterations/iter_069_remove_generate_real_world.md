# Iteration 069: 移除 test_generate_real_world (strict 编译不过)

**Metadata**:
- **Iteration #**: 069
- **Task Tree Level**: L2
- **Parent Task**: 测试清理 (方豆: "遗留的那些。由于编译过不了, 就去掉吧")
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (移除 1 个 strict 编译不过的测试文件, 0 回归)

## 🎯 本次目标

方豆: "遗留的那些。由于编译过不了, 就去掉吧" — 移除
`test_generate_real_world.py` (ZipCPU 真实 RTL 含未知子模块, strict 编译不过,
依赖 --no-strict 才能跑 — 与之前 6 项目编译不过的处理一致)。

## 📊 当前状态 / 预期结果

- 文件用真实 ZipCPU 项目文件 (wbxbar/idecode/wb_tb/axi2axilite), 非仓库 fixture
- 预期: 删除无孤儿, 无外部引用

## 🔬 实际结果

1. **引用核实**: 无外部引用 (只有自身 docstring)
2. **删除**: `git rm sim/tests/regression/test_generate_real_world.py` (25 测试)
3. **文档**: EXTRACTION_FAILURES 移除 --no-strict 遗留登记 (问题已解决);
   TEST_MAP 无独立条目需改 (2.8 真实项目节提及, 已随删除不适用)
4. **回归**: (见下)

## 💡 关键发现 / 决策

- 与 6 项目编译不过的处理一致 (iter_058: "通不过就不作为测试项") — 测试的可
  编译性是前提, 依赖 --no-strict 的测试等于没测 (纪律 #1 精神)
- 真实项目 generate 覆盖损失: wbxbar/idecode 等 4 个真实 RTL 的 generate 行为
  验证缺失 — 若未来 ZipCPU 能 strict 编译 (补 filelist), 可恢复该文件

## 📌 状态

- test_generate_real_world.py 移除, 纪律 #1 冲突清零
- 今日测试升级总览: 24 文件升级 (iter_067/068) + 1 移除 (iter_069)
