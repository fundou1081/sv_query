# Iteration 145: benchmark 测试环境修复 + topModules 编译能力

**Metadata**:
- **Iteration #**: 145
- **Task Tree Level**: L3 (测试资产维护; 编译能力增强)
- **Parent Task**: benchmark usage/integration 测试恢复
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (pr5 10 passed / picorv32 11 passed; 全量回归见 commit)

## 🎯 本次目标

方豆 "先处理 1" = 修复 benchmark usage 测试长期 skip (11 个), 曾误判为
HOME env。核查发现**真因三层**。

## 🔬 实际结果

### 真因链 (层层剥开)

1. **/tmp/pulp_axi_xbar_pr2.f 缺失** (测试 filelist 手工准备, 重启丢失 →
   FileNotFoundError → 长期 skip) — 环境, 但非 HOME 问题 (真实 HOME 也 fail)
2. **axi repo 版本演进**: target `axi_xbar_dp_ram` (pulp pr2 名) 现版本
   不存在 (只有 axi_xbar / axi_xbar_intf; 2026-06 baseline 时 instance 已 0)
3. **free-floating type-param 预 elab**: axi_demux 等 (axi_req_t=logic 默认
   type + 成员访问) 被 pyslang 预 elaborate 报 InvalidMemberAccess —
   **CVA6 cvxif 同款** (iter_140); axi_xbar_intf 默认参数 (Cfg='0) 空壳
   树浅 (2 实例 / 168 nodes)

### 修复

| 文件 | 内容 |
|---|---|
| `compiler.py` | **SVCompiler 新参数 top_modules** → pyslang options.topModules: 只 elaborate 指定 top 实例树, free-floating 忽略 (axi/CVA6 类库场景正解; iter_140 记录弃用, 现落地)。默认 None = 行为不变 |
| `unified_tracer.py` | top_modules 参数透传 SVCompiler |
| `run_benchmark.py` | UnifiedTracer(top_modules=[args.target]) — 编译即按目标树 |
| `class_graph_builder.py` | **GenericClassDefSymbol 不可迭代防崩** (参数化 class 方法赋值提取 TypeError → return) — 真 bug (axi/common_cells 泛型触发) |
| `test_benchmark_pr5.py` | filelist **自动生成** (axi + common_cells + deprecated/, 缺失重建); TARGET → axi_xbar_intf; 结构断言适配新 axi 实际 (旧阈值靠 pulp pr2 大参数 + free-floating 虚高 — 注释 + wrapper 深度基准 TODO) |
| `test_benchmark_picorv32.py` | 断言适配: IM 0 (picorv32 自包含, top_modules 后 free-floating 不虚高); L3 用 mem_busy fanin (clk 无子实例 fanout 0) |

### 结果

- pr5: 11 skip → **10 passed + 1 合理 skip** (L4 top_ports 默认参数空壳)
- picorv32 benchmark: **11 passed** (2 断言修正 — top_modules 后数据更准)
- 受影响回归: unit+integration 全绿 (serv HOME env 假失败除外)

## 💡 关键发现 / 决策

1. **topModules 是"库 filelist + 显式 top"场景的正解** (iter_140 弃用现落地):
   free-floating type-param 预 elab (CVA6 cvxif / axi_demux) 在显式 top 下
   消失 — 编译语义 = 目标树, 与 build_graph(target) 一致, 数据更准
   (picorv32 IM 0 真实反映无子实例, 旧 2 是 free-floating 虚高)。
2. **长期 skip 的测试要挖真因**: benchmark 误判 HOME env 几个月; 真因 =
   环境文件 + repo 版本演进 + 编译器边界三层叠加。教训: skip 时记真因。
3. 遗留: pr5 wrapper 深度基准 (axi_xbar_intf 默认参数空壳 → 结构断言
   弱化) — 需要时加 pr5_wrap (真实端口参数) 恢复深结构断言 (TODO)。

## 📌 状态

- ✅ topModules 编译能力 (SVCompiler/UnifiedTracer/run_benchmark)
- ✅ GenericClassDefSymbol 防崩 (真 bug)
- ✅ pr5 + picorv32 benchmark 恢复 (断言按真实数据修正)
- 全量回归见 commit
