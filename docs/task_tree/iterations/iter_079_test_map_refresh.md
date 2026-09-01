# Iteration 079: 全量测试地图重梳 (TEST_MAP.md 301 文件 / 2997 测试)

**Metadata**:
- **Iteration #**: 079
- **Task Tree Level**: L1
- **Parent Task**: 测试资产梳理 (方豆 "现在再重新梳理项目里已有的测试")
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (TEST_MAP.md 重写, 统计实测, 引用全验证)

## 🎯 本次目标

方豆 "现在再重新梳理项目里已有的测试" — TEST_MAP.md 自 iter_061 (2026-08-29,
317/3033) 后未更新, 期间经历 iter_062~078 大量测试变动, 需要重新实测统计并重写。

## 📊 当前状态 / 预期结果

- 旧 TEST_MAP: 317 文件 / 3033 测试 (iter_061 快照)
- 预期: pytest --collect-only 实测当前全量, 重写目录统计 + 功能域分类

## 🔬 实际结果

### 1. 实测统计 (pytest --collect-only, 2026-09-01)

| 目录 | 文件 | 测试 | 变化 (vs iter_061) |
|---|---|---|---|
| unit | 95 | 1095 | 文件 96→95, 测试 973→1095 (+122) |
| regression | 94 | 766 | 文件 90→94, 测试 722→766 (+44) |
| integration | 52 | 422 | 文件 53→52, 测试 384→422 (+38) |
| cli | 46 | 389 | 测试 387→389 |
| usage | 10 | 298 | 不变 |
| 根 (truth) | 3 | 22 | case27(4) + d1_generate(11) + spec_unsupported(7) |
| poc | 1 | 5 | 不变 |
| **总** | **301** | **2997** | |

**差异来源**: iter_064~066 行为断言升级 (4 域, module 63 + sva 11 + constraint 7 +
covergroup 22) + iter_073/074 connection_extractor (13) + bit_select_handler (12) +
iter_075/076 class_method/task_function 新增 + iter_070 generate_real_world 重建。

### 2. TEST_MAP.md 重写

- 目录总览表更新为实测值, 标注 iter_061→078 变化
- 功能域分类: 新增 2.2 连接提取/位选小节 (iter_073/074 补齐的直接单元测试),
  更新 L1 语法清单 (test_class(6)→实际 class 文件), truth 层独立 2.12 节
- 关键测试集命令表更新基线 (unit 1091 passed + 4 沙箱 failed; regression 766 passed)
- 观察更新: unit 覆盖缺口已补齐 (TECH_MAP 2.4/2.6 ✅), 4 个 unit 失败归因沙箱 cache

### 3. 引用全验证

脚本抽取 TEST_MAP 全部 `test_*` 引用, 与 sim/tests 实际文件比对:
- 缺失引用: **0** (修正了旧版遗留 test_class(6)/test_no_string_fallback/test_schema)
- 通配引用 (test_dataflow_* 等 9 处): 刻意简写, 合理保留

## 💡 关键发现 / 决策

1. **统计必须实测, 不能沿用旧快照**: 旧 TEST_MAP 的 317/3033 含已删除的
   removed_features (11/236) — 现 301/2997 是当前真实可收集集。
2. **文件级引用验证可自动化**: 抽取 `test_*` + 目录列表比对, 10 秒找出 3 处
   旧版遗留错误引用 — 后续 TEST_MAP 更新应带这个校验。

## 📌 状态

- ✅ TEST_MAP.md 重写完成 (301 文件 / 2997 测试, 实测)
- 提交: docs/TEST_MAP.md + 本迭代记录
