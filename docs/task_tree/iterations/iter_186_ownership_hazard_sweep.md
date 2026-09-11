# Iteration 186: 同族隐患系统排查 + 生命周期回归锁

**Metadata**:
- **Iteration #**: 186
- **Task Tree Level**: L1 (基础设施正确性)
- **Parent Task**: iter_185 续 (方豆 "继续" — 兑现 iter_185 报告里的建议项)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 2 处真实隐患修复 + 2 个回归锁 (已验证红/绿) + 死路径清理

## 🎯 本次目标

iter_185 定位的根因是 **pyslang/slang 侧 `string_view` 与对象所有权**问题
(`SourceManager` 持有源文件 buffer, 符号名/token 都是指向 buffer 的 view)。
本次做**同族系统排查**: 全仓找同类"把 buffer 的持有者丢早了"的点, 出清单 →
修真实隐患 → 加**回归锁**(防止同类 bug 再出现), 而不是等下一次玄学复现。

## 📊 当前状态 / 预期结果

预期: 只有 compiler.py 一处 (iter_185 已修), 其余是"架构安全"。
实际: **多找到 2 处真实/潜在隐患**, 其中 1 处是**测试里的活跃 bug**。

## 🔬 实际结果

### 排查清单 (扫描模式 → 命中)

| # | 扫描模式 | 命中 | 判定 |
|---|---|---|---|
| A | `pyslang.SourceManager()` 创建点 (src/tools) | `compiler.py:422` (iter_185 已修) / `uvm_testbench_extractor.py:81` | ⚠️ 潜在 (见 C) |
| B | `options.topModules` / `paramOverrides` 赋值 | 只有 `compiler.py` 两处 | ✅ 均已持有 (`self._top_modules` / `self._param_overrides`) |
| C | 符号 / syntax node **逃出创建帧** | `sim/tests/test_d1_generate_flatten_signal_set.py::_compile_case27` (返回 top/body) / `uvm_testbench_extractor._class_defs` (存 syntax node 到 self) | ❌ C1 活跃 bug / ⚠️ C2 潜在 |
| D | `pyslang.Compilation()` 创建点 | `compiler.py:349` / `uvm_testbench_extractor.py:82` / 测试 2 处 | 见 C |
| E | AST 缓存是否存 pyslang 对象 | `cache/ast_cache.py` 只存 JSON dict (`json.dump`) | ✅ 安全 |
| F | 硬编码开发机路径 | `compiler.py:38` + `semantic_adapter.py:51` `PYSLLANG_BINDINGS_PATH` | ❌ 死路径 (目录不存在) |
| G | 编译后再次改 compiler (`add_source`/`add_include_dir` 使 `_comp=None`) | 调用点均在编译前 (`UnifiedTracer._get_compiler`) | ✅ 安全 |

### C1 (活跃 bug): d1 测试 helper 丢掉了 buffer 持有者

`_compile_case27()` 把 `sm` / `comp` 都放在函数帧里, 却 `return root, top, top.body`
→ 帧退出后 manager 被回收 → 返回的符号名指向已释放内存。

**实测** (隔离复现, 与 helper 同构):

```
run 0: top.name='<UnicodeDecodeError>' body_names=<UnicodeDecodeError>
run 1: top.name='<UnicodeDecodeError>' body_names=<UnicodeDecodeError>
run 2: top.name='<UnicodeDecodeError>' body_names=<UnicodeDecodeError>
```

3/3 全崩。**为什么该套件一直是"8 passed"**: 没有内存压力时, 释放的内存还没被
覆写, 名字"碰巧"还是对的 — `test_case27_top_compiles` 里 `top.name` 在帧内
(安全) 与帧外 (运气) 各读一次, 恰好都过。**这正是 iter_158 记录里
"symbol 对象 str 垃圾" 的来源**, 也是 iter_116 "d1 lookupName 必崩" 之谜的
同族嫌疑 (那条是另一现象: 累计查询 mutex/segfault, 未定论)。

修复: 模块级 `_LIVE_SOURCE_MANAGERS` 登记 manager (与 `SVCompiler` 持有
`self._source_manager` 同一个不变量)。

### C2 (潜在): UVM extractor 的 `_class_defs`

`self._class_defs[class_name] = <syntax node>` — 节点逃生到 self, 但
manager/compilation 是局部变量。当前所有消费点 (`_find_var_type`) 都在
`extract()` 帧内 → **今天不会错**; 但任何"把 `_find_var_type` 挪到 extract 之后"
的改动都会立刻变成 C1 型 bug。

修复 (不重构, 只把不变量显式化): `extract()` 期间把 manager+compilation 挂到
`self._uvm_source_manager` / `self._uvm_compilation`, 遍历结束即释放。
顺手更正该处**错误注释**: 原文写 "SVCompiler full pipeline 会污染
parameterized UVM 类的 `token.name.value` (非 UTF-8 bytes)" — iter_185 证明那
就是 SourceManager 生命周期 bug, 不是 SVCompiler 的语义副作用。

### F: `PYSLLANG_BINDINGS_PATH` 死路径

`/Users/fundou/my_dv_proj/slang/build/bindings` 在本机**已不存在** (pyslang 从
miniconda 站点包导入), 但两处仍无条件 `sys.path.insert(0, ...)` — 个人绝对路径
硬编码 + 死路径, 会误导排查。改为 `os.path.expanduser("~/my_dv_proj/...")` +
`os.path.isdir()` 判定 (同时消掉两文件里重复的绝对路径)。

### 回归锁 (关键交付: 让同类 bug "不会再出现")

| 测试 | 位置 | 无修复时 | 有修复时 |
|---|---|---|---|
| `test_source_manager_outlives_compilation` | `sim/tests/unit/test_compiler_source_manager_lifetime.py` | ❌ failed | ✅ |
| `test_symbol_names_readable_after_gc_churn` (编译 → 强制 GC + 20 万对象 churn → 读全部符号名) | 同上 | ❌ failed | ✅ |
| `test_compile_helper_keeps_source_manager_alive` (确定性: helper 必须登记 manager) | `sim/tests/test_d1_generate_flatten_signal_set.py` | ❌ failed | ✅ |
| `test_symbol_names_readable_after_gc_churn` (d1 版) | 同上 | ❌ failed (top.name 变成空白!) | ✅ |

**红/绿双向验证**: 把修复临时去掉重跑 → 4 个新测试全红 (其中 d1 版实测
`top.name` 从 `'generate_loop'` 变成一片空格 — 垃圾字节的直观样子); 恢复后全绿。
(纪律: "修完要能回答同类 bug 还会不会再出现" — 这 4 个测试就是答案。)

### 自伤记录 (如实)

红/绿验证时我用了 `git checkout -- sim/tests/test_d1_generate_flatten_signal_set.py`,
把**该文件里我尚未提交的全部改动**一起抹掉了 (helper 修复 + 2 个新测试 + gc 导入)。
已重做, 并改为**先复制到 /tmp 自备份**再验证。
教训 (与 iter_177 "先删后归档" 同类): **对未提交的工作执行 `git checkout --`
= 删除**; 临时改动验证要用自己的备份, 不要用 git 恢复。

## 💡 关键发现 / 关键技术 / 决策

1. **"惯例安全" ≠ "不变量成立"**: C2 今天不错, 只因为它恰好只在帧内被消费 —
   这类"靠调用顺序维持的安全"就是下一个 bug 的温床, 所以我把持有关系显式化
   (即使多两行代码)。
2. **测试里的 `return <符号>` 是同族高危写法**: 只要 helper 编译 + 返回符号,
   就必须同时把 buffer 持有者交出去。已在新测试里锁住这个约束。
3. **回归锁要点**: 单纯"读一次名字"抓不到这个 bug (内存还没被复用) —
   必须**制造内存复用** (分配/释放大量小对象 + `gc.collect()`), 或者直接断言
   所有权关系 (确定性的那条)。两条都加了: 一条确定性、一条经验性。
4. **扫描模式可复用**: A~G 七类模式 (SourceManager 创建 / string_view option 赋值
   / 符号逃出帧 / Compilation 创建 / 缓存存对象 / 硬编码路径 / 编译后改 compiler)
   值得写进 `docs/PYSLANG_MEMORY_ISSUE.md` 的"编码规范"节 (已加)。

## 📢 待方豆决定 (未擅自动手)

| # | 事 | 现状 → 建议 | 代价 |
|---|---|---|---|
| 1 | `tools/benchmark/run_benchmark.py::reclaim_memory()` (4GB 技巧) | iter_185 后非必要 → 建议移除 (每次 +3s) | 小 |
| 2 | `uvm_testbench_extractor` 是否不再需要独立 `Compilation` 路径 (原理由已被证伪) | 它仍是合理的架构选择 (语法级分析不走过 SVCompiler 管线) → **建议保留**, 仅更正注释 (本次已做) | — |
| 3 | `compiler.py::add_source/add_include_dir/add_files/add_filelist` 里 `_comp = None` 但不释放 `_source_manager` | 只多留一次编译的 buffer 内存, 下次编译即替换 → 建议**不动** (改了没收益) | — |
| 4 | 是否 push 本地领先的 14 个 commit | 等方豆指令 | — |

## 📎 关联

- 代码: `sim/tests/unit/test_compiler_source_manager_lifetime.py` (新)、
  `sim/tests/test_d1_generate_flatten_signal_set.py`、
  `src/trace/core/uvm_testbench_extractor.py`、
  `src/trace/core/compiler.py`、`src/trace/core/semantic_adapter.py`
- 真因复盘: `iter_185_slang_sourcemanager_lifetime.md`
- 编码规范: `docs/PYSLANG_MEMORY_ISSUE.md`
