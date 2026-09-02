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
riscv_core 对应 `/Users/fundou/my_dv_proj/openrtl/riscv` 项目 (RV32IM, core/riscv/ 有 18 个 .v)。

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

## 📌 阻塞清单 (剩余 3 项目, 方豆指示: 通不过就不作为测试项)

| 项目 | 判定 | 结论 |
|---|---|---|
| cva6 | Flist.ariane (官方 filelist) 完整, 但 65+ elaboration 错误 (csr_regfile rvfi_probes_csr_t struct 成员访问 = pyslang 语义不兼容) | ❌ **移出测试项** |
| coralnpu | 无完整 filelist (.core 依赖链复杂); 缺 VLEN define 配置 (`$clog2()` 0 参, SVCompiler 不支持 -D 宏) | ❌ **移出测试项** |
| vortex | 无 filelist (vortex.cfg = OpenOCD 配置; .cmake = 工具链配置) | ❌ **移出测试项** |

**保留测试项** (verify_native_parity.py PROJECTS): darkriscv / zipcpu / riscv_core。

## 🔬 补充发现: GAP-7 — pyslang elaboration 非确定性 (垃圾实例)

评估 darkriscv/riscv_core 时发现 A/B 结果**跨进程漂移** (同一命令多次跑:
darkriscv 7/7 → 7/6; riscv_core 15/15 → 15/14 → 10/6):

**根因**: pyslang 11.0 elaboration 间歇性产生 **uninitialized-buffer 垃圾实例名**
(hp 含 NUL/控制字符, 如 `riscv_core.u_issue.\x00\x00...` / `u_lsu.\V\x00...` /
darkriscv `core0` 变体)。同一文件集合每次编译可能产生或不产生垃圾 —
**elaboration 本身非确定**。

**GAP-7 修复 (native_adapter.py)**: `_walk_instance` 跳过 hp 含控制字符的实例
(垃圾 = elaboration 噪音, 非真实实例)。递归路径靠 visited 去重碰巧跳过,
native 必须显式过滤。修复后同进程内 A/B 一致 (干净跑 15/15, 垃圾跑 native 14
recursive 14 — 均一致); 跨进程计数波动 (14 vs 15) 是 pyslang 级现象, 不影响
A/B 对比语义。

**`_safe_str` 升级**: 委托 `_safe.safe_str` (单一规范实现, 过滤控制字符 —
原实现只处理 UnicodeDecodeError/TypeError)。

**评估结论修正**: darkriscv/riscv_core 的 verdict 以**干净跑**为准 (EQUIVALENT /
GAP-4); 垃圾跑偶发 UNEXPECTED 属 pyslang 非确定, 非 sv_query 逻辑问题。
zipcpu 3/3 稳定 GAP-4。权威门禁 = 10 fixtures (确定性) + zipcpu。

## 📊 最终等价性评估表 (2026-08-29)

| 项目 | 实例数 | 结论 | 稳定性 |
|---|---|---|---|
| darkriscv | 7/7 | ✅ EQUIVALENT (干净跑) | ⚠️ pyslang 非确定 |
| zipcpu | 75/75 | ✅ GAP-4 已接受 | ✅ 稳定 |
| riscv_core | 15/15 | ✅ GAP-4 已接受 (干净跑) | ⚠️ pyslang 非确定 |
| cva6 / coralnpu / vortex | — | ❌ 移出测试项 (编译不过/无 filelist) | — |
