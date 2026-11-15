# P175 agent skill rewrite from short/long task corpora

**日期**: 2026-11-15
**状态**: ✅ 完成

## 1. 语料盘点

独立 worker 整理并复验了本地短/长任务：

- long_range 12、P115 10、P111 5、blind 20、OpenTitan UART/I2C/intake/P127 13、SPI 9、interactive 5；
- 外部短任务合计 **64**；
- exp 命令使用次数 = **0**；全部任务只用 core。

复验通过：pico neighbors/path/no-path、AXI neighbors、UART intr-test、I2C claims/SDA path、deep_chain。

发现的语义漂移：

- ternary 已是 control edge，不在 `paths` 数据路径里；旧 ground truth 的 ternary path 过期；
- `drivers --depth 1` 当前会带 CLOCK/RESET/constant 源；
- UART intr_test_qe 的 empty-side drivers 从 2 变 1；
- reverse coverpoint lookup 对实例级 class member 仍可能失败。

## 2. skill 重写

`skills/sv-query/` 已改为 snapshot-first、query+verify、core-only：

- `SKILL.md`：D→S→Q→E→V 协议、installed CLI、`--depth 1`、失败语义、7 个坑；
- `references/commands.md`：决策树 + 命令模板 + flag 区分；
- `references/fields.md`：字段/envelope/失败矩阵；
- `references/snapshot.md`：build/prune/save + 能力矩阵；
- `references/pitfalls.md`：实测失败模式；
- `references/semantics.md`：class/constraint/covergroup 只查询、不证明；
- `references/examples.md`：pico/AXI/UART/I2C/deep_chain 示例。

删除旧 `evidence.md` / `workflow.md` / `locations.md` / `pyslang-compat.md` /
`troubleshooting.md` / `cases/` / `examples/` / `scripts/sv_analyze.py`。

## 3. 修正的产品说明

- `requirements.txt`：pyslang v11-only，删除 compat shim 文本；
- `test_skill_surface.py`：不再测试已删除的 helper；增加 skill 协议、无旧兼容引用、
  Markdown 链接存在性检查。

## 4. 验证

```text
canonical: 2740 passed / 0 failed / 123 deferred
skill surface: 6 passed
full gate: green
```
