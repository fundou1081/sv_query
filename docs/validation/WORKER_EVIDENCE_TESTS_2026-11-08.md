# Worker 辅助 evidence 测试（P107）

**日期**: 2026-11-08
**方式**: OpenCode worker `svq-evidence-dev`，隔离 worktree，1 turn
**范围**: `tools/agent` only

---

## 1. Worker 交付

- `evidence.js`：依赖注入的纯 evidence 逻辑；
- `index.js`：注入真实 fs/env；
- `test/evidence.test.js`：13 个测试；
- 总 Node tests：**36**。

覆盖：

- ±2 行 source_context；
- 文件首尾裁剪；
- missing node；
- missing/unreadable source；
- 160 字符截断；
- 80 节点上限；
- 去重；
- sourceRoot；
- evidence opt-in no-op；
- evidence_error。

## 2. 验证

```text
node --test tools/agent/svq-query-tool/test/
36 tests, 36 pass
```

worker 还做了 8 个 differential parity 场景，结果与重构前一致。

## 3. 集成

主 agent：

- 审查 diff；
- 只复制 evidence 相关文件，**没有复制 worker harness 写入的 AGENTS.md**；
- 重装工具；
- 3-cell smoke 6/6；
- deep evidence 单测复核 XOR 正确。

## 4. 边界

evidence.js 可纯测；index.js 仍需要 DSH peer dependency，不能直接 import。
