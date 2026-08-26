# Iteration 20: Investigate `--dot` Flag Misnomer

**Metadata**:
- **Iteration #**: 20
- **Task Tree Level**: L2
- **Parent Task**: L2_plan_b_step_g
- **Created**: 2026-08-26 07:59 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: 🟡 IN PROGRESS

---

## 🎯 Current Goal

User request (07:59:17 GMT+8): "怎么是dot?" — asking why the file extension is `.dot`.

User noticed when I sent SVGs via Feishu, the underlying file path was `/tmp/reverify_*.dot` — they expected `.svg`.

## 📋 Investigation Findings

### T.20.3: File format check
```
$ file /tmp/reverify_picorv32_wb.dot
/tmp/reverify_picorv32_wb.dot: SVG Scalable Vector Graphics image
```
**The files ARE actually SVG!** The `.dot` extension is misleading.

### T.20.6: Code source
- `src/cli/commands/visualize.py:192`: `dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file"),`
- `src/cli/commands/visualize.py:250`: `Path(dot_output).write_text(svg)`  ← writes SVG, not DOT!
- `src/cli/commands/design.py:210`: `# [V100 SVG 2026-08-13] visualize dataflow --dot 现在输出 SVG 内容,` ← known V100 refactor

### Conclusion: `--dot` is a misnomer (bug)

The flag was originally for Graphviz DOT text format, but in **V100 (2026-08-13)** it was repurposed to write SVG content. The flag name `--dot` and help text `"Output DOT file"` were NOT updated.

## 🔬 Actual Result / Observation

This is **a flag naming bug**, not a visualization bug. The visualization is correct (SVG). Just the flag name is misleading.

## 💡 Other Valuable Info

- V100 refactor comment: "visualize dataflow --dot 现在输出 SVG 内容" — explicitly notes this change
- Should rename `--dot` → `--svg` or `--output` to be honest
- Should update help text from "Output DOT file" → "Output SVG file"
- Should deprecate the old `--dot` name (backward compat) or add warning

## 🔄 Next Action

- Explain to user with evidence (file + code)
- Suggest renaming the flag (or add a new `--svg` alias)
- Optionally fix the code (next iteration?)