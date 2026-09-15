# Iteration 216: 彻底移除 strict — 批次 2 (删除全部 34 个 CLI `--strict/--no-strict` 选项)

**Metadata**:
- **Iteration #**: 216
- **Task Tree Level**: L1 (纪律强制 · 执行)
- **Parent Task**: 方豆 "推进批次2, 全部移除"
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ CLI 选项清零 (含 3 次自伤纠正)

## 🎯 本次目标

按方豆指示推进批次 2: **删除全部 CLI `--strict/--no-strict` 选项** (34 处 / 18 文件),
让工具恒定严格。

## 🔬 实际结果

### 执行 (机械删除 + 三次自伤纠正)

| 阶段 | 动作 | 结果 |
|---|---|---|
| 1 | 删 `strict: bool = typer.Option(..., "--strict/--no-strict", ...)` 行 + `strict=strict` → `strict=True` | 删 30 处 / 传参固定 114 处 |
| 2 | **自伤**: `STRICT_OPTION` 常量被删但 20+ 文件仍 import → `ImportError`, CLI 全崩 (CLI 套件 **342 failed / 13 errors**) | 修正: 删 `strict: bool = STRICT_OPTION` 参数行 + 清 import 列表 |
| 3 | `_common.py` / `_viz_common.py` 的常量定义 + `protocol.py` / `snapshot.py` 的多行选项 | 全清 |
| 4 | **剩余 19 个失败** = 测试**显式传 `--strict`** (正向用法) → 选项没了变 rc=2 | 清测试里的 `--strict` (3 文件) → 该两组 **19 passed** |

### 验证

- `grep -rn '"--strict/--no-strict"' src` = **0**; 采样 `stats` / `design show` /
  `trace fanin` / `coverage generate` 的 `--help` 均**不再出现 strict**;
- 冒烟: `stats` rc=0 / `trace fanin` rc=0; `visualize graph` 失败是**既有无关问题**
  (ELK `Referenced shape does not exist`, TESTING.md 已登记);
- CLI 套件: **35 failed → 19 passed 修复后** 只剩可视化 16 个 (按指示暂缓);
- **全量 canonical: 34 failed / 3282 passed** (按方豆"失败先保留, 之后一起修"的原则记录):
  16 个可视化 (暂缓) + 一批**fixture 在严格模式下暴露真错**的用例
  (例: `test_snapshot_compare_flags.py` 4 个 → "Snapshot not found", 因 snapshot 过去
  默认非严格 (`Option(False, ...)`) 掩盖了 fixture 错误)。

## 💡 关键发现 / 关键技术 / 决策

1. **删"选项常量"是连带风险**: 删 `STRICT_OPTION` 定义时, 20+ 文件的 `import`
   与 `strict: bool = STRICT_OPTION` 参数行必须**同批**处理, 否则 `ImportError` 让整个
   CLI 崩 (本次 342 failed 就是这么来的)。**机械改写必须跟"引用清理"配对**。
2. **`ast.parse` 不足以验证**: 语法正确 ≠ 名字存在 (`ImportError` / `NameError` 都要靠
   grep + 冒烟跑命令才能发现)。本次靠 `stats/trace` 冒烟立刻定位。
3. **测试里的 `--strict` 也是"用法"**: 正向使用同样依赖该选项存在 → 删选项必须同步清
   (本次 19 个失败全因此), 否则"纪律清了但测试红"。
4. **无关失败要区分**: `visualize graph` 的 ELK 报错与本次改动无关 (既有问题),
   记录时明确标出, 避免误归因。

## 📢 后续批次 (iter_214 方案)

| 批次 | 内容 | 状态 |
|---|---|---|
| 1 | `design.py` 7 处 flag 追加 | ✅ iter_215 |
| 2 | 34 个 CLI 选项定义 | ✅ 本次 |
| 3 | API 形参 (`_build_tracer` / `build_resolver` / `generate_covergroup` 等) | 待做 (当前以 `strict=True` 传参维持正确行为) |
| 4 | 生产/脚本 `strict=False` 调用点 (11 处 src + tools) | 待做 |
| 5 | 测试 API 级降级 (29 处) | 待做 |
| 6 | 可视化 16 个失败 | 按指示暂缓 |

## 📎 关联

- 方案: `iter_214_strict_default_scan.md`; 批次 1: `iter_215_remove_strict_batch1_design.md`
- 备份: `/tmp/src_backup_batch2` (自伤纠正时使用)
