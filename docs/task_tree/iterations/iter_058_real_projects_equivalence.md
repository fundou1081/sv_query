# Iteration 058: #7 子任务 1 — 真实项目 strict 编译与等价性评估 (3/6)

**Metadata**:
- **Iteration #**: 058
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #7 迁 pyslang 11.0 native API
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ⚠️ 部分完成 (3/6 项目等价性已评估, 3 个编译阻塞已定位)

## 🎯 本次目标

方豆 "继续" — #7 子任务 1: 评估 native API 在 CVA6/coralNPU/darkriscv/zipcpu/
riscv_core/vortex 上的等价性。前置 = 解决 6 项目 strict 编译。

## 📊 当前状态 / 预期结果

- verify_native_parity.py 已支持真实项目 (filelist/文件列表/incdir)
- 6 项目此前全部 strict 编译失败 (iter_053 查明)
- 预期: 逐个尝试编译入口, 能编的跑 A/B 等价性, 不能编的记录精确阻塞原因

## 🔬 实际结果

### 1. 编译入口逐个解锁 (4 个尝试, 3 个成功)

| 项目 | 编译入口 | 结果 |
|---|---|---|
| **darkriscv** | rtl/ 递归 14 文件 + incdir rtl/ | ✅ **可 strict 编译** |
| **zipcpu** | rtl/ 递归 51 文件 | ✅ **可 strict 编译** |
| **riscv_core** (目录 = riscv 项目) | core/riscv 18 文件 + incdir | ✅ **可 strict 编译** |
| **cva6** | Flist.ariane (等 3 个 filelist) | ❌ 179 elaboration 错误 (UnusedPortDecl/InvalidMemberAccess — pyslang↔CVA6 已知不兼容) |
| **coralnpu** | hdl/verilog RTL-only 79 文件 | ❌ `$clog2()` 0 参 (VL_WIDTH 宏展开问题) |
| **vortex** | 无 filelist (204 文件, OpenCL 混合) | ⏸ 未尝试 (大概率同类阻塞) |

**关键修正**: 之前 (iter_053) 说 "riscv_core 目录为空" 是**误判** — REPOS.md 里
riscv_core 对应 `/Users/fundou/my_dv_proj/riscv` 项目 (RV32IM, core/riscv/ 有 18 个 .v)。

### 2. 等价性评估结果 (3/6 完成)

| 项目 | 实例数 | 结果 |
|---|---|---|
| **darkriscv** | A=7 B=7 | ✅ **EQUIVALENT** — 完整 RTL 上递归与 native MIG 四表完全一致 |
| **zipcpu** | A=75 B=75 | ✅ **GAP-4 已接受** — 37 个实例 id/type 相同, 仅 plain generate block 的 parent 字段差异 |
| **riscv_core** | A=15 B=15 | ✅ **GAP-4 已接受** — 1 个实例 (genblk1 未命名 generate 块) parent 差异 |

**结论: 3 个可编译项目全部与 fixture 级结论一致** — native 与递归等价或仅
已接受的 GAP-4 差异。为 MIG native 迁移提供真实项目实证。

### 3. 工具增强 (verify_native_parity.py)

- 支持 --files 目录递归展开 / --incdir / --projects-only
- 编译失败 → 显式 [COMPILE_FAILED] + 原因 (不静默, 纪律 2)
- **差异归类**: GAP-3/GAP-4 (已接受) vs UNEXPECTED — 输出自解释
- **子进程隔离**: 发现 pyslang **同进程连续编译会状态污染** (fixture 或失败编译
  都会影响后续项目 — darkriscv 7→6, riscv 15→14 实证), --all 对每个项目开独立
  子进程 (--projects-only), 隔离后全部恢复正确

## 💡 关键发现 / 关键技术 / 决策

1. **pyslang 同进程编译状态污染是验证工具的陷阱**: 连续编多个项目 (即使全成功)
   结果会漂移。验证工具必须逐项目子进程隔离 — 这是可信度问题, 不是性能问题。
2. **riscv_core = riscv 项目**: todolist 里的项目名与 REPOS.md 不一致, 已用
   REPOS.md 权威映射修正。
3. **cva6/coralnpu 的阻塞是 pyslang 语义不兼容, 非 filelist 问题**: 修复方向是
   改 pyslang 或改项目代码, 超出 sv_query 范围 — 记录为 #7 的已知边界。

## 📌 阻塞清单 (剩余 3 项目)

| 项目 | 阻塞 | 修复方向 |
|---|---|---|
| cva6 | 179 elaboration 错误 | pyslang 语义修复 or CVA6 代码兼容 (超出范围) |
| coralnpu | $clog2() 0 参宏展开 | pyslang 宏处理 or coralnpu 头文件 (超出范围) |
| vortex | 无 filelist, 204 文件 | 人工整理编译入口 (可行, 工作量大) |
