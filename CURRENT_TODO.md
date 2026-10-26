# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **位置固定**: 根目录 `CURRENT_TODO.md`, 路径永不变更。
> **更新时机**: 每次开始任务 / 完成 sub-task / 被打断切换任务时, 立即更新。
> **最后更新**: 2026-10-27 GMT+8 (iter_301: P5~P12 位精确性系列收尾 + 能力评审 + 文档收敛)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **已完成**: P0~P12 全部完成（含 P5~P12 位精确性系列，iter_289~300）
- **当前 item**: `P13.1 缓存 key 纳入 SVQ_BIT_BRIDGE 模式（P0 静默错误） <待做>`
- **P13 评审 backlog**: 见 [trace_capability_review_2026-10-27](docs/architecture/trace_capability_review_2026-10-27.md)
- **建议顺序**: P13.1（静默错误）→ P13.2/13.3（可解释性/契约）→ P13.4/13.5（位精确性）
  → P13.6（多驱动/静态 memory）
- 开工前先更新 PLAN.md + 跑 `python3 tools/check_plan.py`

---

## 📦 仓库状态 (2026-10-27)

- **分支 = `main`**（推送 `backup/main`；本轮文档提交后以 `git log -1` 为准）
- **全量基线**: **2489 passed / 0 failed**（`sim/tests/`, `-m "not opensource"`；
  7 skipped / 152 deselected）；35 命令（core 25 / view 10）
- **图缓存**: `CACHE_VERSION = 1.4`；图基线 6 fixture（`sim/tests/golden/graph_baseline/`）
- **位精确性**: 显式位/切片/寄存器/总线桥/表达式（位运算、加减乘、常量移位、Slice）/
  直接拷贝/纯拼接/常量位/`integer` 宽度/signedness/packed struct 聚合+成员+成员位桥
  全部有模型；比较/逻辑/变量移位/动态选择/函数调用为本质粗粒度（见 KNOWN_LIMITATIONS §3.6）
- **已登记限制**: `SVQ_BIT_BRIDGE` 默认 `one`（`full` 可选）；深层成员（`o.inner.a`）
  与非 packed struct 不参与位桥

---

## 📍 最近完成（位精确性系列）

| 迭代 | 内容 | 关键结果 |
|---|---|---|
| iter_289~292 | 位精度审计 + F1/F2/F3/F5 | 切片/负载按位精确，写污染/断链修复 |
| iter_293 | F4 总线位桥（`one` 默认/`full` 可选） | 缺位侧合成，纯总线可贯通 |
| iter_294 | 表达式按运算符逐位映射 | 位运算/加减乘/常量移位/Slice |
| iter_295 | 直接拷贝 + 纯拼接 | `assign y=a` 位精确；`{a,b}` 分段 |
| iter_296 | 常量位分解 | `4'hA` → `1'b1`；拼接字面量段 |
| iter_297 | signedness 建模 | `TraceNode.is_signed`；符号扩展 |
| iter_298 | 整数类型位宽 | `integer/int/byte/...` 真实宽度 |
| iter_299 | packed struct/union（聚合+成员布局） | 宽度/signedness/位段 |
| iter_300 | packed 成员位级查询桥 | `p.a[1]` ↔ `p[5]` |

---

## 🔥 下一项（P13.1，P0 静默错误）

**现象（实测）**: 默认 `one` 建图后切换 `SVQ_BIT_BRIDGE=full` 再用缓存 → 仍是 5 节点（应 37）。
**根因**: `UnifiedTracer._graph_cache_key` 未包含 bit-bridge 模式。
**修法**: key 加 `-bb{one|full}`；补回归测试（两种模式各建一次，节点数不同且互不串）。
**验收**: 切换模式后必须重建；同模式缓存仍命中；全量 0 failed。

---

## 🧰 固定设施与门禁

```bash
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly   # 全量
python3 tools/check_docs.py            # 死链/归档/未登记
python3 tools/check_plan.py            # 计划树
python3 tools/check_cli_layers.py      # 分层
python3 tools/gen_cli_surface.py --check
python3 tools/check_except_pass.py
```

| 设施 | 位置 |
|---|---|
| 计划树 | [PLAN.md](PLAN.md)（唯一） |
| 迭代记录 | `docs/task_tree/iterations/`（只增不改） |
| 测试地图 | [TESTING.md](TESTING.md) / [docs/TEST_MAP.md](docs/TEST_MAP.md) |
| 已知限制 | [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) |
| 能力评审 | [docs/architecture/trace_capability_review_2026-10-27.md](docs/architecture/trace_capability_review_2026-10-27.md) |
