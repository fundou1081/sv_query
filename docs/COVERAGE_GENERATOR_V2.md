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

## 10. 未来工作（不在 V2.C 范围）

1. **V2.B 多信号** - 改 `decompose()` 接受多个信号
2. **V2.A.2 AST 完整利用** - 默认走 AST 路径,字符串解析为 fallback
3. **V2.D** - ControlFlowGraph 集成 (走 P1 单独重构)
4. **V3 Z3** - 关键值 bin 求解
5. **from_dict()** - 反序列化(V3+ 评估)
6. **JSON Schema** - 官方 schema 文件(V3+ 评估)

---

## 11. 经验教训 (从 V1)

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

## 12. 实施结果 (V2.C)

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

### Commits
- `243e5d8` docs: V2.C plan
- `8144c79` feat: cycle 12 data models
- `a3ed5da` feat: cycle 13 CLI --json

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

### JSON 字段参考

| 字段 | 类型 | 说明 |
|------|------|------|
| `original_signal` | string | 用户输入 |
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

### 经验教训 (V2.C 新增)
6. **placeholder 兑现**: V1 留的 `--json (TODO)` 是个明确的兑现目标
7. **stdout/stderr 分隔**: `--json` 模式必须静音编译器的 WARNING
8. **异构兼容**: control_blocks 类型未来会变, 提前 3 路兼容
9. **bit_range tuple → list**: JSON spec 不支持 tuple, 必须显式转换

### 下一步
V2.B (多信号同时 decompose), 预计 cycle 14-15
