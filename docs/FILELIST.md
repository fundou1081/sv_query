# sv_query Filelist 格式支持

> 创建时间: 2026-06-01
> 状态: 完整支持

---

## 概述

sv_query 支持 Verilator / Modelsim 风格的 filelist 格式，用于指定多文件 SystemVerilog 项目的编译单元。

filelist 是工业级 SV 项目（如 OpenHW Group CVA6、OpenTitan、SiFive 核心等）常用的文件管理方式。

---

## CLI 使用

```bash
# 单文件
python run_cli.py visualize graph -f module.sv

# 使用 filelist
python run_cli.py visualize graph -f top.sv --filelist project.fl

# 使用 include 路径
python run_cli.py visualize graph -f module.sv -I path1,path2

# 组合使用
python run_cli.py visualize graph -f top.sv --filelist project.fl -I include/
```

---

## Filelist 语法

### 基本格式

每行一个文件路径：

```filelist
core/cva6.sv
core/alu.sv
core/branch_unit.sv
```

### 注释

```filelist
// 单行注释
# 也可以用 # 开头
core/cva6.sv   # 行尾注释
```

### `+incdir+` 添加 include 搜索路径

```filelist
+incdir+core/include
+incdir+vendor/pulp-platform/common_cells/include
+incdir+${CVA6_REPO_DIR}/core/include/
```

### `-F` / `-f` 嵌套加载

```filelist
-F vendor/hpdcache/hpdcache.Flist
-f ${CVA6_REPO_DIR}/core/Flist.cva6
```

支持多层嵌套，自动避免循环引用。

### 环境变量展开

```filelist
${CVA6_REPO_DIR}/core/cva6.sv
$HOME/my_project/module.sv
```

环境变量从两个来源解析（按优先级）：
1. 通过 `--include` 显式传入的 filelist
2. 系统 `os.environ`

### `+define+` 宏定义

```filelist
+define+DEBUG=1
+define+XLEN=64
+define+USE_FEATURE
```

宏定义会传递给子 filelist。

### `+libext+` （占位，跳过）

```filelist
+libext+.sv+.v
```

sv_query 不需要此选项，会被忽略。

---

## 环境变量设置

### Bash/Zsh

```bash
export CVA6_REPO_DIR=/Users/fundou/my_dv_proj/cva6
export TARGET_CFG=cv64a6_imafdc_sv39
export HPDCACHE_DIR=/path/to/hpdcache

python run_cli.py visualize graph -f cva6.sv --filelist Flist.cva6
```

### 命令行一次性

```bash
CVA6_REPO_DIR=/path/to/cva6 TARGET_CFG=cv64a6_imafdc_sv39 \
  python run_cli.py visualize graph -f cva6.sv --filelist Flist.cva6
```

---

## 实际案例：CVA6

CVA6 是工业级 RISC-V CPU，有 ~150 个 SV 文件分布在多个子模块。

### 简化 filelist 示例

```filelist
// /tmp/cva6_test.fl

// Include 路径
+incdir+${CVA6_REPO_DIR}/core/include/
+incdir+${CVA6_REPO_DIR}/core/cvfpu/src/
+incdir+${CVA6_REPO_DIR}/vendor/pulp-platform/common_cells/include/
+incdir+${CVA6_REPO_DIR}/vendor/pulp-platform/common_cells/src/
+incdir+${CVA6_REPO_DIR}/vendor/pulp-platform/axi/include/
+incdir+${CVA6_REPO_DIR}/common/local/util/

// 必需的包
${CVA6_REPO_DIR}/core/include/config_pkg.sv
${CVA6_REPO_DIR}/core/include/cv64a6_imafdc_sv39_config_pkg.sv
${CVA6_REPO_DIR}/core/cvfpu/src/fpnew_pkg.sv

// 跳过的 vendor 引用 (本地缺失)
-F ${CVA6_REPO_DIR}/core/Flist.cva6
```

### 实际命令

```bash
cd ~/my_dv_proj/sv_query
CVA6_REPO_DIR=/Users/fundou/my_dv_proj/cva6 \
TARGET_CFG=cv64a6_imafdc_sv39 \
  python run_cli.py visualize graph \
    -f ~/my_dv_proj/cva6/core/cva6.sv \
    --filelist /tmp/cva6_test.fl \
    --dot /tmp/cva6.dot
```

**结果**: 加载 152 个 SV 文件 + 6 个 include 路径。

---

## Python API 使用

### 直接传 filelist

```python
from trace.unified_tracer import UnifiedTracer

tracer = UnifiedTracer(
    sources={},                    # 留空
    filelist='project.fl',         # filelist 路径
    include_dirs=['extra/include'] # 额外 include 路径
)
graph = tracer.build_graph()
```

### 用环境变量

```python
import os
os.environ['CVA6_REPO_DIR'] = '/path/to/cva6'

tracer = UnifiedTracer(filelist='cva6.fl')
```

### 读取所有源码 (for SVA/Covergroup)

```python
tracer = UnifiedTracer(filelist='project.fl')
graph = tracer.build_graph()

# 复用 tracer 已加载的 sources 给 SVA/Covergroup
compiler = tracer._get_compiler()
sources = compiler._sources

from trace.core.sva_extractor import SVAExtractor
sva = SVAExtractor(sources).extract()
```

---

## 限制

### 1. `parameter type` 解析

CVA6 大量使用 `parameter type fu_data_t = logic`，独立看子模块无法解析具体类型。
**解决**: 必须从顶层 `cva6.sv` 入口。

### 2. 复杂宏定义

```svh
`define X_COMPRESSED_REQ_T(Cfg, hartid_t) struct packed { ... }
```

pyslang 不能完整展开某些复杂宏。
**影响**: 依赖这些宏的文件可能报 "invalid member access" 错误。

### 3. UVM 集成

需要 UVM 源码。sv_query 自动检测并加载默认 UVM 路径。

### 4. 错误处理

当前策略: **任何 elaboration 错误抛出异常**。
**影响**: 大型项目可能因单个文件错误导致整个图无法生成。
**解决方向**: 改进为容错模式，输出部分图 + 错误清单。

---

## 验证 filelist 解析

```bash
# 测试 filelist 加载了多少文件
python -c "
import sys
sys.path.insert(0, 'src')
from trace.core.compiler import SVCompiler
import os
c = SVCompiler()
c.add_filelist(
    'project.fl',
    env={'CVA6_REPO_DIR': '/path'}
)
print(f'Sources: {len(c._sources)}')
print(f'Include dirs: {len(c._include_dirs)}')
"
```

---

## 调试技巧

### 1. 查看加载的文件

```bash
# 加载后用 git submodule status 验证 vendor 完整性
cd ~/my_dv_proj/cva6 && git submodule status
```

### 2. 跳过问题文件

```python
# 直接修改 SVCompiler._sources 过滤
# 例如: 跳过 cvxif 相关文件
to_remove = [k for k in c._sources.keys() if 'cvxif' in k.lower()]
for k in to_remove:
    del c._sources[k]
```

### 3. 使用环境变量控制

```bash
# 只看顶层 (避免子模块级 parameter type 错误)
TARGET_CFG=cv64a6_imafdc_sv39 \
  python run_cli.py visualize graph -f top.sv --filelist Flist.cva6
```

---

## 相关文档

- `docs/ARCHITECTURE.md` - 整体架构
- `docs/README.md` - 可视化命令
- `docs/USER_GUIDE.md` - 用户使用指南
- `docs/DISCIPLINE_VIOLATIONS.md` - pyslang 限制记录

---

**最后更新**: 2026-06-01
