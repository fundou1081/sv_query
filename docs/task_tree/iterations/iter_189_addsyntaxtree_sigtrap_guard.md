# Iteration 189: pyslang `addSyntaxTree` 原生 SIGTRAP — 根因定位 + 守卫

**Metadata**:
- **Iteration #**: 189
- **Task Tree Level**: L1 (外部边界正确性 / 崩溃防护)
- **Parent Task**: iter_188 发现的 `visualize module` 崩溃 (方豆 "继续")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 根因定位 (纯 pyslang 最小复现) + 我们层守卫 + 回归锁

## 🎯 本次目标

iter_188 发现 `sv_query visualize module` 丢 SIGTRAP 崩溃 (当时只确认"非本次改动
引入", 记为待立项)。本次把它查到底并修掉: 先诊断、再方案、后动手 (AGENTS 纪律 2)。

## 📊 当前状态 / 预期结果

现象: `sv_query visualize module -f <filelist>` / `--target <任意>` → rc=-5
(SIGTRAP), **无任何输出**, 无 artifact。原以为是"整个子命令废了"。

## 🔬 实际结果

### 1. 二分: 不是子命令废了, 是**输入类型**

| 输入 | `visualize module` |
|---|---|
| `-f <正常 .sv>` (含 module) | rc=0 ✅ |
| `-f <filelist.f>` | **rc=-5** ❌ |
| `--filelist <同一个 filelist.f>` | rc=0 ✅ |
| `-f <内容为"一行路径"的文件, 任意扩展名>` | **rc=-5** ❌ |
| `-f <内容为合法 SV 的文件, 扩展名 .f>` | rc=0 ✅ |
| `visualize graph/pipeline -f <filelist>` | rc=0 (走 `_build_tracer`, 输入处理不同) |

→ 与扩展名无关, **与"文件内容解析成什么"有关**。

### 2. 最小复现 (纯 pyslang, 5 行, 不需要本项目代码)

```python
import pyslang
src = "/path/to/mod.sv\n"                     # ← filelist 的典型内容
tree = pyslang.syntax.SyntaxTree.fromText(src, name="x.sv")
assert str(tree.root.kind) == "SyntaxKind.DivideExpression"   # 被解析成"除法表达式"
comp = pyslang.ast.Compilation()
comp.addSyntaxTree(tree)                      # ← SIGTRAP (exit 133), 无输出
```

- `fromText` 正常返回; 崩的是 **`Compilation.addSyntaxTree()`**;
- 逐步二分 (`fromText` → `addSyntaxTree` → `getParseDiagnostics` →
  `getSemanticDiagnostics` → `getRoot`): **只有 `addSyntaxTree` 崩**;
- `faulthandler` 无栈 → SIGTRAP 不在其默认捕获集, 属 native `abort()/trap`;
- 触发条件: slang 对"不是设计单元"的文本走 **script 模式**解析, 根节点成了表达式
  (`DivideExpression` / `AddExpression` …) → 把它交给 `Compilation` 就 trap。

### 3. 合法输入的根节点类型 (实测 120 个 fixture + 边界用例)

| 输入 | 根节点 | 结果 |
|---|---|---|
| 多 module / 空文件 / 仅注释 / 仅 `define` / `import`+module | `CompilationUnit` | ✅ 正常 |
| 单 module 文件 (如 `pr5_wrap.sv`) | `ModuleDeclaration` | ✅ 正常 |
| 仅 class | `ClassDeclaration` | ✅ 正常 |
| **filelist 内容 / 裸表达式** | `DivideExpression` / `AddExpression` | ❌ **trap** |

→ 守卫的判据取**最小范围**: 只拒绝"表达式根", 不误伤任何设计单元 (含空文件/
仅注释/仅 `define` 这类"没有设计单元"的合法输入)。

### 4. 修复 (我们层, 边界守卫)

`src/trace/core/compiler.py`:

```python
tree = pyslang.SyntaxTree.fromText(...)
_reject_non_design_unit(tree, fname)   # [iter_189] 表达式根 → CompilationError
self._comp.addSyntaxTree(tree)
```

错误信息带**可行动的提示**:

```
x.sv: 解析结果的根节点是 SyntaxKind.DivideExpression (SystemVerilog 表达式),
不是设计单元 — pyslang 在此情况会原生 SIGTRAP (addSyntaxTree)。
常见原因: 把 filelist/文本文件当源码传入 (请用 --filelist 传 .f)。
```

端到端前后对比:

| 命令 | 修复前 | 修复后 |
|---|---|---|
| `visualize module -f <filelist>` | **rc=-5, 无输出** | **rc=1 + 明确错误信息** |
| `visualize module -f <正常 .sv>` | rc=0 | rc=0 (无变化) |
| `visualize module --filelist <filelist>` | rc=0 | rc=0 (无变化) |

### 5. 回归锁 (红/绿双向验证)

新增 `sim/tests/unit/test_compiler_non_design_unit_guard.py`:
- 3 个表达式根输入 → 必须抛 `CompilationError` 且信息含 `Expression` / `设计单元`;
- 7 个合法输入 (空/注释/define/单 module/双 module/class/package+module) → 不得误伤;
- 单文件 + `top_modules` 正常编译 → tops == 1。

**红/绿验证**: 临时去掉守卫那行 → **pytest 进程本身 exit=133 (Trace/BPT trap),
零输出**; 恢复后 11 passed。即: 守卫失效时测试以最原始的方式报警 (进程崩),
不需要任何断言技巧。

## 💡 关键发现 / 关键技术 / 决策

1. **SIGTRAP 无输出的调试方法**: ① 用输入矩阵二分 (扩展名 vs 内容 → 锁定"内容");
   ② 逐步二分到具体 API (`addSyntaxTree`); ③ **纯 pyslang 最小复现**把"CLI 之谜"
   降级为"上游 binding 行为"; ④ `git worktree` 验证是否本次引入 (iter_188 用过);
   ⑤ faulthandler 对 SIGTRAP 无效, 不要被"没有栈"误导 —— 试 lldb 也可能挂住,
   二分反而更快。
2. **上游缺陷要在自己边界兜住**: `addSyntaxTree` trap 是 pyslang/slang 的问题,
   但用户看到的是我们的 CLI 崩。守卫成本 30 行, 换来"任意垃圾输入都不崩进程"。
3. **判据取最小范围**: 不写"必须是 CompilationUnit"(会误伤 `ModuleDeclaration`/
   空文件等常见合法输入), 只拒绝**表达式根** —— 这是"找通用型最佳方案"与
   "不误伤"的平衡。
4. **`-f` 语义歧义是事故温床**: 本项目 `-f` = `--file` (单文件), `--filelist` 才是
   filelist; 但很多工具 `-f` 就是 filelist。本次崩溃正是这么被触发的 (Ventus 测试
   生成器与命令行习惯都踩过) → 已登记为待决项 (是否统一/加友好报错)。

## 📢 待方豆决定

| # | 事 | 建议 | 代价 |
|---|---|---|---|
| 1 | `-f` 歧义 (本项目 `-f`=`--file`) | 可选: `-f` 同时接受 filelist (按内容/扩展名判定) 或给 `.f` 内容加显式提示 | 小 |
| 2 | 是否向上游 pyslang 报此 trap | 有最小复现, 可直接提 issue (addSyntaxTree 应返回错误而非 trap) | 小 |
| 3 | iter_188 遗留的 13 个 SVG 语义 skip | 需方豆确认可视化语义后重写断言 | 中 |

## 📎 关联

- 修复: `src/trace/core/compiler.py` (`_reject_non_design_unit`)
- 回归测试: `sim/tests/unit/test_compiler_non_design_unit_guard.py`
- 文档: `docs/KNOWN_LIMITATIONS.md` §3.1、`TESTING.md` 已知限制
- 前置: `iter_188_ventus_viz_suite_triage.md` (发现该崩溃)
