# Iteration 270: 图缓存复活（25s → 0.2s）+ scope 隔离 + 头文件纳入 hash

**Metadata**:
- **Iteration #**: 270
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-23 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "可以" —— 同意先测缓存命中率）
- **Outcome**: ✅ 缓存从"死代码"变可用；热启动 **0.2s**（冷启动 24.9s）

## 🎯 目标

实例级图比模块级慢 **+58%**（16.3s → 25.8s，verilog-axi 实测）。
切换默认前先验证选项 B：**用缓存把第二次构建拉回秒级**。

## 🕳️ 查出来的三个 bug（缓存此前完全没用）

### ① 图缓存**从未命中过**（静默 miss）

```python
# put_by_key 把 payload 包在 "data" 里
cache_data = {"version": ..., "sources_hash": ..., "cached_at": ..., "data": data}
# 而读取方直接查顶层
if cached and "graph_data" in cached:     # ← 永远是 False
```

结果：缓存文件写了、读的时候永远 miss，**没有任何 warning**。
（缓存 API 的测试锁定的是 `get_by_key(...)["data"]`，所以测试一直是绿的。）

### ② 缓存 key 不含图模式 → scope 串味

旧 key = sources 内容 hash。模块级与实例级共用同一 key：
先建模块级，随后请求实例级 → 直接返回**模块级旧图**（静默错误答案）。

### ③ filelist 模式**根本不进缓存**

`use_cache and self._sources` —— 真实工程都是 filelist 模式，`_sources` 为空 → 永远跳过。
所以"缓存"只对单文件模式理论有效，而单文件模式又因 bug ① 从不命中。

## 🔧 修复

| # | 修法 |
|---|---|
| ① | 读取时取 `cached["data"]["graph_data"]`（cache API 契约不动，测试仍锁 `["data"]`） |
| ② | key = `内容hash + "-s{0/1}-t{target\|all}"` —— scope/target 不同则 key 不同 |
| ③ | 新增 `ASTCache.compute_filelist_hash()`：hash filelist + 它引用的所有文件**内容**，并纳入 include 目录下的 HDL 头文件 |

> 头文件纳入 hash 是必须的：`\`include` 的文件通常不在 filelist 里，只 hash filelist
> 会造成"改了头文件仍命中旧图"的静默错误。

## 📊 实测（verilog-axi，13,188 节点 / 26,230 边）

| 场景 | 耗时 |
|---|---|
| 冷启动（建图 + 写缓存） | **24.9s** |
| 热启动（磁盘缓存命中） | **0.2s**（≈125×） |
| 缓存文件大小 | 20.6 MB |

## ✅ 验收（新增 `sim/tests/unit/test_graph_cache_scope.py`，4 用例）

| 用例 | 锁定 |
|---|---|
| `test_scope_and_target_change_key` | scope/target 影响 key |
| `test_filelist_mode_has_key` | filelist 模式有 key（以前是 None） |
| `test_second_build_uses_cache` | 第二次构建 **不重跑** `GraphBuilder.build`（monkeypatch 计数=0） |
| `test_scope_isolation_no_cross_hit` | 先模块级再实例级 → 不会拿到模块级图 |

## 💡 决策与遗留

1. **缓存默认仍关闭**（`build_graph(use_cache=False)`）：`trace` 系列命令已有
   `--no-cache`（默认走缓存），`paths`/`dataflow` 还没有；是否全局默认开，等方豆定。
2. **20.6 MB/工程的缓存体积**需要留意（可后续 gzip；当前 JSON 明文便于调试）。
3. **切默认的三件事仍未做**：31 处测试引用模块定义 id、generate 语义（D2）、
   缓存目录清理策略。

## 🔗 相关

- 前序: [iter_269 实例级图开关](iter_269_instance_scope_switch.md)
- POC: [2026-10-23_native_connectivity.md](../../poc/2026-10-23_native_connectivity.md)
