# Control Coverage Generator V2 实施计划

> 创建时间: 2026-06-02
> 状态: V2.A 基础完成 (cycle 11), V2.C 完成 (cycles 12-13), V2.B 计划中
> 目标版本: V2

---

## 1. 背景与目标

### 1.1 V2 起点

V1 (cycles 1-10) 已完成核心能力,遗留 5 个限制列在
`docs/COVERAGE_GENERATOR_V1.md`。V2 是**纯增量**功能,不走 P0/P1 重构。

### 1.2 V2 子目标优先级

| # | 候选 | 状态 | Cycle |
|---|------|------|-------|
| A | AST 集成增强 (condition_ast) | ✅ 基础完成 (cycle 11) | 11 |
| C | JSON 输出 | ✅ 完成 (cycles 12-13) | 12-13 |
| B | 多信号同时 decompose | ⏳ V2.C 之后 | 14-15 |
| A.2 | AST 完整利用 (替换默认路径) | ⏳ V2.B 之后 | 16+ |
| D | ControlFlowGraph 集成 | ❌ 走 P1 重构 | - |
| E | Z3 集成 | ❌ V3 候选 | - |

**理由**:
- C (JSON) 影响最小,纯增量,1-2 cycle 出货
- B (多信号) 实用价值高,建立在 C 稳定接口之上
- A.2 (AST 完整化) 真正有技术含量,但要先有 C/B 验证
- D 跟 control_vars 已知 bug 绑死,**不混在 V2 增量**

---

## 2. V2.C 范围 (本计划)

### 2.1 目标

实现 `DecompositionResult` 的 JSON 序列化,以及 CLI `--json` 真实输出。
当前 `--json` 是 TODO 占位符,实际降级到 Markdown。

### 2.2 用户故事

```bash
# 当前 (TODO 降级)
$ python run_cli.py coverage suggest -f top.sv --signal top.x --json
JSON output not implemented yet, falling back to markdown
# ... Markdown ...

# V2.C 后
$ python run_cli.py coverage suggest -f top.sv --signal top.x --json
{"original_signal": "top.x", "atomic_signals": [...], "truncated": false, ...}
```

### 2.3 例子

```python
from trace.core.coverage_models import (
    AtomicSignal, DecompositionResult, SourceLocation
)
result = DecompositionResult(
    original_signal="top.x",
    atomic_signals=[
        AtomicSignal(name="a", base_name="a"),
        AtomicSignal(name="b[3:0]", base_name="b", bit_range=(3, 0)),
    ],
    signal_count=2,
)
d = result.to_dict()
# {"original_signal": "top.x", "atomic_signals": [
#   {"name": "a", "base_name": "a", "bit_range": null, ...},
#   {"name": "b[3:0]", "base_name": "b", "bit_range": [3, 0], ...}
# ], "signal_count": 2, ...}
import json
json_str = result.to_json(indent=2)  # valid JSON, pretty printed
```

---

## 3. 需求决策表

| # | 决策点 | 决策 | 理由 |
|---|--------|------|------|
| 1 | 序列化方法 | `to_dict()` + `to_json(indent=2)` | `to_dict()` 便于程序消费,`to_json()` 便于人类/CLI |
| 2 | `to_dict` 嵌套 | 递归展开所有 dataclass (含 SourceLocation) | 用户期望"完整序列化",不要 lazy 字段 |
| 3 | bit_range 序列化 | `tuple` → `list` (JSON 不支持 tuple) | JSON spec |
| 4 | `SourceSnippet.text` | 不序列化(懒加载,运行时无意义) | 序列化 source 太长且无价值 |
| 5 | `EvidenceStep.source` | 不序列化 `SourceSnippet` 对象本身 (None) | 同上 |
| 6 | 错误信息 | `error` 字段为 `null` 当无错 | 标准 JSON 习惯 |
| 7 | 输出格式 | 默认 `indent=2`,可选 `-1` 单行 | 可读性 + 体积灵活 |
| 8 | CLI 退出码 | 保持现状 (`--json` 不影响退出码语义) | 跟 Markdown 一致 |
| 9 | 依赖 | 不引入新依赖,用 stdlib `dataclasses.asdict` + `json` | 轻量 |
| 10 | 默认行为 | CLI 默认还是 Markdown,`--json` 显式切 | 不破坏现有用户 |

---

## 4. 系统设计

### 4.1 新增方法

```python
# coverage_models.py

import json
from dataclasses import asdict, is_dataclass

@dataclass
class SourceLocation:
    # ... 现有字段 ...
    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column": self.column,
        }

@dataclass
class EvidenceStep:
    # ... 现有字段 ...
    def to_dict(self) -> dict:
        return {
            "step_type": self.step_type,
            "description": self.description,
            "from_signal": self.from_signal,
            "to_signals": list(self.to_signals),
            "source": self.source.load_text() if self.source else None,
        }

@dataclass
class AtomicSignal:
    # ... 现有字段 ...
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "base_name": self.base_name,
            "bit_range": list(self.bit_range) if self.bit_range else None,
            "source": self.source.to_dict() if self.source else None,
            "evidence": [e.to_dict() for e in self.evidence],
        }

@dataclass
class DecompositionResult:
    # ... 现有字段 ...
    def to_dict(self) -> dict:
        return {
            "original_signal": self.original_signal,
            "atomic_signals": [a.to_dict() for a in self.atomic_signals],
            "control_blocks": [self._control_block_to_dict(b) for b in self.control_blocks],
            "depth_reached": self.depth_reached,
            "signal_count": self.signal_count,
            "truncated": self.truncated,
            "error": self.error,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def _control_block_to_dict(block) -> dict:
        """控制块可能是 TraceEdge 或 ControlBlock, 兼容两种"""
        if hasattr(block, "effective_condition"):
            return {
                "type": "TraceEdge",
                "src": getattr(block, "src", ""),
                "dst": getattr(block, "dst", ""),
                "condition": getattr(block, "effective_condition", "") or getattr(block, "condition", ""),
                "expression": getattr(block, "expression", ""),
            }
        if hasattr(block, "to_dict"):
            return block.to_dict()
        # Fallback: string repr
        return {"repr": str(block)}
```

### 4.2 CLI 改动

```python
# src/cli/commands/coverage.py
if json_output:
    print(result.to_json(indent=2))
    if result.truncated or result.error:
        raise typer.Exit(code=1)
    return
```

### 4.3 文件改动汇总

| 文件 | 类型 | 行数估计 |
|------|------|----------|
| `src/trace/core/coverage_models.py` | 修改 | +60 (4 个 to_dict + 1 个 to_json) |
| `src/cli/commands/coverage.py` | 修改 | -5 / +10 |
| `sim/tests/unit/test_coverage_generator.py` | 修改 | +80 (新 JSON 测试) |
| **总计** | | **~150 行** |

---

## 5. 复用检查清单

### 5.1 完全复用
- [x] `dataclasses.asdict` - 基础序列化
- [x] `json.dumps` - JSON 编码
- [x] 现有 `DecompositionResult` / `AtomicSignal` / `EvidenceStep` 字段

### 5.2 不复用
- ❌ `pydantic` / `marshmallow` - 增加依赖,不值
- ❌ 反射式的 generic serializer - 过度设计

---

## 6. 关键技术点

### 6.1 tuple → list

JSON spec 不支持 `tuple`,必须显式转换:

```python
"bit_range": list(self.bit_range) if self.bit_range else None
# (3, 0) -> [3, 0]
# None -> None
```

### 6.2 SourceSnippet 懒加载处理

`SourceSnippet.text` 走懒加载,序列化时**不调用** `load_text()`,
避免在 JSON 输出时意外触发文件 IO(可能在 sandboxed 环境)。
如果用户需要源码,可以单独调 `load_text()`。

### 6.3 ControlBlock 异构处理

V1 实现里 `result.control_blocks` 实际存的是 `TraceEdge` 列表
(临时把 edges 当 control_blocks 用)。V2.C 必须**兼容**两种类型:
- `TraceEdge` (现在) - 有 `effective_condition`, `expression`, `src`, `dst`
- `ControlBlock` (未来 D 实现后) - 有 `condition_vars`, `body_stmts` 等

### 6.4 Unicode 安全

用 `ensure_ascii=False`,允许中文字段名/源码位置。

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 嵌套 dataclass 漏字段 | 中 | 中 | 每个 dataclass 显式写 to_dict(),不用 asdict 递归 |
| 控制块类型变更多 | 中 | 中 | `_control_block_to_dict` 兼容 `to_dict()` 和 `effective_condition` 两种 |
| SourceSnippet 触发 IO | 低 | 低 | 序列化时**不调** `load_text()` |
| indent 太大 | 低 | 低 | 提供 `indent=-1` 紧凑模式 |
| 用户期望 round-trip | 低 | 低 | V2.C 不做 from_dict,V3 评估 |

---

## 8. 验收标准

### 8.1 功能验收
- [ ] `result.to_dict()` 返回标准 Python dict
- [ ] `result.to_json()` 返回有效 JSON 字符串
- [ ] `bit_range` 序列化为 list
- [ ] `SourceLocation` 完整序列化
- [ ] `EvidenceStep.evidence` 列表完整
- [ ] `error` 字段为 `null` 当无错
- [ ] CLI `--json` 输出 JSON 不再是 Markdown
- [ ] CLI `--json` 输出含 `original_signal`/`atomic_signals` 等所有字段
- [ ] 跨模块错误时 `error` 字段含错误信息
- [ ] truncated 时 `truncated=true` 且 `atomic_signals` 被截断

### 8.2 质量验收
- [ ] V2.C 后总测试数 +12-15
- [ ] 1322 现有测试仍通过
- [ ] ruff 错误 < 10
- [ ] 不引入新依赖

### 8.3 文档验收
- [ ] `COVERAGE_GENERATOR_V2.md` 更新实施结果
- [ ] `EXAMPLES.md` 加 JSON 用法示例

---

## 9. 实施 Cycle 计划

| Cycle | 内容 | 估计行数 | 估计测试 |
|-------|------|----------|----------|
| 0 | 本计划文档 | 200 | 0 |
| 12 | `to_dict()` + `to_json()` 数据模型 | +60 | +8 |
| 13 | CLI `--json` 真实实现 | +10 | +5 |
| 14+ | (V2.B 多信号) | - | - |
| **合计** | | **~150 行** | **+13** |

---

## 10. V2.B 计划 (多信号同时 decompose)

### 10.1 目标

V1 `decompose()` 只处理 `signals[0]`, 其他信号被默默忽略。V2.B 改为处理所有信号,
合并去重原子信号,union 控制块。

### 10.2 用户场景

```sv
// RTL
if (en) x <= c & d;
if (mode) y <= a | b;
```

```bash
# V1: 只分解 x, 忽略 y
$ python run_cli.py coverage suggest -f top.sv --signals "top.x, top.y"
# 只看 x 的覆盖度

# V2.B: 一起分解
$ python run_cli.py coverage suggest -f top.sv --signals "top.x, top.y"
# 同时看 x 和 y 的覆盖度, 合并去重 (如 a 出现两次会合并 evidence)
```

### 10.3 需求决策

| # | 决策点 | 决策 | 理由 |
|---|--------|------|------|
| 1 | 合并去重键 | atomic.name (含位选) | 同名同位选 = 同一原子 |
| 2 | evidence 合并 | 同名原子证据链追加 | 多信号分解到同一原子时丰富证据 |
| 3 | control_blocks 合并 | 按 (src, dst) 去重 | 同一驱动边不重复 |
| 4 | 跨模块 | 任一信号跨模块 = 错误 | 避免部分结果,简单明确 |
| 5 | original_signal 字段 | 仍为 `", ".join(signals)` | 向后兼容 V2.C 测试 |
| 6 | **新增** original_signals | `list[str]` 字段 | 结构化原始输入 |
| 7 | max_signals 限制 | 对合并后总原子数限制 | 跟 V1 语义一致 |
| 8 | 同信号重复 ("a, a") | 不去重输入,合并时去重 | 零开销,语义清晰 |
| 9 | 空信号列表 | 错误 (跟 V1 一致) | 无明确意义 |
| 10 | 顺序 | 保持输入顺序 | 用户期望可预测 |

### 10.4 系统设计

```python
# coverage_models.py 新增字段
@dataclass
class DecompositionResult:
    original_signal: str = ""           # 保留: ", ".join 输入
    original_signals: list[str] = field(default_factory=list)  # 新增: 结构化
    # ... 其他字段 ...
```

```python
# coverage_generator.py 重构 decompose()
def decompose(self, signals, max_signals=5, max_depth=10):
    result = DecompositionResult(
        original_signal=", ".join(signals),
        original_signals=list(signals),
    )
    if not signals:
        result.error = "No signals provided"
        return result

    all_atomics: list[AtomicSignal] = []
    all_blocks: list[Any] = []
    seen_atomics: set[str] = set()
    seen_blocks: set[tuple] = set()

    for primary in signals:
        # 跨模块检测 - 任一信号跨模块就报错
        if self._is_cross_module(primary):
            result.error = (
                f"信号 {primary} 跨模块, 当前版本不支持. "
                f"请指定顶层模块信号 (如 top.x)."
            )
            return result

        # 复用 V1 逻辑: 收集 cond_edges + atomics
        cond_edges = self._collect_condition_edges(primary)
        primary_atomics: list[AtomicSignal] = []

        for edge in cond_edges:
            cond = edge.effective_condition or edge.condition or ""
            for a in self._parse_expression_to_atomics(cond):
                if a.name not in seen_atomics:
                    seen_atomics.add(a.name)
                    primary_atomics.append(a)
            expr = getattr(edge, "expression", "") or ""
            for a in self._parse_expression_to_atomics(expr):
                if a.name not in seen_atomics:
                    seen_atomics.add(a.name)
                    primary_atomics.append(a)

        # driver 链追踪
        for atomic in list(primary_atomics):
            recurse_id = self._resolve_signal_id(atomic.base_name, primary)
            sub_atomics = self._trace_drivers(
                recurse_id, atomic.bit_range,
                depth=1, max_depth=max_depth, visited=set(),
            )
            for sa in sub_atomics:
                if sa.name not in seen_atomics:
                    seen_atomics.add(sa.name)
                    primary_atomics.append(sa)

        all_atomics.extend(primary_atomics)

        # 合并 control_blocks (按 (src, dst) 去重)
        for edge in cond_edges:
            key = (getattr(edge, "src", ""), getattr(edge, "dst", ""))
            if key not in seen_blocks:
                seen_blocks.add(key)
                all_blocks.append(edge)

    result.atomic_signals = all_atomics
    result.control_blocks = all_blocks
    result.signal_count = len(all_atomics)
    result.depth_reached = max_depth

    # 截断检查
    if len(all_atomics) > max_signals:
        result.atomic_signals = all_atomics[:max_signals]
        result.truncated = True
        result.error = (
            f"Decomposition exceeds max_signals ({max_signals}): "
            f"found {len(all_atomics)} signals"
        )

    return result
```

### 10.5 文件改动

| 文件 | 类型 | 行数估计 |
|------|------|----------|
| `coverage_models.py` | 修改 | +3 (original_signals 字段) |
| `coverage_generator.py` | 修改 | ~50 (重写 decompose 主循环) |
| `test_coverage_generator.py` | 修改 | +120 (cycle 14 8 tests + cycle 15 5 tests) |
| `coverage.py` (CLI) | 修改 | +5 (help 文本 + 验证) |
| **总计** | | **~180 行** |

### 10.6 验收标准

- [ ] 单信号输入与 V1 行为一致 (回归测试不挂)
- [ ] 2+ 信号输入返回所有合并原子 (无丢失)
- [ ] 同名原子 (a) 出现多次, evidence 合并, 总数正确去重
- [ ] control_blocks 按 (src, dst) 去重, 不重复
- [ ] 跨模块信号 → 错误, 其他信号不被处理
- [ ] 同信号重复 ("a, a") 输入不重复, 总数正确
- [ ] 合并后超过 max_signals → truncated + error
- [ ] original_signals 字段存在, 元素顺序匹配输入
- [ ] JSON 输出含 original_signals list
- [ ] CLI `--signals "a, b, c"` 实际分解 3 个
- [ ] 1322 (V1) + 28 (V2.C) + 13 (V2.B) = 1363 测试通过
- [ ] V2.B 新增代码 ruff 干净

### 10.7 Cycle 拆分

| Cycle | 内容 | 估计行数 | 估计测试 |
|-------|------|----------|----------|
| 14 | `decompose()` 多信号合并 + original_signals 字段 | +55 | +8 |
| 15 | CLI `--signals` 验证 + help 文本 | +10 | +5 |
| **合计** | | **~65 行** | **+13** |

### 10.8 经验教训 (预设)

- 合并逻辑要明确去重键,否则 evidence 会重复追加
- original_signals 字段加在末尾保持向后兼容
- 跨模块快速失败,避免半成品结果
- max_signals 在合并后判断,语义跟 V1 一致

---

## 11. 未来工作（不在 V2.C/B 范围） — 移至附录 B

1. **V2.A.2 AST 完整利用** - 默认走 AST 路径,字符串解析为 fallback
2. **V2.D** - ControlFlowGraph 集成 (走 P1 单独重构)
3. **V3 Z3** - 关键值 bin 求解
4. **from_dict()** - 反序列化(V3+ 评估)
5. **JSON Schema** - 官方 schema 文件(V3+ 评估)

---

## 12. 经验教训 (从 V1)

1. **小步快跑**: C 只有 2 个 cycle,容易回滚
2. **优先复用**: 用 `dataclasses.asdict` 思想,显式 `to_dict()` 而非黑魔法
3. **兼容异构**: ControlBlock 类型未来会变,提前兼容
4. **测试先写**: 跟 V1 一样,先红后绿
5. **真实 CLI 测试**: 跑 `run_cli.py coverage suggest --json` 验证实际输出

---

**创建**: 2026-06-02
**更新**: 2026-06-02 (cycle 12-13 完成)
**状态**: V2.C 完成, V2.B 计划中

---

## 13. 实施结果 (V2.C)

### Cycle 12 - 数据模型序列化
- `SourceLocation.to_dict()`: 4 字段
- `EvidenceStep.to_dict()`: 跳过 SourceSnippet 懒加载 (避免 IO)
- `AtomicSignal.to_dict()`: bit_range tuple → list
- `DecompositionResult.to_dict()`: 递归 + control_blocks 异构兼容
- `DecompositionResult.to_json(indent=2)`: ensure_ascii=False
- `_control_block_to_dict`: TraceEdge / ControlBlock / repr fallback

### Cycle 13 - CLI `--json` 实际输出
- 替换 TODO 降级为真实 `result.to_json(indent=2)`
- `--json` 模式下 `UnifiedTracer(log_level="ERROR")` 避免 WARNING 污染 stdout
- help 文本移除 'TODO'

### 测试 & 质量
- 总测试: 1350 (+28 from V1 1322)
- coverage_generator: 103 (V1 75 + cycle 11 7 + cycle 12 21)
- ruff: 干净

### V2.C 使用示例

```bash
# JSON 输出 (取代默认 Markdown)
python run_cli.py coverage suggest -f top.sv --signal top.x --json

# 紧凑模式
python run_cli.py coverage suggest -f top.sv --signal top.x --json | jq .

# 提取原子信号名
python run_cli.py coverage suggest -f top.sv --signal top.x --json | \
  jq -r '.atomic_signals[].name'
```

### JSON 字段参考 (V2.B 增列)

| 字段 | 类型 | 说明 |
|------|------|------|
| `original_signal` | string | 用户输入拼接 (V1 兼容) |
| **`original_signals`** | **array** | **V2.B: 原始信号列表 (结构化)** |
| `atomic_signals[]` | array | 原子信号列表 |
| `atomic_signals[].name` | string | "a" 或 "a[3:0]" |
| `atomic_signals[].base_name` | string | "a" |
| `atomic_signals[].bit_range` | array\|null | [3, 0] 或 null |
| `atomic_signals[].source` | object | 源码位置 |
| `atomic_signals[].evidence[]` | array | 推导链步骤 |
| `control_blocks[]` | array | 涉及的 if/case 块 (异构) |
| `depth_reached` | int | 实际分解深度 |
| `signal_count` | int | 原子信号数量 |
| `truncated` | bool | 是否截断 |
| `error` | string\|null | 错误信息 |

### 经验教训 (V2.C + V2.B 新增)
6. **placeholder 兑现**: V1 留的 `--json (TODO)` 是个明确的兑现目标
7. **stdout/stderr 分隔**: `--json` 模式必须静音编译器的 WARNING
8. **异构兼容**: control_blocks 类型未来会变, 提前 3 路兼容
9. **bit_range tuple → list**: JSON spec 不支持 tuple, 必须显式转换
10. **测试考虑 max_signals 默认值**: 多信号场景下默认 5 容易截断丢失原子, 测试要显式传 max_signals

### 下一步
V2.B (多信号同时 decompose) → cycle 14-15, 预计 +13 测试

---

## 14. 实施结果 (V2.B)

**状态**: ✅ 完成 (cycles 14-15)
**总提交**: 3 个 commit (cycle 0 + 2 feat)

### Cycle 14 - 多信号 decompose + 数据模型字段

**`coverage_models.py`**:
- `DecompositionResult`: 新增 `original_signals: list[str] = field(default_factory=list)` 字段
- `to_dict()`: 包含 `original_signals` (list 序列化)
- 向后兼容: 默认空 list, 不影响 V1 单信号调用

**`coverage_generator.py`**:
- `decompose()` 重构为主循环: 处理 `signals` 中每个信号
- **跨模块检测**: 任一信号跨模块 → 快速失败 (明确错误语义)
- **atomics 去重键**: `atomic.name` (含位选)
- **control_blocks 去重键**: `(src, dst)` pair
- **max_signals 位置**: 合并后判断 (跟 V1 语义一致)
- 新 import: `typing.Any` (用于 `list[Any]` 注释)

### Cycle 15 - CLI `--signals` 集成

**零逻辑改动!** CLI V1 已正确解析 `--signals` 为 list 传入 `decompose()`。
V2.B 内部多信号支持后自动工作。

仅调整:
- `--signals` help 文本提及 V2.B 多信号能力 + 合并去重语义

### 测试结果

- **总测试**: 1367 (+17 from V2.C 1350)
  - cycle 14: +12 (TestMultiSignalDecomposeV2B)
  - cycle 15: +5 (TestCLIMultiSignalsV2B)
- **coverage_generator**: 120 (103 + 12 + 5)
- **ruff**: 干净 (V2.B 新增代码 0 错误)

### Commits
- `4b44e8e` docs: V2.B plan (cycle 0)
- `df9cc33` feat: cycle 14 多信号 decompose
- `df734a0` feat: cycle 15 CLI 集成

### V2.B 使用示例

```bash
# 多信号同时分解 (V2.B 新能力)
python run_cli.py coverage suggest -f top.sv \
  --signals "top.x, top.y" --max-signals 10

# 提取原始信号列表
python run_cli.py coverage suggest -f top.sv \
  --signals "top.x, top.y" --json | jq '.original_signals'
# → ["top.x", "top.y"]

# 同信号重复 (a, a) - 输入保留, 结果去重
python run_cli.py coverage suggest -f top.sv \
  --signals "top.x, top.x" --json | jq '.original_signals, (.atomic_signals | length)'
# → ["top.x", "top.x"]
# → 5   (不是 10)
```

### 关键设计决策

1. **`original_signals: list[str]` 新字段** (而非改 `original_signal: str`):
   - 向后兼容 V2.C 测试
   - 程序化消费可以区分 1 信号 vs 2 信号

2. **跨模块快速失败**:
   - 任一信号跨模块 → 整个 `decompose()` 报错返回
   - 避免半成品结果混淆用户

3. **去重键选择**:
   - atomics: `atomic.name` (含位选) — `a[3:0]` 和 `a` 视为不同原子
   - control_blocks: `(src, dst)` — 同一驱动边不重复

4. **测试陷阱**: `max_signals=5` 默认在多信号场景下容易截断
   - 测试要显式传 `max_signals=10` 或更高
   - 这是 cycle 14 真实 bug 调试中发现的(感谢 TDD!)

### 经验教训 (V2.B 新增)

11. **max_signals 是合并后总限制**: 跟 V1 语义一致, 用户需预期
12. **TDD 救场**: cycle 14 调试时用临时 print 发现是 max_signals 截断
    - 假设 bug 在合并逻辑, 实际在截断
    - TDD 强制显式测试每个 case 反而暴露了截断边界
13. **零 CLI 改动不丢人**: V1 留的 `--signals` 解析已正确, V2.B 内部能力够了自动工作
14. **list[Any] 注释要 import Any**: ruff 严格, type annotation 必须 import 完整

### 下一步
V2.A.2 (AST 完整利用) - 默认走 AST 路径,预计 cycle 16-19

---

## 附录 C. V2.A.2 计划 (AST 完整利用)

### C.1 起点诊断

Cycle 11 添加了 AST 入口但**未接入**:
- `TraceEdge.condition_ast: Any | None = None` 字段已加
- `coverage_generator._extract_condition_atomic(edge, src)` 已实现 (优先 AST, fallback 字符串)
- `coverage_generator._extract_atomics_from_ast(ast_node)` 已实现 (用 SignalExpressionVisitor)
- `_convert_signal_result_to_atomics(sr, ast)` 已实现
- `_is_simple_literal(name)` 已实现

**问题发现**:
- `coverage_generator.decompose()` **未调用** `_extract_condition_atomic`, 仍用 `_parse_expression_to_atomics` 直接解析
- `graph_builder.py` 17+ 处创建 `TraceEdge(condition=...)` 但**全部不填 `condition_ast`**

**结论**: cycle 11 留下了 AST 入口但路径未贯通, V2.A.2 要贯通。

### C.2 目标

让 AST 成为 decompose() 条件提取的**默认路径**。当 `condition_ast` 被填上时走 AST, 当为 None 时回退字符串。

### C.3 风险评估 (用户明确要求小心)

| 阶段 | 改的文件 | 风险 | 保护措施 |
|------|---------|------|----------|
| Cycle 16 | `coverage_generator.py` 仅改 `decompose()` 走 `_extract_condition_atomic` | 🟢 低 | 1322 V1 回归 + 7 个 AST 单元测试 |
| Cycle 17 | `graph_builder.py` 改 if 条件赋值, 加 `condition_ast=` | 🟡 中 | 单点修改 + git diff 逐行核对 + 1367 V2.B 回归 |
| Cycle 18 | 跑 test_data_path.sv 端到端验证 | 🟢 低 | 真实文件回归 + 对比 V2.B 输出一致 |

**关键保护原则**:
1. 每个 cycle 独立 commit, 可独立 `git revert`
2. **Cycle 16 只改 generator.py**, 不会动 graph_builder.py, 如果出问只损失 ~30 行
3. Cycle 16 完成后 **STOP** 给用户看 diff, 经确认才开 cycle 17
4. 始终保留字符串 fallback: 即使 cycle 17 填了 AST, 如果 AST 解析失败, 还走字符串

### C.4 系统设计 (不变 `TraceEdge` 模型)

**Cycle 16 改动** (`coverage_generator.py:decompose`):
```python
# 改前 (现状)
for edge in cond_edges:
    cond = edge.effective_condition or edge.condition or ""
    for a in self._parse_expression_to_atomics(cond):
        ...
    expr = getattr(edge, "expression", "") or ""
    for a in self._parse_expression_to_atomics(expr):
        ...

# 改后
for edge in cond_edges:
    # 1. 条件 - 优先 AST, fallback 字符串
    for a in self._extract_condition_atomic(edge, primary):
        if a.name not in seen_atomics:
            seen_atomics.add(a.name)
            primary_atomics.append(a)
    # 2. driver 表达式 - 保持字符串 (暂未支持 AST)
    expr = getattr(edge, "expression", "") or ""
    for a in self._parse_expression_to_atomics(expr):
        if a.name not in seen_atomics:
            seen_atomics.add(a.name)
            primary_atomics.append(a)
```

**关键不变性**:
- 当 `condition_ast=None` (当前默认): `_extract_condition_atomic` 内部回退到 `_parse_expression_to_atomics(effective_condition or condition)`
- 输出与现状**完全一致** (回归保护)
- driver 表达式保持字符串解析 (暂不改, 减少风险)

**Cycle 17 改动** (`graph_builder.py` 一处):
```python
# 改前 (示例)
TraceEdge(
    src=source, dst=target,
    condition=sig_cond,
    ...
)
# 改后
TraceEdge(
    src=source, dst=target,
    condition=sig_cond,
    condition_ast=<AST_node>,  # 新增: 如果能取到
    ...
)
```

只动 if-condition 场景, 不动 case/ternary 等其他场景, 减少风险面。

### C.5 Cycle 拆分

| Cycle | 内容 | 估计行数 | 估计测试 |
|-------|------|----------|----------|
| 16 | `decompose()` 改走 `_extract_condition_atomic` | ~10 | +6 (AST 路径集成) |
| 17 | `graph_builder.py` 给 1 类 if 条件填 `condition_ast` | ~30 | +3 (集成测试) |
| 18 | 跑 test_data_path.sv 验证 | ~5 | +2 (CLI 验证) |
| **合计** | | **~45 行** | **+11** |

### C.6 验收标准

- [ ] `decompose()` 在 `condition_ast=None` 时与 V2.B 输出完全一致
- [ ] `decompose()` 在 `condition_ast=mock_node` 时走 AST 路径
- [ ] 1322 (V1) + 28 (V2.C) + 17 (V2.B) = 1367 测试全过
- [ ] cycle 17 后 1367 + 11 = 1378 测试全过
- [ ] 跑 test_data_path.sv, JSON 输出含 `condition_ast_used: true` (新增 evidence 字段)
- [ ] ruff 干净 (V2.A.2 新增代码)

### C.7 经验教训 (预设)

- 死代码 (`_extract_condition_atomic` cycle 11 加了没接) 是 cycle 11 的遗憾
- 用户对误删的担忧提示: 改动小一点, review 多一点
- 默认走 AST 但保留 fallback 是兼容性最稳的模式
- 真实数据测试是发现"代码加了没接入"的唯一可靠手段

### C.8 下一步

Cycle 16 → STOP 给用户看 diff → Cycle 17 → Cycle 18


---

## 附录 D. V2.A.2 实施结果 (cycles 16-18)

**状态**: ✅ 完成
**总 commits**: 6 (cycle 0 plan + 5 实施)
**V2.A.2 净代码改动**: 11 行(全部新增, 0 行删除)

### Cycle 16 - 接线 (coverage_generator.py 1 行)
- `decompose()` 改走 `_extract_condition_atomic(edge, primary)`
- `_extract_condition_atomic` 加 1 行: AST 失败时也试字符串
- 6 个集成测试

### Cycle 17a - visitor 存 AST (statement_collector_visitor.py 1 行)
- `visit_conditional_statement` ifTrue 分支的 `new_ctx` 加 `"condition_ast": cond_expr`
- `cond_expr` 已经是 pyslang semantic AST node (line 901/906 拿到)
- 1 个测试: 验证 ctx 含 condition_ast

### Cycle 17b - graph_builder 第 1 个点 (graph_builder.py 1 行)
- line 968 TraceEdge 加 `condition_ast=ctx.get("condition_ast")`
- 2 个测试: AST 填充率 > 0 + 节点是真实 pyslang

### Cycle 17c - graph 挂 adapter (unified_tracer.py 1 行)
- `self._graph._adapter = semantic_adapter`
- 让 SignalExpressionVisitor 在真实数据上能工作
- 2 个测试: graph 含 adapter + 真 SV 文件 ast_extract 出现

### Cycle 17d - 剩余 7 个 ctx-based 点 (graph_builder.py 7 行)
- lines 991, 1019, 1045, 1564, 1610, 1680, 1752 都加 `condition_ast=ctx.get("condition_ast")`
- AST 填充率: 14.9% → 100% (47/47)

### Cycle 18 - CLI 端到端验证
- 2 个 CLI 集成测试
- 跑 `run_cli.py coverage suggest --json` 验证用户能看到 `ast_extract` 证据

### 真实数据最终状态 (test_data_path.sv)

```
$ python run_cli.py coverage suggest -f test_data_path.sv \
    --signal data_path.result --max-signals 10 --json | jq '.atomic_signals[].evidence[].description' | head

"AST extract: rst_n (kind=UnaryOp)"
"AST extract: pipeline_stall (kind=UnaryOp)"
```

→ **V2.A.2 完整利用 AST, 落到用户可见输出**

### 测试 & 质量
- 总测试: **1380** (cycle 0 起点 1373, V2.A.2 净 +7)
- V2.A.2 新增: 12 个测试 (6 + 1 + 2 + 2 + 0 + 2)
- ruff 干净
- 11 行代码, 0 行删除

### 经验教训 (V2.A.2 新增)

15. **code path 就位 ≠ 真实使用**: cycle 11/16 装的代码 100% 正确, 但喂入数据 None
    → 必须验证 data path, 不能只验 code path
16. **adapter 传递**: 真 AST 路径需要 `SignalExpressionVisitor`, 它的入口需要 adapter
    → `_graph._adapter = semantic_adapter` 是联通 code 和 data 的关键
17. **小步可独立回滚**: 4 个文件各 1 行改动, 任何一步出问题都只损失 1 行
    → 之前担心的"小心, 避免误删"通过 5 个 commit 守住
18. **TDD 红→绿 真实暴露问题**: 17c 写测试才发现 graph 缺 adapter, 之前没意识到
    → 端到端测试是发现 wiring 问题的唯一手段
19. **CLI 端到端是最终验证**: 单元测试通过 ≠ 用户能用
    → cycle 18 的 CLI 测试才是 V2.A.2 完整闭环

### 剩余工作 (P1 范围, 不阻塞 V2.A.2 完成)

1. **sig_cond-based 创建点** (7+ 处, graph_builder line 737, 760, 784, 807, 917, 941)
   - 用局部变量 `sig_cond`, 不是 ctx
   - 需 refactor 跟踪 `sig_cond_ast`
   - 估计 1 cycle, ~20 行 (需要新 ctx-style 数据流)
2. **case 语句的 cond_expr 透传** (visitor line 760-781)
   - 当前 case path 的 ctx 也没存 cond_expr
   - 需 visitor 配合改
   - 估计 1 cycle, ~10 行

### 下一步候选

1. **完成 sig_cond + case**: 推到 AST 填充率 100% 包括所有场景 (cycle 17e+, 估计 +30 行)
2. **V2 整体收尾文档**: 写 V2 总结 (V2.A + V2.B + V2.C + V2.A.2)
3. **P1 启动**: graph_builder.py 3054 行拆分 (跟 V2 解耦)

