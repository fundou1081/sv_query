# Iteration 172: 缓存目录可配置 + 不可写降级 (A 路线第二项)

**Metadata**:
- **Iteration #**: 172
- **Task Tree Level**: L1
- **Parent Task**: L1_cache_dir_config (tasks/L1_cache_dir_config.md)
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (29 个环境假失败 → 0; 11 新测试)

## 🎯 本次目标

方豆 "缓存目录先更改, 更通用, 避免未来失败" — 修全面回顾里的环境可复现性
缺陷 (缓存硬编码 + 失败致命)。

## 📊 当前状态 / 预期结果

- `CACHE_DIR = Path.home()/".svq"/"cache"` 硬编码; mkdir/写盘无保护;
  只读 HOME 下 29 个测试假失败 (cli 19 + integration 10)。
- 预期: 可配置 + 不致命 + 失败可见。

## 🔬 实际结果

**诊断 (3 根因链)**:
1. 路径: 模块级常量硬编码 `Path.home()/".svq"/"cache"`, 无 env/惯例覆盖
2. 构造: `ASTCache.__init__` 的 `mkdir(parents=True, exist_ok=True)` 裸调用
   → `PermissionError` 直接冒泡
3. 写入: `put_by_key` 的 `open(...,"w")` 裸调用 → 异常冒泡到 CLI → **exit 1**
   (证据: `Error: [Errno 1] Operation not permitted: '<home>/.svq/cache/*.json'`)

**方案对比 (≥2)**:
- A. 只加 env 覆盖 — 最小改动, 但用户不设 env 时仍旧致命 → 不彻底
- B. **env + XDG 惯例 + 不可写降级** (选定) — 覆盖整类问题 (CI/容器/沙箱/
  只读 HOME); 缓存是优化, 失败降级 + warning 是正确语义
- C. 再加 CLI `--cache-dir` — 额外接口面, env 已覆盖 CI, 收益低 → 不做

**实现**:
- `resolve_cache_dir()`: 显式 > `SVQ_CACHE_DIR` > `$XDG_CACHE_HOME/svq` >
  `~/.svq/cache`; 保留 `CACHE_DIR` 常量 (外部 import 兼容)
- `ASTCache`: 构造/写盘 `OSError` → `enabled=False` 内存降级 + warning
  (含 `SVQ_CACHE_DIR` 修复提示); 降级后不重复 warning (不刷屏)
- `get_by_key` 降级后跳过磁盘探测; `invalidate` 逐文件 guard;
  `list_cache` 裸 `except Exception: continue` (AGENTS §2.5 违规) →
  `(OSError, json.JSONDecodeError)` + warning; `cache_stats` + `disk_cache_enabled`

**测试 11** (`sim/tests/unit/test_cache_dir_config.py`):
解析优先级 (默认/env/XDG/env>XDG/显式>env) 5 / 降级 (构造不抛+提示、put-get
走内存、降级后不重复 warning、读与管理操作不抛、可写不回归) 5 /
**子进程 CLI 端到端** (SVQ_CACHE_DIR 指向不可创建路径 → rc=0) 1。

**端到端验证 (关键)**: 修复前 cli 19 + integration 10 假失败;
修复后 **`pytest sim/tests/cli sim/tests/integration -m "not opensource"`
= 739 passed / 0 failed** (沙箱内一次跑通)。

## 💡 关键发现 / 决策

- **"优化性设施" 不该致命**: 缓存/快照/日志这类旁路设施, 失败必须降级 +
  可见 warning, 而不是把整条主流程拉挂。判断标准: 去掉它结果是否仍正确?
  是 → 就不能 fatal。这条已推广到 `invalidate/list_cache` 等管理操作。
- **惯例优先于私有约定**: 解析顺序纳入 `XDG_CACHE_HOME` (Unix/CI 通行),
  保留 `~/.svq/cache` 只为向后兼容 — 新项目默认应直接走 XDG。
- **测试自身也会"假失败"**: 我第一版测试因 cleanup 顺序 (只读目录先被删)
  导致模拟失效 → 测试全红; 教训: 模拟"不可写"的测试必须保证权限恢复在
  清理之前 (LIFO 顺序)。
