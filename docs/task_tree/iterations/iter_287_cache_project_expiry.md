# Iteration 287: 缓存按工程过期（PLAN P3.2）

**Metadata**:
- **Iteration #**: 287
- **Task Tree Level**: L2（PLAN `P3.2`）
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "都做完。不要妥协，不要跳过。"）
- **Outcome**: ✅ 完成（三级淘汰：单工程版本数 / 年龄 / 全局总量；13 个新测试）

## 🎯 问题

缓存只有全局总量上限（`SVQ_CACHE_MAX_MB` + mtime LRU）：

- 一个改得勤的大工程会产出大量内容版本，把其它工程的缓存挤出总量上限
- 没有"条目放太久就失效"的机制（半年前的图一直占着）

## 🔧 方案

### 1. 工程身份（只看路径）

`ASTCache.compute_project_key(sources | filelist, include_dirs)`：

- 对 `sources`：hash 各文件**路径**（不含内容）
- 对 `filelist`：hash filelist 路径 + 其中列出的文件路径 + include 目录
- 同样的路径不同内容 = **同一个工程**（改代码不应换工程身份）

### 2. 文件名带工程段

```
<content_key>.p<project_key>.json.gz      新格式（content key 仍含 target 模式）
<content_key>.json.gz                     旧格式（无工程段，仍可读 → 不强制重建）
```

`_split_cache_name()` 用 `.p` 中缀无歧义地区分（content key 本身含 `-v2-t...`）。

### 3. 三级淘汰（`_enforce_size_limit`）

| 级别 | 规则 | 环境变量 | 默认 |
|---|---|---|---|
| ① 单工程版本数 | 每个工程最多保留 N 个最新版本 | `SVQ_CACHE_MAX_ENTRIES_PER_PROJECT` | 8（0=不限） |
| ② 条目年龄 | 超过 N 天的条目删除（含旧格式） | `SVQ_CACHE_MAX_AGE_DAYS` | 30（0=不限） |
| ③ 全局总量 | 原有 mtime LRU | `SVQ_CACHE_MAX_MB` | 1024 MB（0=不限） |

顺序有意义：先按工程裁剪（保住别的工程），再按年龄清理，最后才动全局 LRU。

### 4. 调用方

`UnifiedTracer` 新增 `_graph_project_key()`；`build_graph` 读写缓存时传
`project_key=`。`get_by_key` 的查找顺序：带工程段的新文件 → 无工程段新文件 →
旧格式（内容相同即同一张图，跨工程共享是安全的）。

## 🧪 测试（13 个）

`sim/tests/unit/test_cache_project_expiry.py`

| 组 | 覆盖 |
|---|---|
| 工程身份 | 只随路径变；不同路径不同；filelist 稳定/可区分；缺失返回 None |
| 单工程版本数 | 保留最新 N；其它工程不受影响；0=不限 |
| 年龄 | 超龄删除；0=不限；旧格式也参与 |
| 全局总量 | 不可压缩负载触发 LRU（普通重复字符 gzip 后不占空间，测试特意用随机内容） |
| 兼容性 | 旧格式可读；`invalidate(key)` 清除该 key 的所有工程变体 |

## ✅ 验证

| 项 | 结果 |
|---|---|
| 缓存专项 | 13 passed（新）+ 20 passed（旧 cache 测试） |
| 端到端 | 首次 0.06s → 二次 0.00s 命中；文件名 `...-v2-tall.p0abc3ce0.json.gz` |
| 全量门禁 | 见 INDEX 基线 |

## 💡 说明

- 内容 key 不变 → 命中语义不变，只是**文件名多了工程段**
- 旧缓存不失效（渐进升级），但会参与年龄/总量淘汰
- 工程 key 只 8 位 hex（文件名更短），碰撞概率对单机缓存足够低

## 🔗 相关

- 计划: [PLAN.md P3.2](../../../PLAN.md)
- 缓存压缩/上限前作: [iter_271](iter_271_instance_scope_default.md)
