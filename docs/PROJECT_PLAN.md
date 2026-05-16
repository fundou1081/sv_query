# 开源 RTL 验证问题生成计划

> 更新日期: 2026-05-15
> 排除: Chisel 项目 (BOOM, XiangShan, rocket-chip)
> 新增: Ethernet/WiFi 通信类项目

---

## 计划总览

### ✅ 已完成

| # | 项目 | 问题数 | 说明 |
|---|------|--------|------|
| 1 | **OpenTitan** (10 模块) | 176 题 | 安全 MCU |

### 🏃 阶段 1: 小型模块化（入门）

| # | 项目 | 规模 | 难度 | 预计题数 | 状态 |
|---|------|------|------|----------|------|
| 2 | **verilog-axi** | ~10K 行，59 文件 | ★★☆☆☆ | 32 | 🏃 开始 |
| 3 | **clacc** | ~2K 行，20 文件 | ★★☆☆☆ | 16 | ⏳ 待做 |

### 阶段 2: 通信/协议类

| # | 项目 | 规模 | 难度 | 预计题数 | 状态 |
|---|------|------|------|----------|------|
| 4 | **verilog-ethernet** | ~36K 行，98 文件 | ★★★☆☆ | 24 | ⏳ 待做 |
| 5 | **verilog-pcie** | ~3K 行，25 文件 | ★★★☆☆ | 16 | ⏳ 待做 |

### 阶段 3: 中型复杂

| # | 项目 | 规模 | 难度 | 预计题数 | 状态 |
|---|------|------|------|----------|------|
| 6 | **Mayoiuta** | ~10K 行 | ★★★☆☆ | 16 | ⏳ 待做 |
| 7 | **CVA6** | ~20K 行 | ★★★☆☆ | 32 | ⏳ 待做 |
| 8 | **ProNoC** | ~30K 行，446 文件 | ★★★☆☆ | 24 | ⏳ 待做 |
| 9 | **Vortex** | 中型 GPU | ★★★☆☆ | 24 | ⏳ 待做 |

### 阶段 4: 超大型挑战

| # | 项目 | 规模 | 难度 | 预计题数 | 状态 |
|---|------|------|------|----------|------|
| 10 | **NVDLA** | **811K 行**，266 文件 | ★★★★★ | 48 | ⏳ 待做 |

---

## 已完成项目

| # | 项目 | 问题数 | 状态 |
|---|------|--------|------|
| 1 | **OpenTitan** (10 模块) | 176 题 | ✅ 完成 |

---

## 最终预计总量

```
已完成: 176 题 (OpenTitan)
阶段 1: 48 题 (verilog-axi + clacc)
阶段 2: 40 题 (verilog-ethernet + verilog-pcie)
阶段 3: 96 题 (Mayoiuta + CVA6 + ProNoC + Vortex)
阶段 4: 48 题 (NVDLA)
---
合计: ~408 题
```

---

## 项目本地路径

### 🖥️ CPU/处理器

| 项目 | 本地路径 |
|------|----------|
| OpenTitan | `~/my_dv_proj/opentitan/` |
| CVA6 | `~/my_dv_proj/cva6/` |

### 🎮 GPU/NPU/AI加速器

| 项目 | 本地路径 |
|------|----------|
| NVDLA | `~/my_dv_proj/hw/` |
| Vortex | `~/my_dv_proj/vortex/` |
| Mayoiuta | `~/my_dv_proj/Mayoiuta/` |
| clacc | `~/my_dv_proj/clacc/` |

### 🔗 互联/协议

| 项目 | 本地路径 |
|------|----------|
| verilog-axi | `~/my_dv_proj/verilog-axi/` |
| ProNoC | `~/my_dv_proj/ProNoC/` |

### 📡 通信类

| 项目 | 本地路径 | 说明 |
|------|----------|------|
| **verilog-ethernet** | `~/my_dv_proj/verilog-ethernet/` | 10G/25G/100G Ethernet IP |
| **verilog-pcie** | `~/my_dv_proj/verilog-pcie/` | PCIe DMA 引擎 |
| openwifi | `~/my_dv_proj/openwifi/` | WiFi 系统（驱动+FPGA）|

---

## 问题结构（每项目）

每项目 16-48 道题，分 4 阶段：

| 阶段 | 维度 | 问题类型 |
|------|------|----------|
| Phase 1 | 基础 | 协议解析、信号定义 |
| Phase 2 | 中等 | 数据转换、路由路径 |
| Phase 3 | 刁钻 | 边界条件、竞争冒险 |
| Phase 4 | 真实场景 | 溯源分析、故障诊断 |

---

## 输出目录结构

```
sv_query/docs/
├── README.md                    # 总览
├── PROJECT_PLAN.md              # 本文件
├── opentitan实战/               # ✅ 已完成 (176 题)
│
├── verilog-axi实战/             # 🏃 进行中
│   ├── VERIFICATION_QUESTIONS.md
│   └── results/ANSWERS.md
│
├── clacc实战/                   # ⏳ 待做
├── verilog-ethernet实战/
├── verilog-pcie实战/
├── mayoiuta实战/
├── cva6实战/
├── pronoc实战/
├── vortex实战/
└── nvdla实战/
```

---

## 下一步

从 **verilog-axi** 开始生成验证问题