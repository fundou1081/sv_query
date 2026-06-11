# NaplesPU 项目跑通测试 - Issue 和改进建议

## 测试时间
2026-06-11

## 测试对象
- **目标项目**: [NaplesPU](https://github.com/AlessandroCilardo/NaplesPU) (SystemVerilog 实现的 manycore 加速器)
- **位置**: `~/my_dv_proj/NaplesPU/`
- **规模**: 148 个 `.sv`/`.v` 文件,40,006 行代码,SystemVerilog RTL
- **已抓取资源**:
  - `NaplesPU/` 主仓 (SystemVerilog RTL, 3.0MB, 浅克隆)
  - `NaplesPU-toolchain/` LLVM 改写 (549MB, zip 下载后 git init)
  - `docs/` 抓取官方 MediaWiki 文档 8 页 (168KB)

## 测试 sv_query HEAD
`2d7c225 docs+scripts: OpenTitan 项目跑通 HOWTO + 一键生成脚本`

---

## Issue 状态总览

| Issue | 严重度 | 描述 | 状态 |
|-------|--------|------|------|
| **Issue 17** | 🔴 P0 | `snapshot save` 跨文件 elaboration 失败时抛 `CompilationError` 未被捕获,直接 crash | **待修复** |
| **Issue 18** | 🔴 P0 | 大部分命令不支持 `--filelist`(只 trace/handshake/backpressure 支持),项目级分析无路可走 | **待修复** |
| **Issue 19** | 🟡 P1 | `trace fanout/fanin` API 简化:只看 DRIVER/CONNECTION 边,不含 CLOCK/RESET,跟其他命令图不一致 | **待修复** |
| **Issue 20** | 🟡 P1 | `dataflow analyze` 错误信息不友好 — 报 "not in digraph" 不告诉用户需 hierarchical name (`module.signal`) | **待修复** |
| **Issue 21** | 🟡 P2 | `controlflow` 矛盾条件检测把 if/else 互斥分支 (`reset` vs `!reset`) 误报为矛盾 | **已知限制** |
| **Issue 22** | 🟡 P2 | `stats` 跨文件 elaboration 失败时不输出 partial result,直接 exit 1 | **待修复** |

---

## 改进建议 (按优先级)

### Req-9 [P0]: 所有命令统一支持 `--filelist`

**现状**: 只有 `trace fanin/fanout/impact`、`handshake scan/analyze/pair`、`backpressure analyze` 支持 `--filelist`。

**缺失** (10 个命令): `stats`、`risk analyze`、`coverage suggest`、`dataflow analyze`、`controlflow analyze`、`timing analyze`、`sva extract`、`cdc analyze`、`verify gap`、`visualize graph`、`snapshot save`

**影响**: 想做项目级分析时,80% 的命令不可用。

**建议方案**:
- 在 `UnifiedTracer.__init__` 加 `filelist: str | None = None` 参数
- 解析 `.f`/`.fl` 文件,把全部源文件读进 `sources: dict[file_path, source]`
- 同时保留 `--file` 单文件模式(向后兼容)
- 参考 OpenTitan HOWTO 的 filelist 实践 (`docs/OPENTITAN_HOWTO.md`)

### Req-10 [P0]: elaboration 错误优雅处理

**现状**: 编译报错时直接 `raise CompilationError` 给用户看 Python traceback。

**建议方案**:
```python
# 当前 (src/trace/core/compiler.py:279)
else:
    raise CompilationError(f"Elaboration errors:\n{report}") from None

# 建议
else:
    if self._strict_mode:
        raise CompilationError(f"Elaboration errors:\n{report}") from None
    else:
        # 走 partial graph fallback
        print(f"[WARNING] {len(errors)} elaboration error(s), continuing in non-strict mode", file=sys.stderr)
        # 继续 _do_compile,失败的节点标 is_valid=False
```

- `snapshot save` 默认 strict (要求全编译通过才存)
- `stats`/`risk`/`visualize` 默认 non-strict (存部分图,失败节点标红)
- 加 `--strict` flag 强制严格模式

### Req-11 [P1]: dataflow analyze 错误信息加 hint

**现状**:
```
$ run_cli.py dataflow analyze data_i data_o --file synchronizer.sv
Error: The node data_o is not in the digraph.
Traceback (most recent call last):
  ...
networkx.exception.NetworkXError: The node data_o is not in the digraph.
```

**建议**:
```python
# 当前 (src/trace/core/graph/dataflow.py:660)
if to_signal not in self.graph.nodes():
    raise NetworkXError(f"The node {to_signal} is not in the digraph.")

# 建议
if to_signal not in self.graph.nodes():
    available_signals = sorted(self.graph.nodes())[:10]
    raise ValueError(
        f"Signal '{to_signal}' not found in graph.\n"
        f"Hint: signal name should be hierarchical, e.g. '{module_name}.{to_signal}'\n"
        f"Available signals: {available_signals}..."
    )
```

同时把 NetworkXError 包装成 CLI 友好错误,不暴露 Python traceback。

### Req-12 [P1]: trace API 文档化并对齐 visualize

**现状**:
- `trace fanout clk` 在 synchronizer.sv 上返回 "no loads" (因为 clk 只在 sensitivity list)
- 但 `visualize graph` 能正确显示 `clk → sync0/sync1/data_o` (CLOCK 边,虚线)

**建议**:
- 在 `trace fanin/fanout` help 文本加注:
  > "Only tracks DRIVER and CONNECTION edges. Sensitivity list (CLOCK/RESET) and conditional control (CONTROL) are excluded. For complete view, use `visualize graph`."
- 加 `--include-clock` / `--include-reset` / `--include-control` flag
- 把 `risk`/`visualize`/`timing` 用的"完整图"作为单一图源,`trace` 加参数决定过滤哪些边

### Req-13 [P2]: controlflow 矛盾条件加 if/else 互斥判断

**现状**:
```
when reset: synchronizer.clk → synchronizer.sync0
when !reset: synchronizer.clk → synchronizer.sync0
⚠️  矛盾条件检测: reset vs !reset
```

**误报原因**: if/else 分支被当成"两个独立的 condition",实际是互斥的合法分支。

**建议方案**:
- 在 `controlflow analyzer` 加 `exclusive_conditions: dict[signal, set[conditions]]` 表
- 对每个 always 块的 if/else 分支,标记 conditions 为 exclusive
- 矛盾检测只在同一 always 块的 if 分支 + 同 always 块的 else 分支之间豁免
- 输出改成:
  ```
  [1] synchronizer.sync0
    if reset: clk → sync0, RESET_STATE → sync0
    else (!reset): clk → sync0, data_i → sync0
  ```

### Req-14 [P2]: stats 跨文件失败时输出 partial result

**现状**: `stats -f tile_ht.sv` 报 65 errors 后直接 exit 1,没有图数据。

**建议方案**:
- 跟 Req-10 配合,默认走 non-strict mode
- 输出 partial graph stats + warning 列表
- 加 `--strict` flag 保持当前行为

---

## NaplesPU 代码本身的真实问题 (供参考,非 sv_query bug)

NaplesPU 写得很"研究级",sv_query parser 抓到 65 个 elaboration errors,真实反映了代码风格问题。

| # | 类型 | 数量 | 示例文件 | 表现 |
|---|------|------|----------|------|
| A | MissingTimeScale | 10+ | `npu_core_logger.sv`, `core_interface.sv`, `debug_*.sv`, `uart_*.sv`, `synchronizer.sv` | 这些文件没 `` `timescale`` directive,仿真时序可能不对 |
| B | UndeclaredIdentifier | 30+ | `npu_*_defines.sv` 里反向引用 `tile_id_t`, `tile_mask_t`, `address_t`, `thread_id_t` 等 | parser 不能正向解析 typedef 依赖 |
| C | $clog2 缺参数 | 10+ | `npu_defines.sv:100: typedef logic [$clog2(`THREAD_NUMB) - 1 : 0] thread_id_t;` | $clog2 是系统函数,sv_query parser 当普通函数 |
| D | CaseTypeMismatch | 5 | `cc_protocol_rom.sv` 的 `case` 表达式是 enum 但 item 是 `4'd4` 数字 | 实际是合法 enum cast,sv_query 类型推断过严 |
| E | DuplicateDefinition | 1 | 同名 typedef/packgage 重复 | 实际可能是 include 顺序问题 |
| F | EmptyMember | 1 | typedef struct 含空成员 | 实际可能是条件编译空体 |

**给 NaplesPU 项目的修复建议** (非 sv_query 范畴):
- 加 `` `timescale 1ns/1ps`` 到所有 module 文件
- 重新组织 typedef 顺序(基础类型先,衍生类型后)
- 宏里避免在 `$clog2` 等系统函数中嵌套宏
- case 用 `unique case` 强化,或者把 enum 成员写完整

---

## 测试验证结果

### ✅ 在 synchronizer.sv (完全自包含 leaf module) 上能跑的命令

| 命令 | 结果 |
|------|------|
| `stats -f src/deploy/uart/synchronizer.sv` | 7 节点 (3 PORT_IN + 3 REG + 1 SIGNAL), 12 边 (3 CLOCK + 3 RESET + 6 DRIVER) |
| `search "npu_core" -f npu_system.sv` | 找到 4 个匹配,带行号和上下文 |
| `trace fanin clk -f synchronizer.sv` | "no drivers" (正确,clk 是 input) |
| `trace fanout sync0 -f synchronizer.sv` | **"no loads"** (Bug 19: should show sync0 → sync1) |
| `risk analyze -f synchronizer.sv` | 完整报告,3 CRITICAL + 1 MEDIUM, fan_in/fan_out 正确 |
| `coverage suggest -s sync0 -f synchronizer.sv` | "无原子信号可生成" (1 bit 寄存器,合理) |
| `cdc analyze -f synchronizer.sv` | 1 时钟域, 0 CDC 路径 (单时钟域,正确) |
| `sva extract -f synchronizer.sv` | 0 sequences/properties/assertions (无 SVA,合理) |
| `dataflow analyze synchronizer.data_i synchronizer.data_o -f synchronizer.sv` | 1 path, depth=3, sync0 → sync1 中间,条件 `!reset` |
| `controlflow analyze synchronizer.sync0 -f synchronizer.sv` | 4 conditional drivers, 误报 2 个 "矛盾" |
| `timing analyze -f synchronizer.sv` | 3 关键路径, depth 3/2/1 |
| `verify gap -f synchronizer.sv` | 3 高风险缺口 (sync0/sync1/data_o, 都无 SVA/Cov) |
| `visualize graph -f synchronizer.sv --dot /tmp/sync.dot` | 35 行 DOT,完整显示 CLOCK/RESET/DRIVER 边 |

### ❌ 跑失败/崩的命令

| 命令 | 触发 | 错误 |
|------|------|------|
| `snapshot save .` (NaplesPU 全项目) | 跨 148 文件 elaboration | 65 errors, exit 1, 部分图无法构建 |
| `stats -f src/deploy/uart/uart.sv` | 实例化 `uart_transmit`/`uart_receive`/`sync_fifo` 未 include | `CompilationError` 直接 crash + Python traceback |
| `stats -f src/mc/tile/tile_ht.sv` | 实例化 `l1d_cache`/`router`/`directory_controller` 等 7+ 子模块 | 65 errors, exit 1, no partial result |
| `dataflow analyze data_i data_o` (裸信号名) | 应要求 hierarchical name | `NetworkXError: data_o is not in the digraph` (误导) |

### ⚠️ 误报/不准确

| 命令 | 触发 | 误报 |
|------|------|------|
| `controlflow analyze synchronizer.sync0` | if/else 分支的 `reset` vs `!reset` | 报"矛盾条件" 2 次 (if/else 是合法互斥) |
| `trace fanout clk` | sensitivity list 引用 | "no loads" (实际 always_ff 用 clk,visualize 正确) |
| `stats` 的 `synchronizer.sync0` | 内部 reg | risk/type 标 "?" (不能识别 always_ff 里的 reg 类型细节) |

---

## 临时绕行方案 (在 Req-9/10 修复前)

1. **想跑项目级分析** → 必须先用 `tools/test.sh`/`modelsim` 跑 Vivado/Questa 确认 RTL elaboration OK,然后改 sv_query 加 filelist 支持
2. **想跑单文件** → 挑**完全自包含**的 leaf module (无 instance 子模块),如 `synchronizer.sv`、`deserializer.sv` 等 `src/common/` 下的简单模块
3. **想看完整信号图** → 用 `visualize graph --dot` 而不是 `trace fanout`
4. **dataflow 要用 hierarchical name** → `module.signal` 格式,如 `synchronizer.data_o` 而非 `data_o`

---

## 测试日志

测试时的完整命令序列已记录在 OpenClaw workspace `memory/2026-06-11.md`。
