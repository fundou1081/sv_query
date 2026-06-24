# Contributing to sv_query

> **新成员入门指南** — 30 秒理解 → 5 分钟跑起来 → 30 分钟懂架构 → 加你的第一个 feature

---

## 📍 0. 项目一句话

**sv_query** 是一个 SystemVerilog 静态分析工具: 让验证工程师直接问"这个信号谁驱动的？"
而不是读代码。基于 pyslang (MikePopoloski 的 SV 解析器) + 自己的 4 维分析
(L1 module 抽取 → L2 端口连接 → L3 内部信号 → L4 可视化)。

---

## 🚀 1. 5 分钟跑起来

### 1.1 准备环境

```bash
# 要求: Python 3.11+, git
python3 --version

# Clone 项目
git clone https://github.com/fundou1081/sv_query.git
cd sv_query

# 装依赖 (dev 模式)
pip install -e ".[dev]"

# pyslang 不在 PyPI, 装 GitHub 版
pip install git+https://github.com/MikePopoloski/pyslang.git

# 验证 (expect: 2415 collected, ~30s)
python -m pytest sim/tests/unit sim/tests/cli -q
```

### 1.2 第一次跑命令

```bash
# 看一个简单的 sv 文件
cat sim/openTitan_validation.sv | head -30

# 跑 stats 命令: 列出所有信号 + 风险分数
python run_cli.py stats -f sim/openTitan_validation.sv

# 跑 trace 命令: 看 state_q 的驱动链
python run_cli.py trace fanout -f sim/openTitan_validation.sv -s state_q

# 跑 coverage 命令 (Phase 3 新加): 给一个信号自动生成 covergroup
python run_cli.py coverage generate -f sim/openTitan_validation.sv -s data_o
```

跑通了 = 你的环境 OK。

---

## 🏛️ 2. 30 分钟理解架构

### 2.1 顶层目录

```
sv_query/
├── README.md               # 项目门面 (5min quickstart 在这)
├── CONTRIBUTING.md         # 你正在读的文件
├── run_cli.py              # CLI 入口 (typer based)
├── src/                    # 核心代码 (~26K 行)
│   ├── trace/
│   │   ├── core/
│   │   │   ├── compiler.py          # pyslang 编译入口 (用这个就对了)
│   │   │   ├── graph/               # 信号图 (节点 + 边)
│   │   │   │   ├── builder/         # 4 维 builder (L1/L2/L3/L4)
│   │   │   │   └── analyzer/        # 各种分析器 (controlflow, timing, cdc)
│   │   │   ├── driver_extractor.py  # L3: 提取 always block 内 driver
│   │   │   ├── edge_factory.py      # 边工厂
│   │   │   └── covergroup_*.py      # covergroup 分析
│   │   └── unified_tracer.py        # 顶层 facade
│   └── cli/
│       ├── main.py                  # typer app
│       ├── _common.py               # `_build_tracer` 等共享工具
│       └── commands/                # 21 个 CLI 命令
│           ├── trace.py             # trace fanin/fanout/impact/evidence
│           ├── stats.py             # 列出所有信号
│           ├── risk.py              # 风险分数
│           ├── coverage.py          # [Phase 1-3] coverage generate
│           ├── visualize.py         # L4 Graphviz
│           └── ... (其他 16 个)
├── tools/                          # 独立工具 (跟我们这次加的 2 个)
│   ├── coverage_gen_demo.py         # [Phase 1] 主工具 (生成 covergroup)
│   └── coverage_gen_sv_compile.py   # [Phase 3 #C] SV 编译验证
├── sim/
│   ├── tests/
│   │   ├── unit/        # 1263 tests (最快, 单文件, 1-2s)
│   │   ├── cli/         #   59 tests (CLI 端到端, 5-10s)
│   │   ├── integration/ #  385 tests (跨模块 + 工业项目, 中等)
│   │   └── regression/  #  708 tests (含 OpenTitan ascon 等大型工业项目, 慢)
│   ├── openTitan_validation.sv      # 测试用 SV (含 8+ 子模块, 完整 SV 子集)
│   ├── TEST_REPORT.md               # 自动生成的测试报告 (每次跑覆盖度更新)
│   └── golden/coverage_gen_demo/    # Phase 1 golden baselines (3 工业项目)
└── docs/                           # 60+ 设计/架构/开发文档
```

### 2.2 核心概念: 4 维分析

```
L1: Module 抽取      ──►  ModuleInstanceGraph (MIG)        # "哪些 module 在这里?"
L2: 端口连接          ──►  PortGraph                        # "signal 怎么穿越 submodule?"
L3: 内部信号驱动      ──►  SignalGraph                      # "谁驱动这个 reg?"
L4: 可视化            ──►  Graphviz dot                     # "画给我看"
```

新人从 **L3 (SignalGraph)** 开始最容易上手 — 跟用户问题最直接 ("谁驱动这个信号")。

### 2.3 核心代码导读 (按重要性)

| 想做什么 | 读这个 |
|---------|-------|
| 看入口 | `src/cli/main.py` |
| 加新 CLI 命令 | `src/cli/commands/risk.py` (200 行, 模板) |
| 解析 SV (基础) | `src/trace/core/compiler.py` (`_build_tracer` 用这里) |
| 拿 signal graph | `src/trace/core/graph/data_models.py` (节点/边定义) |
| 加新分析算法 | `src/trace/core/graph/analyzer/` (cdc/timing/controlflow 模板) |
| 跑测试 | `sim/tests/{unit,cli,integration,regression}/` |

### 2.4 一次 "hello world" 调用

```python
# 看一个信号的 driver
import sys; sys.path.insert(0, 'src')
from pathlib import Path
from cli._common import _build_tracer

tracer = _build_tracer(
    file=Path('sim/openTitan_validation.sv'),
    strict=False,  # 工业代码常见 warning, 用 False 优雅降级
)
tracer.build_graph()

# 拿 graph + 找 driver
g = tracer.get_signal_graph()
for node in g.nodes():
    print(f"node: {node.name}, type={node.kind}")
```

3 行 = 拿到完整信号图。`_build_tracer` 是 sv_query **统一入口**，所有 CLI 都用它。

---

## 🛠️ 3. 常见任务 (怎么加新 X)

### 任务 A: 加一个新的 CLI 命令

模板 — 复制 `src/cli/commands/risk.py` 改 3 处:

```python
# src/cli/commands/mynew.py
import typer
from typing import Optional

mynew_app = typer.Typer(help="My new command")

@mynew_app.command("do-something")
def do_something(
    file: str = typer.Option(..., "-f", "--file", help="RTL file"),
    signal: str = typer.Option(..., "-s", "--signal", help="Signal name"),
    include: list[str] = typer.Option(None, "-I", "--include", help="Include dirs"),
    filelist: Optional[str] = typer.Option(None, "--filelist", help="Filelist"),
):
    """Description of my new command."""
    from pathlib import Path
    from cli._common import _build_tracer
    tracer = _build_tracer(file=Path(file), filelist=filelist, include_dirs=include)
    tracer.build_graph()
    # ... do your analysis ...
    print("result")

if __name__ == "__main__":
    typer.run(mynew_app)
```

然后 `src/cli/main.py` 加 `from cli.commands.mynew import mynew_app` + `app.add_typer(mynew_app, name="mynew")`。

### 任务 B: 加一个新的分析器

模板 — 复制 `src/trace/core/graph/analyzer/cdc_analyzer.py`:

```python
# src/trace/core/graph/analyzer/my_analyzer.py
from typing import Any

class MyAnalyzer:
    """Doc: 做什么分析."""
    def __init__(self, signal_graph):
        self.g = signal_graph
    def analyze(self) -> dict[str, Any]:
        result = {}
        # ... 算法 ...
        return result
```

### 任务 C: 加新测试

| 测试类型 | 放这里 | 速度 |
|---------|-------|------|
| 单元 (单函数) | `sim/tests/unit/test_<module>.py` | < 1s |
| CLI (跑 run_cli.py) | `sim/tests/cli/test_<cmd>.py` | 1-5s |
| 集成 (多 module) | `sim/tests/integration/test_<feature>.py` | 5-30s |
| 回归 (工业项目) | `sim/tests/regression/test_<project>.py` | 30s+ |

模板 — 复制 `sim/tests/unit/test_pyslang_type_extraction.py` (含 fixture 共享 + 工业项目 skip)。

### 任务 D: 加新文档

放 `docs/MY_FEATURE.md`，跟现有命名一致（如 `COVERAGE_GEN.md`、`CDC_ANALYSIS.md`）。

---

## 🧪 4. 测试体系

### 4.1 跑哪些测试

```bash
# 日常开发 (快速, 30s)
python -m pytest sim/tests/unit sim/tests/cli -q

# 提交前 (含 integration + regression, 5-15 min)
python -m pytest sim/tests/ -q

# 单个测试文件
python -m pytest sim/tests/cli/test_coverage_generate.py -v
```

### 4.2 测试统计 (截至 2026-06-24)

| 类型 | 文件数 | tests | 速度 |
|------|--------|-------|------|
| `unit/` | 83 | 1,263 | 30s |
| `cli/` | 7 | 59 | 5s |
| `integration/` | 51 | 385 | 5min |
| `regression/` | 88 | 708 | 15min |
| **总计** | **229** | **2,415** | **~25min 全套** |

### 4.3 工业项目测试

很多测试依赖工业项目 (`~/my_dv_proj/picorv32/` 等)。测试会用 `pytest.skip` 自动跳过：
- 工业项目**没装** → 自动 skip
- 工业项目**装了** → 自动跑

CI 跑全套（含工业项目）。本地没工业项目也能跑 unit + cli。

---

## 🚢 5. 提交 / CI 流程

### 5.1 提交前 checklist

```bash
# 1. 跑 unit + cli (必须 pass)
python -m pytest sim/tests/unit sim/tests/cli -q

# 2. 自己加的测试 (如果你改了 src/)
python -m pytest sim/tests/unit/test_<your_module>.py -v

# 3. CI workflow 不破坏 (如果你改了 workflow)
.github/workflows/coverage-gen.yml  # Phase 2 #7 workflow
.github/workflows/tests.yml          # 全套
.github/workflows/benchmark.yml     # benchmark regression

# 4. lint (warning 级别, 不 block)
ruff check src/ tools/ tests/
```

### 5.2 提交格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

- `<type>`: feat / fix / refactor / test / docs / ci
- `<scope>`: 模块名 (`coverage`, `trace`, `cli`, `compiler`)
- 例子: `feat(coverage): 加 packed struct field bins`

### 5.3 CI Workflows

| Workflow | 跑什么 | 时间 |
|---------|-------|------|
| `tests.yml` | 全套 sim/tests/ + coverage | 20min |
| `benchmark.yml` | picorv32 benchmark regression | 5min |
| `coverage-gen.yml` | [Phase 2 #7] coverage_gen_demo 工具测试 + 3 工业项目 golden | 10min |

提交后 GitHub Action 自动跑。**全部 pass 才 merge**。

---

## 📚 6. 必读文档 (按阅读顺序)

1. **README.md** — 项目门面 + 5min quickstart
2. **docs/COVERAGE_GEN.md** — 我们这次加的 coverage_gen_demo 工具 (Phase 1+2+3 #C, 完整)
3. **docs/ARCHITECTURE.md** — 4 维分析架构
4. **src/trace/core/compiler.py** — pyslang 怎么用的 (看注释头部)
5. **docs/PYSLANG_MEMORY_ISSUE.md** — pyslang 内存不足的坑 (8GB MBA 必看)
6. **docs/CODE_DISCIPLINE_REVIEW.md** — 代码规范 (项目自定)
7. **MEMORY.md** (在 OpenClaw workspace `~/.openclaw/workspace/MEMORY.md`) — 我 (QClaw) 的长程记忆, 含 sv_query 项目历史 + 踩坑

---

## ⚠️ 7. 常见坑

### 坑 1: pyslang 内存不足
8GB MBA 跑大工业项目会 OOM, pyslang **不会报错, 静默失败**。
跑前先回收 4GB:
```bash
python3 -c "import time; a = bytearray(4 * 1024**3); time.sleep(3); del a"
```
详见 `docs/PYSLANG_MEMORY_ISSUE.md`。

### 坑 2: 不要删 `~/.gradle/caches/modules-2/metadata-*/`
（跟 Java/Maven 有关, 不是 sv_query 项目, 但 OpenClaw 跑 MikuNotes 编译时常见坑）

### 坑 3: pyslang 不在 PyPI
必须从 GitHub 装: `pip install git+https://github.com/MikePopoloski/pyslang.git`

### 坑 4: CI 跑全套超时
本地跑 `sim/tests/unit sim/tests/cli` 就够 (30s)。全套 25min。

### 坑 5: filelist 路径
工业项目 filelist 假设项目在 `~/my_dv_proj/<project>/`。详见 `sim/tests/pyslang_type_fixtures/industrial_filelists/`。

### 坑 6: strict mode
默认 `strict=False`。**不要**改全局默认 — 工业代码常见 UnknownModule。

---

## 🤝 8. 找人问

| 问题类型 | 找谁 / 查哪里 |
|---------|--------------|
| pyslang API | `docs/PYSLANG_MEMORY_ISSUE.md` + `src/trace/core/compiler.py` 注释 |
| 加新 command 模板 | `src/cli/commands/risk.py` (200 行, 模板) |
| 测试 fixture | `sim/tests/{unit,integration}/conftest.py` |
| Coverage 工具 | `docs/COVERAGE_GEN.md` |
| 项目历史 + 决策 | OpenClaw workspace `~/.openclaw/workspace/MEMORY.md` |
| General Q | GitHub Issues / Discussions |

---

## 📊 9. 当前活跃开发 (2026-06-24)

- **coverage_gen_demo 工具** (Phase 1+2+3 #C 完结): 自动从 RTL 生成 covergroup, SV 编译验证
- **benchmark regression** (Phase 2 PR5+6+7): picorv32, OpenTitan 基线
- **CI workflow** (Phase 2 #7): 4 job 专门验证

新人最容易上手: **修/加 `coverage_gen_demo` 工具 + 加新 SV type 解析 + 加新 fixture**。

---

**最后**: 拿不到信号? 先看 README 第 100 行的常见故障排查。
有具体问题直接问 QClaw (我), 会拉相关 memory + 文档回答。