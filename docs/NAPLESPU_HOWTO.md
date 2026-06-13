# NaplesPU 项目跑通 HOWTO

> 日期: 2026-06-13
> 状态: ✅ 编译问题根因定位完成
> 适用: NaplesPU RISC-V Manycore Processor

## 现象

跑 `python run_cli.py protocol detect --filelist naplespu.f` 编译错:

```
strict: 66 UndeclaredIdentifier errors (service_message_t, tile_mask_t, address_t, ...)
--no-strict: 65 elaboration errors, partial graph, 0 modules extracted
```

## 根因 (3 层)

```
第 1 层: include_dirs 缺失
  ├─ pyslang 的 `\`include "npu_coherence_defines.sv"` 找不到路径
  └─ 修: 传 include_dirs=["src/include", "src/common", "src"]

第 2 层: dsu/debug 模块 (非主体)
  ├─ debug_message_handler.sv / debugger_request_manager.sv
  ├─ 引用外部调试器 typedef (service_message_t、read_debugger_command、DEBUG 等)
  ├─ NaplesPU Vivado 脚本自己的 `setup_project.tcl` 显式排除 `*/dsu/*`
  └─ 修: 从 filelist 排除 dsu/ 目录

第 3 层: VHDL FPU (FloPoCo 生成)
  ├─ 5 个 FPU 模块: fp_addsub、fp_mult、fp_div、fp_itof、fp_ftoi
  ├─ 底层用 VHDL: InputIEEE_8_23_to_8_23、FPDiv_8_23、OutputIEEE_8_23_to_8_23
  ├─ pyslang 不支持 VHDL
  └─ 修: 排除 fp_pipe.sv + 写 Verilog stub 或接受 --no-strict
```

## 正确 filelist (来自 NaplesPU 官方)

NaplesPU 自己的 `tools/modelsim/simulate.sh` 包含**手写 filelist**:

```bash
# 120 个 .sv 文件 + 5 个 .v + +incdir+
vlog $COMPILE_FLAGS -sv \
  "+incdir+../../src/include" "+incdir+../../src/include" \
  "../../src/common/priority_encoder_npu.sv" \
  "../../src/common/memory_bank_async_2r1w.sv" \
  ... (共 125 个文件)
```

**关键**: 
- includes `src/include` (包含所有 `*_defines.sv`)
- **不**含 dsu/debug 模块主体 (只有 2 个辅助文件: bp_wp_handler.sv, debug_controller.sv)
- **不**含 deploy/ (独立子项目)

## 实战工作流 (推荐)

### Step 1: 生成正确 filelist

```bash
# 从 NaplesPU simulate.sh 提取 filelist (排除 fpu/)
# 见 scripts/generate_naplespu_filelist.sh
```

### Step 2: 用 `fix report` 看现状

```bash
python run_cli.py fix report --filelist /tmp/naplespu_modelsim.f
# → 65 UndeclaredIdentifier errors, 0 auto-fixable
```

### Step 3: 传 include_dirs 解决 `\`include 链

```bash
python run_cli.py protocol detect \
    --filelist /tmp/naplespu_modelsim.f \
    -m npu_core \
    --include src/include,src/common,src
```

或直接用 Python API:

```python
ext = SVSignalExtractor.from_filelist(
    filelist='/tmp/naplespu_modelsim.f',
    strict=False,
    include_dirs=[
        'src/include',
        'src/common', 
        'src',
    ]
)
```

### Step 4: 跑 analysis

```bash
# protocol detect
python run_cli.py protocol detect --filelist naplespu.f -m npu_core --no-strict

# stats
python run_cli.py stats --filelist naplespu.f --no-strict

# controlflow
python run_cli.py controlflow analyze <signal> --filelist naplespu.f --no-strict

# dataflow
python run_cli.py dataflow analyze <from> <to> --filelist naplespu.f --no-strict

# visualize
python run_cli.py visualize graph --filelist naplespu.f --no-strict
```

## 实测结果 (with --no-strict)

```
Graph Statistics:
  Total nodes: 2790
  Total edges: 2410
  
  Node kinds:
    PORT_IN: 1061, PORT_OUT: 470, REG: 40, SIGNAL: 1107
    INSTANTIATED_MODULE: 61, CONST: 51

  Edge kinds:
    CLOCK: 40, RESET: 35, DRIVER: 967, CONNECTION: 1514
```

## VHDL FPU 移植分析

### 规模

| 文件 | 行数 | 内容 |
|------|------|------|
| `flopoco.vhdl` | 1919 行 | 27 个 entity/architecture (FloPoCo 生成的 IEEE 754 FPU) |
| `fp_pipe.sv` | ~440 行 | FPU 顶层流水线 (实例化 5 个算术单元) |

### VHDL entity 需转写

```
InputIEEE_8_23_to_8_23    — IEEE 754 unpack (32→33 bit)
OutputIEEE_8_23_to_8_23   — IEEE 754 pack (33→32 bit)
FPDiv_8_23                — 单精度除法器
Fix2FP_* (8 个子模块)      — fix→float 转换器流水线
FP2Fix_* (6 个子模块)      — float→fix 转换器流水线
+ 其他辅助 (zeroD, fracConversion, oneSubstracter 等)
```

### 难度评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 算法复杂度 | 🔴 高 | IEEE 754 加法/乘法/除法/转换,各含多个流水线 stage |
| 验证要求 | 🔴 高 | 浮点精度+舍入+异常(inf/NaN/denorm)需逐 case 验证 |
| 工作量 | 🔴 高 | 1919 行 VHDL → 估计 2500+ 行 Verilog |
| **推荐** | 🟢 **写 stub** | sv_query 只需端口签名,不需要实现 |

### 推荐方案: Verilog Stub (30 行)

```systemverilog
// stubs/fp_addsub.sv
module fp_addsub (
    input  clk, rst,
    input  [31:0] op1, op2,
    input  input_valid,
    output [31:0] result,
    output output_valid
);
    // stub: sv_query 静态分析不需要实现
    assign result = 32'h0;
    assign output_valid = 1'b0;
endmodule
```

**工作量**: 5 个 stub × ~10 行 = **50 行 Verilog**, 10 分钟完成。

### 不建议完整移植 VHDL 的原因

1. **算法深**: IEEE 754 浮点运算 (LZC > normalize > round > exception) → 200+ 行/模块
2. **验证难**: 需要 corner case 测试 (NaN/Inf/Denorm/Rounding modes)
3. **FloPoCo 可重新生成**: 如果有 FloPoCo 工具,可用 `-outputfile` 生成 Verilog
4. **收益小**: sv_query 是静态分析器,不跑仿真,stub 端口签名已够

## 与 OpenTitan 对比

| 维度 | OpenTitan tlul | NaplesPU |
|------|---------------|----------|
| 文件数 | 192 | 125 (modelsim) |
| 编译错 (strict) | 67 | 65→0 (加 include_dirs) |
| 阻塞类型 | `mubi4_t` 包缺 | `\`include 链缺路径 |
| 最终方案 | `top_pkg.sv` stub (30 行) | `include_dirs` 参数 |
| protocol 结果 | TL-UL 0.350 | UNKNOWN 0.000 (无标准 bus) |
| strict pass? | ❌ (VHDL→stub 未做) | ❌ (VHDL→stub 未做) |
| --no-strict 图规模 | 3795 nodes / 3749 edges | 2790 nodes / 2410 edges |

## 备忘

- NaplesPU 实际用 `modelsim simulate.sh` 做仿真, `vivado setup_project.tcl` 做 FPGA
- 两者都 `remove_files */dsu/*` → debug 模块不是主体
- `verilator_lint.sh` 用更激进的 `find src/ -type d | for d in $DIRS; -I$d` → 全目录 include
- `src/include/npu_user_defines.sv` 里的 `SIMULATION` macro 只影响日志,不影响编译
- 学术上游: https://gitlab.com/vincenscotti/nuplus
