# P165.3 alternative: independent Verilator oracle

**日期**: 2026-11-12
**状态**: ✅ 第一块（P165.3.1）

## 1. 为什么不用 OpenTitan 历史

本机 OpenTitan 是浅克隆（`rev-list --count HEAD = 1`），无法诚实回溯真实 bug commit。
继续从它构造 fault set 会把“一次性的 worker 观察”当成外部效度。

## 2. 替代方法

使用 **Verilator 5.048** 作为独立第二 elaborator：

```text
sv_query = pyslang + 结构查询
Verilator = 独立 parser/elaborator
```

它不依赖 OpenTitan 历史、Docker 或 git clone；检查的是**候选 RTL/filelist 是否真的可 elaborate**，
并可与 sv_query 的查询结果做差分。

工具：

```text
tools/agent/verilator_oracle.py
```

命令：

```bash
python3 tools/agent/verilator_oracle.py \
  --file sim/test_simple.sv --top top --json
```

## 3. 实测

```text
sim/test_simple.sv         ok=True errors=0
sim/tests/fixtures/arch_pair.sv  ok=True errors=0
openrtl/picorv32/picorv32.v      ok=True errors=0 warnings=1
```

P165.4 的 UART/I2C/SPI 候选 filelist 也用同一 oracle 复核：

```text
UART      ok=True errors=0 warnings=4
I2C       ok=True errors=0 warnings=49
SPI_HOST  ok=True errors=0 warnings=17
```

这独立于 pyslang 的 elaboration，是比“自己生成 filelist 自己验证”更强的证据。

## 4. 边界

- Verilator lint 通过 ≠ 每个 sv_query 查询语义正确；
- 它不能替代 fault set / mutation；
- 下一步 P165.3.2：在**独立 oracle**下做 mutation fault injection：
  - 从真实 RTL 生成可控 mutation（改驱动/改条件/删连接）；
  - Verilator 证明 mutant 可 elaborate；
  - sv_query 的 ground truth 由 mutation diff 定义；
  - 统计 false-confident，而不是把自撰 expected 当规格。

## 5. 测试

```text
sim/tests/unit/test_verilator_oracle.py
  1 passed (or skip if verilator absent)
```
