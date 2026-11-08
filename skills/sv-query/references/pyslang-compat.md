# sv_query pyslang 10/11 兼容性

> sv_query 完整支持 pyslang 10.0.0 和 11.0.0, 全量测试在 v10/v11 两边 100% 一致 (计数以 [docs/INDEX.md](../../../docs/INDEX.md) 为准)。
> 如果用户升级 pyslang 后出问题, 读这个文档。

---

## 1. 背景

pyslang 11.0 (2026-05) 引入 breaking changes:
- API 重构 (submodule 拆分, 一些类移走)
- 4 个语义差异 (SyntaxList 包装, foreach loop var, modport structure, ranges flatten)

我们用 `_pyslang_compat.py` (240 行 shim) 桥接。

---

## 2. 项目内的兼容机制

### 2.1 compat shim

`src/trace/core/_pyslang_compat.py`:

- 探测 v10 vs v11
- 提供统一 re-export: `SyntaxKind` / `SyntaxTree` / `TokenKind` / `Compilation`
- v11+ 通过 PEP 562 `__getattr__` 自动从 `pyslang.ast` 找缺的类
- v11+ 通过 `__init__.py` 注入 v10 风格的 attr 到 `pyslang` 主模块
- 提供 `is_syntax_list()` / `iter_syntax_list()` 适配 SyntaxList 包装消失

**业务代码用 `from trace.core._pyslang_compat import ...`, 不要 `from pyslang import ...`**

### 2.2 4 个语义差异适配

| 差异 | 业务修复位置 |
|------|-------------|
| #1 SyntaxList 包装消失 | 7 个文件, 用 `is_syntax_list` / `iter_syntax_list` |
| #2 foreach loop var 'i' 暴露 | `visitors/constraint_visitor.py` 位置-based 取 array name |
| #3 modport item.ports 结构 | `semantic_adapter.py` 用 `is_syntax_list` 判 sep_list |
| #4 InsideExpression.ranges flatten | `visitors/constraint_visitor.py` 同时支持 2 结构 |

---

## 3. agent 怎么诊断

### 3.1 看装的是哪个版本

```bash
python3 -c "import pyslang; print(pyslang.__version__)"
# 期望: 10.x 或 11.x
```

### 3.2 跑双版本 smoke 测试

```bash
cd <PROJ_DIR>/sv_query
python3 -m pytest sim/tests/integration/test_pyslang_version_compat.py -v
# 期望: 8 passed
```

### 3.3 跑全量

```bash
python3 -m pytest sim/tests/ -q
# 期望: 全量 passed (计数以 [docs/INDEX.md](../../../docs/INDEX.md) 为准)
```

### 3.4 切版本测试

```bash
# 装 v10
pip install pyslang==10.0.0
python3 -m pytest sim/tests/ -q   # 应该全量 passed (计数以 [docs/INDEX.md](../../../docs/INDEX.md) 为准)

# 装 v11
pip install pyslang==11.0.0
python3 -m pytest sim/tests/ -q   # 应该全量 passed (计数以 [docs/INDEX.md](../../../docs/INDEX.md) 为准)
```

---

## 4. 常见错误与处理

### 4.1 `ModuleNotFoundError: pyslang`

```bash
# 用户没装 sv_query
cd <PROJ_DIR>/sv_query
pip install -e .

# 或单独装依赖
pip install pyslang networkx typer
```

### 4.2 `ImportError: cannot import name 'X' from pyslang`

v11 把 X 移到 `pyslang.ast` 子模块。shim 自动处理。如果还报:

```bash
# 检查 shim 是否加载
python3 -c "from trace.core._pyslang_compat import SyntaxKind, SyntaxTree, Compilation; print('OK')"
```

### 4.3 `AttributeError: 'SyntaxNode' object has no attribute 'X'`

v11 拆了 SyntaxNode, 一些 attr 移到子节点。shim 适配 4 个已知差异, 其他新 attr 缺失请:
- 看 sv_query 业务代码
- 加 `is_syntax_list` / `iter_syntax_list` 调用
- 加测试 + commit

### 4.4 `pyslang version 12.0.0 not supported`

```bash
# 切回 v10/v11
pip install 'pyslang>=10.0.0,<12.0.0'

# 或看 shim 能不能扩, 提 issue
```

---

## 5. 升级 pyslang 后

### 5.1 跑测试

```bash
cd <PROJ_DIR>/sv_query
pip install pyslang==<新版本>
python3 -m pytest sim/tests/ -q
```

### 5.2 如果失败

- 99% 概率是新增的 4 个差异之一又变了
- 读 `sim/tests/integration/test_pyslang_compat.py` (12 单元测试) 找新差异
- 在 `_pyslang_compat.py` 加兼容代码
- 业务代码用 shim 提供的 helper

### 5.3 提交

```bash
# 测试全过后
cd <PROJ_DIR>/sv_query
git add -A
git commit -m "feat(compat): support pyslang <新版本>"
git push origin main
```

---

## 6. 给 agent 的提示

如果用户升级 pyslang 后跑 sv_query 报错:

1. 先 `python3 -c "import pyslang; print(pyslang.__version__)"` 确认版本
2. 跑 `python3 -m pytest sim/tests/integration/test_pyslang_version_compat.py` 跑 smoke
3. 跑 `python3 -m pytest sim/tests/ -q` 跑全量
4. 失败时看 `sim/TEST_REPORT.md` 里的失败 traceback, 通常是 `is_syntax_list` 漏改或新 attr 不存在
5. 告诉用户: "需要扩 shim, 这超出 skill 范围" 或直接修 (如果用户授权)
