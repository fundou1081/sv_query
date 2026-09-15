# Iteration 206: R4-4 修复 — 输入路径显示形态不一致 (9 failed → 0)

**Metadata**:
- **Iteration #**: 206
- **Task Tree Level**: L2 (输出一致性)
- **Parent Task**: iter_205 交接 (方豆 "好，push完再继续")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 该文件 9 failed → **15 passed** + 抽掉 11 处重复逻辑

## 🎯 本次目标

执行 iter_205 的三步计划第一步: 修 R4-4 (`test_cli_filelist_parity.py` 长期失败)。

## 🔬 实际结果

### 重要更正 (先纠正我上一轮的判断)

上一轮我判断"该文件单独跑失败、全量套件绿 → 测试隔离缺陷"。**本轮实测推翻**:
全量 canonical 同样报 **9 failed** (`9 failed, 3322 passed`) —— 所以它不是隔离问题,
而是 **HEAD 上真实的既有失败**: `--file` 与 `--filelist` 两种模式对**同一个文件**
输出不同的路径字符串:

```
-风险分析: /var/folders/.../test.sv          ← --file  (CLI 原始参数, 未 resolve)
+风险分析: /private/var/folders/.../test.sv  ← --filelist (parse_filelist 已 resolve)
```

(macOS 上 `/var` 是 `/private/var` 的符号链接; iter_193 统一解析器后 filelist 侧
会 `resolve()`, 而各命令显示 `--file` 时直接用原始参数 → 形态不一致。)

### 通用修复 (不是逐处打补丁)

- 新增 `cli/_common.py::display_path(file, sources, filelist)` — 统一"被分析文件"的
  显示路径形态 (`--file` 也 resolve);
- **11 处重复逻辑收敛**到该 helper: `risk`(1) / `cdc`(2) / `sva`(3) / `timing`(1) /
  `verify`(1) / `controlflow`(3);
- `_build_tracer` 的 `--file` 分支 sources key 也 resolve (与 filelist 侧同形态)。

### 结果

| 阶段 | 该文件 |
|---|---|
| 修复前 (HEAD) | **9 failed / 6 passed** |
| risk 单点修 | 8 failed |
| + cdc/sva helper | 5 failed |
| + timing/verify helper | 3 failed |
| + controlflow helper | **15 passed** ✅ |

## 💡 关键发现 / 关键技术 / 决策

1. **先验证"是不是既有问题"再动手**: 我上一轮把 9 个失败归因为"测试隔离缺陷"并
   因此回退了 R4-3 修复。本轮实测全量 canonical = `9 failed` → 判断错了。**教训**:
   "局部失败 / 全量通过"的结论必须用**当期全量实测**确认, 不能引用上一轮的记忆数字
   (上一轮门禁是绿的, 但那是更早的 commit)。
2. **同一逻辑复制 11 处 = 形态不一致的温床**: 每个命令各自写一遍
   `display_file = file if file else sources.keys()[0] ...` → 一处改了解析器 (iter_193),
   11 处显示逻辑全部滞后。收敛到 helper 后, 这类分歧不可能再分散发生。
3. **修复是"消除差异"而不是"改断言"**: 断言 (两模式输出必须一致) 未动, 改的是产品
   行为 (显示同一形态) —— 符合 AGENTS "assertion 是 spec" 的要求。

## 📢 下一步 (按 iter_205 计划)

R4-4 已解决 → **R4-3 的修复现在可以安全落地** (方案已验证: `_read_filelist_full` 交出
`spec.include_dirs` + `_build_tracer` 合并; 实测 `graph/stats --filelist` rc=1→0),
落地后重跑一次门禁; 然后 R4-1 (误用提示)。

## 📎 关联

- 修复: `src/cli/_common.py` (`display_path`) + 6 个命令文件
- 测试: `sim/tests/unit/test_cli_filelist_parity.py` (15 passed, 未改断言)
- 前序: `iter_205_r4_3_filelist_incdir.md` (R4-3 真因 + R4-4 交接)
