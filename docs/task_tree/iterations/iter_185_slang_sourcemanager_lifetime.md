# Iteration 185: pyslang SourceManager 生命周期 — benchmark 波动的真根因

**Metadata**:
- **Iteration #**: 185
- **Task Tree Level**: L1 (基础设施正确性)
- **Parent Task**: (C 路线: 质量纵深; iter_180~184 稳定性/健壮性族的**真根因**收敛)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 成功 (真因定位 + 修复 + 基准从"波动"变"确定性")

## 🎯 本次目标

**起点不是这个课题** — 本次是 iter_184 收尾: pr5 wrapper benchmark 里
`test_l1_instance_chain` 失败 (`instance_count=0`), 按纪律**不许放宽断言**,
必须先诊断根因 (方豆长期指令: "失败时正确归因", AGENTS.md 核心纪律 3)。

## 📊 当前状态 / 预期结果

**开工时的假设 (继承 iter_181/183/184)**: 该 filelist (pulp axi + common_cells)
含**非 UTF-8 identifier** → pyslang 属性 getter (`obj.name`) 取值本身抛
`UnicodeDecodeError` → elaboration 部分失败 → L1 实例 2→0、节点数漂移。
沿此假设的"正确做法"是继续 safe_attr 打地鼠 + 用干净语料做精确基准。

## 🔬 实际结果

### 1. 假设被证伪 — 语料根本没有非 UTF-8 字节

```python
# axi/**/*.sv + common_cells/**/*.sv 全部 UTF-8 解码
non-utf8 files: 0
```

### 2. 失败的 L1 是"静默空结果", 但空的原因不是崩溃

`collect_l1` → `extract_module(adapter, "pr5_wrap")` → `_find_module()` 找不到
`pr5_wrap` → 返回**空** `ModuleExtraction` (无 error, benchmark 报
`instance_count=0`)。逐层下钻发现:

| 观察 | 结果 |
|---|---|
| `root.topInstances` | **1 个**, 就是目标 top |
| 该 top 的 `.name` | `'\x00\x14\x00z\x00-\x00y'` ← 垃圾字节 |
| 它的 `definition.name` / `body.name` | 同一个垃圾串 |
| `get_modules()` 里 | 86 个"模块", 名字含 `'=ecod'` / `'rtE'` / `'unknown'` |
| 项目自己的告警 | `缺少 '        ? ' 的定义文件` / `缺少 '   arb_    ' 的定义文件` |

→ 名字是**垃圾**, 但**没有任何异常**; 而 `get_modules()` / `_find_module()`
全部基于名字 → 名字一坏, L1 就静默返回空。

### 3. 最小复现 (决定性实验)

```python
import pyslang
SRC = "module top; logic [3:0] a; child u_c (.x(a)); endmodule\nmodule child(input logic x); endmodule\n"

def run(mode):
    comp = pyslang.ast.Compilation()
    if mode == 'private_sm_del':
        sm = pyslang.SourceManager()                       # ← 私有 manager
        tree = pyslang.syntax.SyntaxTree.fromText(SRC, sourceManager=sm, name='t.sv')
        comp.addSyntaxTree(tree)
        del sm, tree                                       # ← 用完即丢
    elif mode == 'private_sm_keep':
        ...  # 同样构造, 但把 sm 存进全局
    ...
    return [repr(t.name) for t in comp.getRoot().topInstances]
```

| 模式 | 结果 |
|---|---|
| 默认 manager (不传 `sourceManager=`) | `'top'` ✅ |
| 私有 manager + **保留引用** | `'top'` ✅ |
| 私有 manager + **丢弃引用** | `<UnicodeDecodeError>` ❌ (4/4 稳定复现) |

**结论**: pyslang 的 `py::keep_alive<0,2>` 只保证"**tree wrapper 活着**时
manager 活着"; `Compilation.addSyntaxTree()` 在 C++ 侧持 `shared_ptr<SyntaxTree>`,
但 loop 里那个 `tree` 是 Python 局部变量, 下一轮就被回收 → manager 引用计数
归零 → **manager 析构 → 源文件 buffer 释放** → 所有指向 buffer 的
`string_view` (符号名 / token 文本) 变成释放内存里的垃圾字节。

slang 侧证据 (`~/my_dv_proj/slang/source/text/SourceManager.cpp`):
- `assignText()`: `SmallVector<char> buffer; buffer.insert(text...)` → 文本被
  **复制进 manager 自己的 `FileData`**;
- `cacheBuffer()`: `auto fd = std::make_unique<FileData>(..., std::move(buffer), ...);
  lookupCache.emplace(pathStr, std::move(fd))` → buffer 归 **manager** 所有。

### 4. 本项目里的同一 bug

`src/trace/core/compiler.py::_do_compile()`:

```python
sm = None
if include_dirs:                 # ← 只有带 +incdir+ 的 filelist 才会走到这里
    sm = pyslang.SourceManager() # ← 局部变量, 函数返回即被 GC
    for d in include_dirs:
        sm.addUserDirectories(d)
for fname, source in self._sources.items():
    tree = pyslang.SyntaxTree.fromText(source, sourceManager=sm, name=fname)  # ← tree 也是局部
    self._comp.addSyntaxTree(tree)
```

- `include_dirs` 来自 filelist 的 `+incdir+` 行 → **真实工程 (axi / CVA6 / UVM)
  必命中**, 而单元测试的小 fixture 通常不带 incdir → 长期只在"大语料"上暴露;
- 症状与内存复用模式强相关 → 表现为"跑几次结果都不同"(iter_180 的
  "runs>1 退化"、iter_181 的"跨次波动"、PR1 时代的 "graph 2076~5200")。

### 5. 修复与量化验证

**修复** (`compiler.py`, 3 处):
1. `__init__` 新增 `self._source_manager`; `_do_compile()` 里
   `self._source_manager = sm` (所有权挂到 compiler);
2. override-orphan 重编时释放旧 manager (`self._source_manager = None`);
3. 同类加固: `self._param_overrides` 持有 override 字符串 —
   slang 侧 `options.paramOverrides` 是 `vector<string_view>`,
   `options.topModules` 是 `flat_hash_set<string_view>`, view 都指向 Python
   str 的 buffer (slang 不拷贝) → 必须保证 str 活到 Compilation 生命周期结束。

**量化 (同一语料同一命令, `--target pr5_wrap --depth 4`)**:

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 可遍历符号节点 | 10,957 | **23,567** |
| 有名符号种类 (Instance/Variable/Port/...) | 7,441 | **14,604** |
| `name` getter 失败 (None) | 647 → 建图后 1,508 | **0** |
| 乱码名 (非可打印 ASCII) | 1,340 → 建图后 3,349 | **0** |
| graph nodes | 2,275 (且跨次 1,076~3,408) | **4,946 (3/3 完全一致)** |
| IM / 最大深度 | — | **516 / 14** |
| `pr5_wrap.clk_i` fanout | 0~137 | **445** |
| flakiness `--runs 3` | 失败/stdev 大 | **stdev = 0.0** |
| pr5 套件 | 1 failed (L1=0) | **13 passed + 1 skipped** |

空壳 (默认 Cfg) 对照: 168 nodes / IM 2 / clk 2 — 深结构与空壳区分度反而更清晰。

### 6. 断言收紧 (不许"为通过而放宽", 同理也不许留着松弛的假下限)

iter_184 因**错误诊断**把 wrapper 断言放宽为 `fanout >= 30 or nodes >= 800`;
真因修复后收紧回实测下限: nodes ≥4,000 / IM ≥400 / 深度 ≥12 / clk ≥300,
并在 docstring 里写明"放宽的理由已被证伪"。

## 💡 关键发现 / 关键技术 / 决策

1. **pyslang 所有权规则 (最重要)**: 凡 slang 侧以 `string_view` 存的东西
   (`CompilationOptions.topModules` / `paramOverrides`, 以及 `SourceManager`
   持有的源文件 buffer), **Python 侧必须持有所有权到 Compilation 结束**。
   pyslang 只对 `SyntaxTree` 建了 `py::keep_alive`, 而
   `Compilation.addSyntaxTree()` 之后 tree 的 Python wrapper 可以死 —— 这
   恰恰是 manager 被误回收的入口。
2. **"非 UTF-8 identifier" 是五年老误会 (PR1 2026-06-14 起)**:
   `docs/PYSLANG_MEMORY_ISSUE.md` 把 flakiness 归因于 8GB 内存不足 +
   `reclaim_memory()` 4GB 技巧 (它确实"有效", 因为改变了内存复用模式),
   `iter_141/181/182/183/184` 又归因于语料编码。真因是悬垂 `string_view`。
   教训: **乱码名 + 随机 getter 异常 + 结果漂移** 是"读已释放内存"的
   典型签名, 优先怀疑**生命周期**, 而不是先怀疑输入数据。
3. **静默空结果是放大器**: `_find_module()` 找不到目标 → `extract_module()`
   返回空结构且无 error → benchmark 报 `instance_count=0`。名字可读性是
   L1 的**隐含前置条件**, 却没有任何断言守着 (见"建议")。
4. **修根因 vs 打地鼠**: iter_181~184 共修了 ~10 处 `safe_attr` getter 点,
   每处都"有效"但只是把崩溃变成静默降级; 真正解决只花了 3 行所有权修正。
   `safe_attr` 本身没错 (防御价值保留), 但**不能替代根因定位**。
5. **验证手段**: 最小 pyslang 复现 (4 种 manager 生命周期 × 4 次) 是本次
   定性的关键 — 它把"环境玄学"变成"必然", 比在项目里跑 5 次语料高效得多。

## 📢 需要方豆决定 / 建议 (未擅自动手)

| # | 事 | 现状 → 建议 | 代价 |
|---|---|---|---|
| 1 | `tools/benchmark/run_benchmark.py::reclaim_memory()` (4GB 分配技巧) | 它是为掩盖本 bug 而加的, 现在非必要 → 建议移除 (每次省 ~3s) | 小 |
| 2 | `uvm_testbench_extractor.py:81` 私有 SourceManager | 当前 trees 只在本函数帧内使用 (安全), 但 `_class_defs` 把 **syntax node 存进 self** → 一旦跨界使用即悬垂 → 建议改用它自己的 `SVCompiler`/持有 manager | 中 |
| 3 | `docs/PYSLANG_MEMORY_ISSUE.md` | 已按真因改写 (内存压力保留为历史观察), 但该文档名/定位是否还要留? | 小 |
| 4 | `compiler.py::PYSLLANG_BINDINGS_PATH` | 硬编码 `/Users/fundou/my_dv_proj/slang/build/bindings` — 该目录**已不存在** (pyslang 从 miniconda 站点包导入) → 死路径, 建议删除或加存在性判断 | 小 |
| 5 | `_find_module()` 静默空结果 | **已改** (本次顺手): `extract_module()` 找不到目标模块时 `logger.warning` (含语义树模块数) — 正是这个静默把 iter_185 的真因藏了 4 个迭代 | 小 |
| 6 | iter_141/181/182/183/184 的 `safe_attr` 家族 | 保留 (廉价防御), 但相关注释已更正, 不再宣称"非 utf8"根因 | — |

## 📎 关联

- 修复: `src/trace/core/compiler.py` (`_source_manager` / `_param_overrides`)
- 断言收紧: `sim/tests/usage/test_benchmark_pr5.py`
- 基准重测: `docs/BENCH_BASELINE.md`
- 更正: `docs/PYSLANG_MEMORY_ISSUE.md`、`iter_180/181/184` 记录头部注记
- 上游证据: `~/my_dv_proj/slang/source/text/SourceManager.cpp`
  (`assignText` / `cacheBuffer`)、`bindings/python/SyntaxBindings.cpp`
  (`fromText` 的 `py::keep_alive<0,2>`)
