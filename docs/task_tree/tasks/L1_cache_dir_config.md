# L1: 缓存目录可配置 + 不可写降级 (A 路线第二项)

> **Created**: 2026-09-08 GMT+8
> **Status**: ✅ CLOSED (iter_172)
> **方豆**: "缓存目录先更改, 更通用, 避免未来失败"

## 背景

项目全面回顾定位的环境可复现性缺陷:
- `ast_cache.CACHE_DIR = Path.home() / ".svq" / "cache"` **硬编码**, 无任何覆盖手段
- `ASTCache.__init__` 的 `mkdir(parents=True, exist_ok=True)` **无保护** →
  只读 HOME (容器 / CI / 沙箱) 直接抛 `PermissionError`
- `put_by_key` 写盘同样无保护 → 异常冒泡到 CLI → **exit 1**
- 实测后果: 本沙箱内 **cli 19 + integration 10 = 29 个测试假失败**
  (报 `Error: [Errno 1] Operation not permitted: '<home>/.svq/cache/*.json'`)

## 目标

1. 缓存目录可配置 (env + 惯例), 覆盖 CI/容器/只读 HOME
2. **任何不可写都不得让分析失败** (缓存 = 优化, 不是必需品)
3. 失败可见 (warning + 修复提示), 不静默

## 结果 (iter_172)

- `resolve_cache_dir()`: 显式参数 > `SVQ_CACHE_DIR` > `XDG_CACHE_HOME/svq` >
  `~/.svq/cache` (向后兼容); 保留 `CACHE_DIR` 常量供外部 import
- `ASTCache`: 构造 mkdir 失败 → `enabled=False` (内存缓存降级) + warning;
  `put_by_key` 写失败 → 同样降级 (只 warning 一次, 不刷屏);
  `get_by_key`/`invalidate`/`list_cache` 全部健壮化; `cache_stats` 增
  `disk_cache_enabled`
- `list_cache` 的裸 `except Exception: continue` (AGENTS §2.5 违规) 收窄为
  `(OSError, json.JSONDecodeError)` + warning
- 测试 11 新增 (`sim/tests/unit/test_cache_dir_config.py`): 解析优先级 5 /
  降级行为 4 / 可写不回归 1 / **子进程 CLI 端到端 1** (不可写目录 → rc=0)
- **端到端验证**: 之前 29 个假失败套件 **cli+integration 739 passed / 0 failed**

## 文档

- `docs/USER_GUIDE.md`: 环境变量表 + 缓存目录解析顺序 + 只读 HOME 说明
- `docs/INDEX.md` 基线: CLI/integration 行改为实测通过数 (去掉环境失败注记)

详见 [iter_172](../iterations/iter_172_cache_dir_config.md)
