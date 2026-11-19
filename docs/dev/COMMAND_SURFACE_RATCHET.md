# Command-surface ratchet — P185.4

> **状态**: 启用；`tools/check_command_surface.py --check` 已接入 `run_gates.sh`。
> **Baseline**: `tools/command_surface_baseline.json`
> **日期**: 2026-11-19

## 1. 锁定的表面

```text
45 canonical listed
39 default visible
2 aliases (trace fanin -> drivers, trace fanout -> loads)
32 standard / 13 direct
39 core + 6 exp
```

baseline 记录：

- canonical 命令名；
- default-visible 命令名；
- aliases；
- layer/envelope 计数；
- core groups。

## 2. 规则

- 新增/删除命令、改别名、改变默认可见性、逐命令 layer/group/envelope 重指派、
  隐藏命令变化 → `--check` FAIL；
- 命令面变更必须**同一提交**更新 baseline 并记录原因；
- baseline 不是“防止所有演化”，而是让演化必须显式。

## 3. 使用

```bash
python3 tools/check_command_surface.py --check
# command-surface: PASS (45 canonical, 39 visible, 2 aliases, 32 standard, 13 direct)

python3 tools/check_command_surface.py --write-baseline
# 仅在有意变更命令面时使用
```

## 4. 不覆盖

- 单命令 option/字段 schema（由 CLI_SURFACE / JSON schema 负责）；
- `exp` 内部实验稳定性；
- 命令实现本身是否可用（由测试/真实 smoke 负责）。
