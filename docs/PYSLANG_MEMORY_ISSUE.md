# pyslang 解码/乱码与"波动"问题 — 真根因 (iter_185 更正版)

> **⚠️ 2026-09-08 iter_185 重大更正**: 本文件原名 "pyslang 内存不足问题",
> 把 PR1 时代 (2026-06-14) 的 flakiness 归因于 **8GB 内存不足**。该归因
> **已被证伪**: 真因是**我们自己的 `SourceManager` 生命周期 bug** ——
> `SVCompiler._do_compile()` 把 `pyslang.SourceManager` 存成局部变量,
> parse 循环结束后被 GC, 它持有的**源文件 buffer 被释放**, 而所有符号名 /
> token 文本都是指向这些 buffer 的 `string_view`。
> 完整复盘: `docs/task_tree/iterations/iter_185_slang_sourcemanager_lifetime.md`
> 原文 (内存压力观察) 保留在下方"历史记录", 但结论不再成立。

## 摘要 (现行结论)

**乱码符号名 / 随机 `UnicodeDecodeError` / 结果跨次漂移 = "读已释放内存"的
典型签名。** 在 sv_query 里它的来源是 pyslang 的**所有权边界**:

| slang 侧以 `string_view` 存储的东西 | Python 侧必须持有所有权到 Compilation 结束 |
|---|---|
| `SourceManager` 持有的源文件 buffer (`FileData`) | manager 对象本身 |
| `CompilationOptions.topModules` (`flat_hash_set<string_view>`) | 传入的 str 对象 |
| `CompilationOptions.paramOverrides` (`vector<string_view>`) | 传入的 str 对象 |

`SyntaxTree.fromFile/fromText` 的绑定带 `py::keep_alive<0,2>`, 只保证
"**Python tree wrapper 活着**时 manager 活着"; 而 `Compilation.addSyntaxTree()`
之后 Python 侧那个 `tree` 局部变量就可以被回收 → manager 引用计数归零 →
buffer 释放 → 所有 `string_view` 变垃圾。

### 最小复现 (纯 pyslang, 不依赖项目代码)

```python
import pyslang
SRC = "module top; logic [3:0] a; child u_c (.x(a)); endmodule\nmodule child(input logic x); endmodule\n"

comp = pyslang.ast.Compilation()
sm = pyslang.SourceManager()                    # 私有 manager
tree = pyslang.syntax.SyntaxTree.fromText(SRC, sourceManager=sm, name='t.sv')
comp.addSyntaxTree(tree)
del sm, tree                                    # ← 丢引用
print(comp.getRoot().topInstances[0].name)      # → UnicodeDecodeError
```

保留 `sm` 引用 (或干脆不传 `sourceManager=`, 用默认 manager) → 名字正常。

## 现象 → 真因映射 (历史症状表)

| 历史症状 | 真因 |
|---|---|
| `get_modules()` 数量波动 (50~120+) | 名字读垃圾 → 去重键/分类随机 |
| 模块名为 `<id:binary>` / `_anon_` / `_bad_` / 空串 | 这些是**我们代码对垃圾名的分类标记** (不是 slang 行为) — 名字坏掉后我们的过滤逻辑把它们归一成这些占位符 |
| 访问 pyslang 属性偶发 `UnicodeDecodeError` | `string_view` 指向已释放内存, 且落在非 UTF-8 字节上 |
| `build_graph()` 节点数随机 (2076~5200 / 1076~3408) | 名字坏掉 → 路径去重、模块解析、generate 下钻结果随机 |
| 同一 source 连跑结果不同 | 症状由**内存复用模式**决定 (释放的字节被覆写与否) |

**为什么"内存不足"看起来像根因**: `reclaim_memory()` (分配 4GB bytearray)
技巧确实能让结果更稳定 —— 因为它改变了堆的复用模式, 而不是因为"内存不够"。
它治的是症状。iter_185 修复后该技巧不再是必要条件。

## 修复 (iter_185, 已在 `src/trace/core/compiler.py`)

```python
self._source_manager = sm        # 所有权挂到 compiler (_do_compile 内)
self._param_overrides = list(_overrides)   # 同类加固
```

修复后实测 (同一 axi 语料): 乱码名 **3,349 → 0**、可遍历符号 **10,957 → 23,567**、
graph nodes **2,275 (波动) → 4,946 (3/3 完全一致)**、flakiness `--runs 3`
**stdev = 0.0**。

## 编码规范 (新代码必须遵守)

1. 凡把 Python str 交给 pyslang 的 **string_view 型 option**
   (`topModules` / `paramOverrides` / `defaultLiblist`), 必须持有该 str
   到 Compilation 生命周期结束 (存 `self._xxx`);
2. 自己创建 `pyslang.SourceManager()` 时, 必须保证它比所有使用其 syntax
   tree / 符号的代码活得久 (推荐直接交给持有者对象);
3. 看到"乱码名 / 随机 getter 异常 / 结果漂移"三连, **先查生命周期**,
   不要先怀疑输入数据或内存压力。

## 历史记录 (保留, 结论已更正)

以下为 2026-06-14 PR1 调查时的原始记录 (当时归因于内存压力):

- 环境: 8GB MacBook Air, 物理内存 7.5GB used / free ~100MB, swap 3.1GB (76%);
- 关闭浏览器 → flakiness ±60% → ±34%; `reclaim_memory()` (4GB bytearray) →
  free ~1350MB, graph 2076-3089 → 4600-5200, IM 39-77 → ~218, 10 次一致率 0/10 → 7/10;
- 当时结论: "pyslang elaboration 在内存不足时静默失败" — **不成立**;
  真实解释: 那些"稳定化"操作改变了内存复用模式 (见上);
- `SVCompiler._do_compile()` 里保留的 swap 告警 (`_check_memory_pressure`)
  **仍然是有效提示** (内存压力本身会让 pyslang 慢/失败), 但它**不是**
  解码乱码的原因。

## 参考

- 真根因复盘: `docs/task_tree/iterations/iter_185_slang_sourcemanager_lifetime.md`
- 上游代码: `~/my_dv_proj/slang/source/text/SourceManager.cpp`
  (`assignText` 复制文本 / `cacheBuffer` 把 buffer 交给 manager 的 `FileData`),
  `bindings/python/SyntaxBindings.cpp` (`fromText` 的 `py::keep_alive<0,2>`)
- 基准影响: `docs/BENCH_BASELINE.md`
