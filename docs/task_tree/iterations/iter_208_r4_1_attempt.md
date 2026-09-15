# Iteration 208: R4-1 尝试与回退 — 两个新线索

**Metadata**:
- **Iteration #**: 208
- **Task Tree Level**: L2 (CLI 可用性)
- **Parent Task**: iter_207 后续 (方豆 "可以，继续做吧")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ❌ 修复未生效 (已回退) + 2 个关键线索

## 🎯 本次目标

修 R4-1: `-f <filelist>` 误用时的提示退化。

## 🔬 实际结果

### 部分改善 (由 iter_207 的 R4-3 顺带带来)

原始 R4-1 场景 (`stats -f <filelist 带 +incdir+>`) **已被 R4-3 修复**: 现在 rc=0
(过去 rc=1 + UndeclaredIdentifier 级联 + 被禁 flag 提示)。

### 剩余形态: 非 `.f` 扩展名的 filelist

`stats -f list_noext.txt` (内容是 `+incdir+inc` + `top_inc.sv`) 仍给误导信息:

```
Error: <path>
Hint: First check your filelist is complete (missing modules? missing includes?).
      Use --no-strict to analyze the partial AST as a last resort.
```

### 修复尝试 (iter_189 守卫扩展) → ❌ 未生效, 已回退

方案: 在 `SVCompiler._reject_non_design_unit` 里按**特征行**识别 filelist
(`+incdir+` / `+define+` / `-f ` / 裸路径)。

踩到的两个问题 (留下的线索, 下次直接用):

1. **判据不能只看首行**: 我们的预处理器会在文件顶部注入 `` `timescale 1ns/1ps ``
   (实测 `preprocess_all(': +incdir+inc\ntop_inc.sv\n')` → 输出第 1 行是 timescale)
   → filelist 的 `+incdir+` 退到第 2 行。必须扫描**前若干有效行**。
2. **裸路径判据要收紧**: 首版用 `line.endswith('.v')` → 把
   `endmodule // top.v` 这类**行尾注释**误判成 filelist (实测 cordic `.v` 语料误报)。
   必须加"无空白 + 无分号"约束。
3. **守卫信息被上层格式吞掉**: 即使守卫抛了带"内容看起来是 **filelist**"的
   `CompilationError`, 最终 stderr 只显示 `Error: <path>` + 通用 Hint →
   用户**看不到**关键信息。要修 R4-1, **必须先看 `handle_compilation_error` 的
   格式化逻辑** (它似乎只打印首行/抹掉正文), 否则守卫写得再好也白费。

→ 按纪律 (不提交未验证的行为改动 + 不留红测试) **回退代码**, 记录线索。

## 💡 关键发现 / 关键技术 / 决策

1. **"错误信息链路"要端到端验证**: 我验证了守卫"抛了什么", 却没验证"用户看到什么"。
   中间层 (`handle_compilation_error`) 会把消息改写 → 必须**从 CLI 输出反推**,
   不能只看异常内容。
2. **预处理器会改写文件头部**: 注入 `` `timescale `` 让"首行判据"类启发式失效 ——
   任何基于行号的输入识别都要容忍前缀注入。
3. **启发式的误报代价高**: `endswith('.v')` 就把正常 `.v` 语料判成 filelist。
   收紧到"裸路径"(无空白/无分号) 后才安全 —— 这条判据下次可直接复用。

## 📢 下一步 (R4-1 的正确做法)

1. 先读并修 `cli/_common.py::handle_compilation_error` 的格式化 (让错误正文可见);
2. 再把守卫判据 (特征行扫描 + 裸路径) 加回去 —— 两个坑的解已在上面;
3. 或者更简单: 在 `_build_tracer` 的 `--file` 分支做"filelist 内容检测"
   (closer to the CLI, 不受 compiler 层格式影响)。

## 🔎 追加线索 (iter_208 末): `stats` 有**两个**错误分支

```python
# src/cli/commands/stats.py:176
except CompilationError as e:
    handle_compilation_error(e, strict=strict)      # 打印 Error: <header> + 前 10 行
except Exception as e:                              # 179
    data = {"ok": False, "command": "stats", "error": str(e), "errors": [str(e)]}
    ...
    print(f"Error: {e}", file=sys.stderr)           # 184 ← 只打印异常字符串
```

实测误用场景里 stderr 只有 `Error: <filelist 路径>` + 通用 Hint —— **匹配第二个分支**
(`print(f"Error: {e}")`), 而不是 `handle_compilation_error` 的格式 (后者会带前 10 行细节)。

→ 说明守卫抛出的 `CompilationError` 在场某处**被包装/替换成了普通异常**(或走了另一条
路径), 因此消息正文丢失。**下一步 (5 分钟可验证)**: 重新加上守卫, 在 `stats.py:179`
的通用分支打印 `type(e)`/`repr(e)`, 看异常到底是谁 —— 定位后再决定消息怎么传。

`handle_compilation_error` 本身的行为已确认无问题: 单行消息会**完整**打印
(`header = lines[0]`), 多行消息打前 10 行 —— 所以"格式化吞消息"的判断**需要修正**:
真正的问题在**异常类型/包装**, 不在格式化函数。

## 📎 关联

- 相关: `iter_189_addsyntaxtree_sigtrap_guard.md` (守卫) / `iter_204` (R4-1 发现) /
  `iter_207_r4_3_landed.md` (R4-3 顺带修掉了原场景)
- fixture: `sim/tests/fixtures/hostile_input/incdir_case/list_noext.txt`
