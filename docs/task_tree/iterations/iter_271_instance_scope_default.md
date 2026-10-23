# Iteration 271: 实例级图切默认 + 缓存压缩/上限 + 测试迁移

**Metadata**:
- **Iteration #**: 271
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-23 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "1 切默认 / 2 限制最大体积，要压缩 / 3 要加上限"）
- **Outcome**: ✅ 默认已切；全量 2317 passed / 0 failed

## 🎯 三项决策落地

### 决策 1：实例级图切默认

- `UnifiedTracer.build_graph(instance_scope=None)` → 默认**开**；只有 `SVQ_INSTANCE_SCOPE=0|false|no`
  或 CLI `--no-instance-scope` 才回到模块定义级（应急逃生口，该路径将删除）
- `paths` / `dataflow analyze` 的开关改为 `--instance-scope/--no-instance-scope`（默认开）
- 其余命令通过 `UnifiedTracer` 默认值自动生效

### 决策 2+3：缓存压缩 + 体积上限

| 项 | 实现 |
|---|---|
| 压缩 | 缓存文件改 `.json.gz`（`gzip.open` 读写；兼容读旧 `.json`） |
| 体积实测 | verilog-axi 图：**20.6 MB → 0.41 MB**（≈50×），热启动仍 **0.2s** |
| 上限 | `SVQ_CACHE_MAX_MB`（默认 **1024 MB**；0/负数=不限） |
| 淘汰 | 写盘后按 **mtime LRU** 淘汰最旧条目直到低于上限；`list_cache`/`invalidate` 同时兼容两种后缀 |

## 🔧 测试迁移（26 → 0）

切默认后 26 个测试红，全部是"断言模块定义命名空间 id"的用例。逐类处理：

| 类别 | 处理 |
|---|---|
| 跨模块遍历（`test_cross_module_traversal` 7 个） | 断言改实例路径；D2 链条由 5 段变 3 段（不再有"进模块"跳） |
| L2 适配层（`test_load_tracer_adapter` 3 个） | 同上；`use_mig=False` 的语义改为"跨模块由图边提供，与 MIG 开关无关" |
| 类型级契约（`test_accuracy_a1_a2`） | **反转断言**：实例级图不应再有 `leaf.a`；实例内部应有真实驱动 |
| restore 生成展开（`test_generate_real_world`） | 显式用 `instance_scope=False` 保留"模块级 generate"这条路径的覆盖 |
| golden 快照（batch/filters/snapshot） | id 换实例路径 + 重新生成 golden |
| `connections` 模块类型查询 | 旧行为返回模块级四类边；现改为**显式失败** + 提示该类型的实例列表（不再抛 networkx 异常） |
| stats / module_synth / boundary / cache_error | id 与阈值更新 |

## 🕳️ 顺带修的两个真 bug

1. **`depth=1` 把自环当 load**：图里有 `x → x`（端口直通/位桥产生），`_find_loads` 不过滤
   → `depth=1` 结果含自己，`depth=2` 不含 → 深度单调性被破坏（被 traversal 测试抓到）。
   修：跳过 `succ == signal_id`。
2. **限定查询在实例级图下失效**：`--module` 的"不跨模块"以前只关 MIG 虚拟跳；实例级图里
   跨模块是普通图边，于是 `loads a --module inst_demo.u_adder` 会漏到外层。
   修：加命名空间前缀剪枝（`_in_scope` + 递归入口 guard）。

## 📊 量化

| 指标 | 值 |
|---|---|
| 全量门禁 | **2317 passed / 0 failed**（2316 → 2317，迁移中删/并了若干断言） |
| 缓存体积 | 20.6 MB → **0.41 MB** |
| 热启动 | 0.2s（不变） |
| 命令数 | 34（不变） |

## 💡 遗留

1. **模块定义级逃生路径仍存在**（`SVQ_INSTANCE_SCOPE=0`）：待确认无回归后删除，
   届时可清理 `_filter_by_target` / `MIG.port_to_internal` 等历史结构。
2. **generate 语义**：`_configure_instance_paths` 会下钻 generate，与决策 D2 的潜在冲突
   仍未实测收敛（本轮未新增失败用例，但也没有专门断言）。
3. **缓存清理策略**只有 LRU 上限，没有"按工程过期"；大工程多时依赖 1 GB 上限兜底。

## 🔗 相关

- 前序: [iter_270 缓存复活](iter_270_graph_cache_revive.md) / [iter_269 实例级开关](iter_269_instance_scope_switch.md)
