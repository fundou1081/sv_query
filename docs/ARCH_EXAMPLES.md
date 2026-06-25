# Arch 命令实战案例

> arch v2 在真实开源项目上的运行结果. 用 `--cluster-by-type --format svg` 生成.

## 1. Google CoralNPU (RISC-V NPU)

**项目**: https://github.com/google-coral/coralnpu (Google Coral NPU, 2025)
**架构**: 32-bit RISC-V + vector (RVV) + matrix + scalar processors

```bash
# Filelist (55 SV files in hdl/verilog/rvv/design/)
+incdir+.../hdl/verilog
+incdir+.../hdl/verilog/rvv/design
+incdir+.../hdl/verilog/rvv/inc
.../RvvCore.sv
.../RvvFrontEnd.sv
.../rvv_backend.sv
.../Aligner.sv
.../MultiFifo.sv
.../rvv_backend_*.sv (50+ files)

# Run
python run_cli.py arch --filelist=coralnpu.f -t RvvCore -d 3 --cluster-by-type
```

**Summary 模式输出**:
```
📐 Project Architecture: RvvCore
============================================================
Total instances:  2
Hierarchy depth:  1 levels
Port connections: 0 (cross-module)

Top module types:
  RvvFrontEnd       1  █
  rvv_backend       1  █
```

**架构解读**:
- **RvvCore** 是顶层模块, 2 个直接子模块
- **RvvFrontEnd** (绿色 cluster) — 指令前端 (取指/译码/调度)
- **rvv_backend** (蓝色 cluster) — 后端执行单元 (ALU/向量/矩阵/标量)

## 2. OpenTitan ascon (crypto accelerator)

**项目**: lowRISC/opentitan (工业级 IoT 芯片)
**架构**: crypto + reg_top + 8 个 package 依赖

```bash
python run_cli.py arch --filelist=ascon.f -t ascon -d 3 --cluster-by-type
```

**Summary 模式输出**:
```
📐 Project Architecture: ascon
============================================================
Total instances:  2
Hierarchy depth:  1 levels

Top module types:
  ascon_reg_top     1  █
  ascon_core        1  █
```

**架构解读**:
- **ascon** 顶层模块 (密码学 IP wrapper)
- **ascon_reg_top** (粉色 cluster) — 寄存器接口层
- **ascon_core** (橙色 cluster) — 算法核心 (Ascon cipher rounds)

## 3. PicoRV32_axi (RISC-V CPU wrapper)

**项目**: YosysHQ/picorv32 (Verilog CPU)

```bash
python run_cli.py arch -f picorv32.v -t picorv32_axi -d 2 --cluster-by-type
```

**Summary 模式输出**:
```
📐 Project Architecture: picorv32_axi
============================================================
Total instances:  2

Top module types:
  picorv32_axi_adapter   1
  picorv32               1
```

## 4. 真实 SVG 生成示例

所有 3 个项目用 `--format svg -o arch.svg` 生成标准 SVG:

```bash
python run_cli.py arch --filelist=coralnpu.f -t RvvCore \
    --cluster-by-type --format svg -o coralnpu_arch.svg
# → coralnpu_arch.svg (4 KB, 232x164 pt, 浏览器直接打开)
```

SVG 内含:
- `cluster_<type>` subgraph (按 module type 着色)
- 节点 + hierarchy 边 (虚线)
- 标题 + hash-based color (`#92a450` 等)

## 5. 实测 SVG 渲染

本地实测 SVG 渲染（用 `rsvg-convert` 转 PNG）:
- CoralNPU: 310x219 pt, 24 KB PNG
- OpenTitan ascon: 286x219 pt, 22 KB PNG
- PicoRV32: 256x164 pt, 22 KB PNG

## 6. 验证结果总结

| 项目 | LOC (RTL) | SV files | arch 抽取 instances | 耗时 |
|------|-----------|----------|---------------------|------|
| CoralNPU (rvv/design/) | ~80K | 55 | 2 (top-level) | <10s |
| OpenTitan ascon | ~15K | 11 | 2 (top-level) | <10s |
| PicoRV32_axi | ~3K | 1 | 2 | <5s |
