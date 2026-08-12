# Manual Test Tools

集中放一次性 / ad-hoc 测试工具脚本, 区别于 `sim/tests/unit` (pytest) 和 `sim/tests/integration` (端到端)。

## extract_target.py — 提 SV fixture 的顶层 module instance

**为什么不是 regex?** pyslang 已经 elaborate 完了, 直接问 `root.topInstances` 比正则扫文本更可靠:

| 处理场景 | regex | semantic AST |
|---------|-------|--------------|
| multiline `module foo (\n  param...\n);` | ❌ | ✅ |
| package 里的 module | ❌ | ✅ |
| `module foo #(` 参数语法 | 手工加 | ✅ 自动 |
| `// module foo` 注释 | 手工加 | ✅ 自动 |
| pyslang binary garbage | ❌ | ✅ `safe_str()` |

### Python API

```python
from sim.tests.manual.extract_target import extract_target
target = extract_target(Path('golden_dataflow_26_hier_levels.sv'))
# → 'golden_hier_top'
```

### CLI

```bash
# 单个文件
python3 -m sim.tests.manual.extract_target sim/tests/fixtures/golden_mini/golden_dataflow_26_hier_levels.sv
# → sim/tests/fixtures/golden_mini/golden_dataflow_26_hier_levels.sv: golden_hier_top

# 多个文件
python3 -m sim.tests.manual.extract_target golden_dataflow_*.sv

# 校验模式: 失败返非零 exit code
python3 -m sim.tests.manual.extract_target --check foo.sv bar.sv
```

### 设计决策

- **取最后一个 topInstance** 作为顶层 wrapper — SV 惯例: helper modules 先 declare, top wrapper 最后 instantiate
- **pyslang 编译失败** 让异常向上抛 (不让 fallback 掩盖问题)
- **没有 topInstances** 返 `fix.stem` (防御性 fallback, 不 crash)

## regress_golden_mini.py — case1-28 全量 strict regression

跑 `sim/tests/fixtures/golden_mini/` 下所有 fixture 的 strict 模式检查:

```bash
# 全量 (默认 strict 模式)
python3 -m sim.tests.manual.regress_golden_mini

# 标准模式
python3 -m sim.tests.manual.regress_golden_mini --level standard

# 子集
python3 -m sim.tests.manual.regress_golden_mini --files golden_dataflow_1_op.sv

# 只看失败
python3 -m sim.tests.manual.regress_golden_mini --quiet
```

预期结果: **PASSED: 29 / 29** (含 case12_ternary_complex + case12_ternary_mixed)。

## 何时用

- **改 viz / checker 后**: 跑 `regress_golden_mini.py` 确认没破坏现有 case
- **写新 fixture**: 用 `extract_target.py` 确认 target_module 名称 (避免 regex 错)
- **临时 ad-hoc 测试**: 直接 import 用, 不用建 pytest fixture