# P172.2 check_crap 默认 base

**日期**: 2026-11-14
**状态**: ✅ 完成

## 1. 问题

clean worktree 上：

```bash
python3 tools/check_crap.py
```

输出：

```text
0 changed files —— 门禁通过 (无事可判)
```

这不是检查，是 no-op。CI 通过 `SVQ_GATE_BASE` 才有真实比较，本地 gate 没有。

## 2. 修复

`tools/run_gates.sh`：

```text
SVQ_GATE_BASE set -> --base "$SVQ_GATE_BASE"
else HEAD~1 exists -> --base HEAD~1
else -> fallback no base (first commit only)
```

本地默认检查最后一次提交的 `src/**/*.py` 改动，避免 clean worktree 变成假绿。

## 3. 边界

- 无 `HEAD~1` 的初始仓库仍走旧路径；
- `crapper` 缺失仍是 exit 3，不是 pass；
- 这只是让 gate 真正执行，不改变复杂度阈值。

## 4. 验证

```bash
bash -n tools/run_gates.sh
SVQ_GATE_BASE=2c11488b bash tools/run_gates.sh
```

最后一次：全绿。
