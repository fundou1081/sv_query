# Iteration 176: Step 4-9 — 按域 mixin 拆分 (3036 → 227 行 facade)

**Metadata**:
- **Iteration #**: 176
- **Task Tree Level**: L1
- **Parent Task**: L1_adapter_split
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (六域 mixin 落地; API 面零变化; 2243 + 739 全绿)

## 🎯 本次目标

方案 Step 4-9: 把 semantic_adapter.py 的活代码按 6 域搬进
`src/trace/core/semantic/` mixin 包, 方法名/签名不变, 调用方零改动。

## 🔬 实际结果

**域划分 (62 个方法搬迁, 15 个留在 facade)**:

| mixin 模块 | 方法数 | 行数 | 内容 |
|---|---|---|---|
| `semantic/source_core.py` | 6 | 197 | 源位置/文本/子节点/名字清洗 |
| `semantic/modules.py` | 14 | 713 | module/instance/generate/primitive 导航 |
| `semantic/ports_ifaces.py` | 10 | 413 | 端口/接口/modport |
| `semantic/connections.py` | 4 | 301 | 实例连接/表达式→信号名/索引求值 |
| `semantic/exprs_drivers.py` | 23 | 792 | 赋值/数据声明/驱动/任务函数参数 |
| `semantic/classes.py` | 5 | 248 | class/约束/参数化特化 |
| `semantic/_expr_helpers.py` | — | 396 | 表达式信号抽取 16 处理器 + 折叠 helper (Step 3 产物移出) |
| `semantic/_wrappers.py` | 2 类 | 107 | instance/decl 包装类 (modules 域使用) |
| **`semantic_adapter.py` (facade)** | 15 | **227** | `__init__`/属性/状态 + mixin 组合 + 兼容再导出 |

`class SemanticAdapter(SourceCoreMixin, ModulesMixin, PortsIfacesMixin,
ConnectionsMixin, ExprsDriversMixin, ClassesMixin)` — MRO 正确, 实例 API 不变。

**搬迁过程中修掉的 6 个真实问题 (全部由测试暴露, 非猜测)**:
1. 方法块 dedent 错位 (def 行也被去 4 空格) → 方法变模块级函数 (API 冻结测试立刻红)
2. `...ast_utils` 相对导入深度错 (semantic 包内应为 `..ast_utils`)
3. `.._safe` → 应为 `..._safe` (trace/_safe.py)
4. mixin 缺 `from typing import Callable, Iterator`
5. **方法体内的延迟相对导入** (`from .native_adapter import ...`) 在包内变成
   `trace.core.semantic.native_adapter` → 改为 `..native_adapter`
6. 两处 undefined 名 (`_clean_name_fn` / `logger`+`safe_str`) — 用 AST 扫描
   (builtins + import + 赋值 − 引用) 系统性找出, 而非逐个报错试

**验证 (Step 4-9 gate)**:
| gate | 结果 |
|---|---|
| unit + regression + truth | **2,243 passed** (与拆分前完全一致) |
| cli + integration | **739 passed / 0 failed** |
| API 面冻结 (MRO-wide) | ✅ 65 方法 + 签名 + 3 property 全一致 |
| `check_docs.py` | ✅ |

> 冻结测试口径适配: 方法现定义在 mixin 类中 → 采集改为 **MRO-wide**
> (有效 API 面 = 实例可调用集合, 与拆分前等价); 已在该测试 docstring 说明。

## 💡 关键发现 / 决策

- **安全网价值再次兑现**: 每次脚本化搬迁的破绽 (dedent/导入深度/漏导入) 都由
  "API 冻结测试 + 2243 基线" 在 1-2 分钟内精确暴露 — 937 个失败的根因只是
  2 个 undefined 名 + 1 个延迟导入。
- **AST 静态扫描 > 逐个报错试错**: 用 builtins/import/赋值集合减去引用集合,
  一次找出全部 undefined 名 (否则要跑 6 轮测试套件)。
- **相对导入是搬迁的头号坑**: 显式顶层 import (深度错) 与**方法体内延迟 import**
  (包名遮蔽) 两类都要处理 — 后者只在运行到该分支时才炸, 静态扫描不易发现,
  靠真实套件覆盖 (native_adapter 路径) 才暴出来。
- 结果: 单文件 3,049 → 227 行 facade + 6 个域模块 (最大 792 行), 认知负担与
  并行编辑冲突面大幅下降; 后续 Step 10 (死 API 清理) 可按域逐个进行。
