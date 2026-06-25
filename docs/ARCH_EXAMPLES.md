# Arch 命令实战案例

> arch v2 在真实开源项目上的运行结果. **核心**: filelist 必须**完整**含 typedef headers + 所有 nested modules, 否则 elaboration 失败, nested instances 拿不到.

## 关键: 完整 filelist

`extract_module` 走 pyslang AST. 如果某个 module 引用了 typedef/module 没在 filelist, elaboration 失败 → 该 module 的 nested instances 拿不到.

**经验**:
- ✅ Top module 放最前
- ✅ 所有 `.svh` typedef header 加进去 (用 `find ... -name "*.svh"`)
- ✅ 所有 nested module definitions 加进去 (recursive find)
- ❌ 不要只 include 顶层 + 几个 module

---

## 1. Google CoralNPU (RISC-V NPU) — 28 instances, 4 层 ✅

**项目**: https://github.com/google-coral/coralnpu (Google Coral NPU, 2025)
**架构**: 32-bit RISC-V + vector (RVV) + matrix + scalar processors

```bash
# 完整 filelist (70+ files: 9 .svh + 51 .sv)
+incdir+.../hdl/verilog
+incdir+.../hdl/verilog/rvv/design
+incdir+.../hdl/verilog/rvv/inc
+incdir+.../hdl/verilog/rvv/sve
# Top
.../RvvCore.sv
# All headers
find .../rvv/inc -name "*.svh"
# All sources
find .../rvv/design -name "*.sv" | grep -v "_tb.sv"

# Run
python run_cli.py arch --filelist=coralnpu.f -t RvvCore -d 10 \
    --cluster-by-type --max-nodes 50 --format svg -o coralnpu_arch.svg
```

**Summary 输出**:
```
📐 Project Architecture: RvvCore
============================================================
Total instances:  28
Hierarchy depth:  4 levels
Port connections: 0 (cross-module)

Top module types:
  RvvFrontEnd                                 1  █
  Aligner                                     1  █
  rvv_backend                                 1  █
  rvv_backend_decode                          1  █
  rvv_backend_decode_de2                      1  █
  rvv_backend_decode_unit_de2                1  █
  rvv_backend_decode_unit_lsu_de2            1  █
  rvv_backend_decode_unit_ari_de2            1  █
  rvv_backend_decode_ctrl                     1  █
  rvv_backend_dispatch                        1  █
  rvv_backend_dispatch_structure_hazard       1  █
  rvv_backend_dispatch_operand                1  █
  rvv_backend_dispatch_ctrl                   1  █
  rvv_backend_alu                             1  █
  rvv_backend_alu_unit                        1  █
  rvv_backend_alu_unit_addsub                 1  █
  rvv_backend_alu_unit_shift                  1  █
  rvv_backend_alu_unit_mask                   1  █
  rvv_backend_alu_unit_other                  1  █
  ... (更多)
```

**架构解读**:
```
RvvCore (顶层 RVV 处理器核)
├── RvvFrontEnd (指令前端, 深度 1)
│   └── Aligner (指令对齐器, 深度 2)
└── rvv_backend (后端执行, 深度 1)
    ├── rvv_backend_decode (解码, 深度 2)
    │   ├── rvv_backend_decode_unit_de2 (深度 3)
    │   ├── rvv_backend_decode_unit_lsu_de2 (深度 3)
    │   └── ...
    ├── rvv_backend_dispatch (分发, 深度 2)
    │   ├── rvv_backend_dispatch_structure_hazard (深度 3)
    │   └── ...
    └── rvv_backend_alu (ALU, 深度 2)
        ├── rvv_backend_alu_unit (深度 3)
        │   ├── rvv_backend_alu_unit_addsub (深度 4)
        │   ├── rvv_backend_alu_unit_shift (深度 4)
        │   └── ...
```

**SVG**: 2479×544 pt, 47 KB (SVG) / 267 KB (PNG). **真实** CoralNPU 架构图.

---

## 2. OpenTitan ascon (crypto accelerator) — 2 instances ⚠️

**项目**: lowRISC/opentitan
**问题**: OpenTitan 多包依赖链复杂 (prim_alert_pkg → prim_util_pkg → prim_math_pkg),
ascon 需要 `prim_pulse_sync` 等深层 module, filelist 难凑齐.

```bash
# 部分 filelist (11 files)
python run_cli.py arch --filelist=ascon.f -t ascon -d 3 --summary

# 输出: 仅 2 instances (ascon_reg_top + ascon_core, 都是直接子模块)
```

**架构解读**:
- 顶层只有 2 个直接子模块 (reg_top + core)
- reg_top 内部需要 `prim_reg_pkg`, `tlul_pkg` 等 chain packages
- 完整 filelist 需要整个 OpenTitan tree (200+ files)

**建议**: 用 OpenTitan 自带 `data/top_earlgrey.f` filelist 跑完整 tree.

---

## 3. PicoRV32_axi (RISC-V CPU wrapper) — 2 instances ✅

**项目**: YosysHQ/picorv32
**架构**: 简单 wrapper (2 个直接子模块)

```bash
python run_cli.py arch -f picorv32.v -t picorv32_axi -d 2 --cluster-by-type
```

**架构解读**:
- `picorv32_axi` 是 CPU 顶层 wrapper
- 2 个直接子模块: `axi_adapter` (AXI 协议转换) + `picorv32_core` (CPU 核心)

---

## 4. Filelist 模板 (新建项目时)

```bash
# Template: full recursive filelist for a SystemVerilog project
PROJECT_ROOT=/path/to/project

cat > myproject.f << EOF
+incdir+$PROJECT_ROOT/rtl
+incdir+$PROJECT_ROOT/include
# Top first
$PROJECT_ROOT/rtl/top.sv
# All headers (typedef + package)
find $PROJECT_ROOT/include -name "*.svh" -o -name "*.pkg.sv"
# All sources
find $PROJECT_ROOT/rtl -name "*.sv" | grep -v "_tb.sv"
EOF
```

---

## 5. 实测结果对比

| 项目 | Filelist files | Instances | Hierarchy depth | SVG size |
|------|----------------|-----------|------------------|----------|
| **CoralNPU** (完整) | 60 (51 .sv + 9 .svh) | **28** | **4** | 47 KB |
| **OpenTitan ascon** (部分) | 11 | 2 | 1 | 4 KB |
| **PicoRV32_axi** | 1 | 2 | 1 | 4 KB |

**关键 takeaway**: filelist 完整性直接决定 arch 输出深度. CoralNPU 完整 filelist 抽出 28 instances / 4 层, 部分 filelist 只有 2 instances / 1 层.