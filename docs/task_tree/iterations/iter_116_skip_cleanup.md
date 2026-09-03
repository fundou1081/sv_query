# Iteration 116: 7 个 skip 处置 — serv 解锁 / neorv32+zipcpu 移除 / d1 mutex 收编

**Metadata**:
- **Iteration #**: 116
- **Task Tree Level**: L2 (测试资产整理, 方豆 "再看那7个skip是啥" → "看情况可以去掉哪些? 或重写")
- **Parent Task**: 测试资产 (Test_Assets) 收尾
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

处置全量回归的 7 个 skip (integration real_project_viz ×3 + d1 mutex ×4):
逐个诊断"能否去掉 (真跑)"或"按测试目的重写"。

## 📊 当前状态

7 skip = real_project_viz 3 (serv/neorv32/zipcpu) + d1 lookupName 4 (mutex)。

## 🔬 实际结果

### 诊断 (决定性发现)

1. **三个 real_project skip 的测试路径全部失效** (openrtl 迁移后 stale):
   - serv: 测试指向 `serv/serv.v` — 实际顶层是 `serv/rtl/serv_top.v` (多文件)
   - neorv32: 指向 `neorv32_top.v` — 当前 clone 是 **VHDL** (rtl/core/*.vhd)
   - zipcpu: 指向 `zipcpu.v` — 新版仓库重构: 真核在 `rtl/core/` 子模块,
     rtl 顶层 (zipbones/zipaxil/zipsystem) 是纯连线 wrapper (实测 dataflow SVG
     104×100 近空)
2. **serv 端到端实测可行**: rtl/*.v filelist + serv_top → strict 通过, **747KB
   SVG, 4.1s** — 可直接解锁
3. **d1 mutex 深挖**: 与 pytest 上下文无关 — 纯 subprocess 也崩; 同进程累计
   ~13 次 lookupName 必崩; def 包装/脚本文件/exec 模式均崩, 仅**直排 python -c
   单 case (≤4 查询)** 稳定 (16/16)

### 处置

| skip | 处置 | 结果 |
|---|---|---|
| serv | **解锁** — 参数化改 (name, sources, target), 多文件合成临时 filelist 走 --filelist | ✅ 真跑 (SVG 747KB) |
| neorv32 | **移除参数** — VHDL 不符 SV 测试目的 | ✅ |
| zipcpu | **移除参数** — 重构后 wrapper 顶层无数据通路, ELK 验证价值低 (注释理由) | ✅ |
| d1 ×4 | **收编** — 直排 `python3 -c` snippet × 每 case 独立 subprocess, 4 case 全真跑 (含类型断言 NetSymbol/ParameterSymbol/None) | ✅ 1 test 替 4 skip |

### 验证

- test_real_project_viz: 3 项目全跑 (darkriscv/picorv32/serv + smoke) **4 passed**
- test_d1: **8 passed** (mutex 4 case 收编为 1 subprocess test, 非 skip)
- 全量回归结果见 commit

## 💡 关键发现 / 决策

1. **skip 会掩盖路径失效**: 3 个 skip 指向的文件 openrtl 迁移后根本不存在 —
   "file not found" 本会 pytest.skip, 显式 mark.skip 让 stale 参数永远不被发现。
   处置后这类参数要么真跑 (serv) 要么移除 (neorv32/zipcpu), 不留死参数。
2. **pyslang lookupName mutex 真根因** (比 SKIP NOTE 更深入): 同进程累计查询
   必崩, 与 pytest 无关; 触发量与代码形态相关 (直排最小代码稳) — workaround
   是"每 case 独立进程 + 最少查询", 已记录, upstream 修复后可改回普通测试。
3. 多文件项目测试统一走 "临时 filelist + --filelist" (CLI 已支持), 参数化从
   单文件升级为 sources 列表 — 未来加真实项目 (serv 式) 不再需要单文件假设。

## 📌 状态

- ✅ 代码 (测试重写) + 验证; 全量回归见 commit
- skip 总数: 7 → 0 (全量 run 应不再有任何 skip)
