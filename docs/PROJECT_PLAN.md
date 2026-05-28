# 开源 RTL 验证问题生成计划

> 更新日期: 2026-05-23
> 状态: 测试框架已稳定 (996 passed, 0 failed)

---

## 项目进度总览

| # | 项目 | 方向 | 本地路径 | 状态 | 问题数 |
|---|------|------|----------|------|--------|
| 1 | **OpenTitan** | 安全 MCU | `~/my_dv_proj/opentitan/` | ✅ 完成 | 176 题 |
| 2 | **verilog-axi** | AXI 协议 | `~/my_dv_proj/verilog-axi/` | 🔄 进行中 | 32 |
| 3 | **clacc** | NPU (Eyeriss-like) | `~/my_dv_proj/clacc/` | ⏳ 待做 | 16 |
| 4 | **verilog-ethernet** | Ethernet | `~/my_dv_proj/verilog-ethernet/` | ⏳ 待做 | 24 |
| 5 | **verilog-pcie** | PCIe | `~/my_dv_proj/verilog-pcie/` | ⏳ 待做 | 16 |
| 6 | **Mayoiuta** | NPU | `~/my_dv_proj/Mayoiuta/` | ⏳ 待做 | 16 |
| 7 | **CVA6** | CPU (工业级) | `~/my_dv_proj/cva6/` | ⏳ 待做 | 32 |
| 8 | **ProNoC** | NoC 互联 | `~/my_dv_proj/ProNoC/` | ⏳ 待做 | 24 |
| 9 | **Vortex** | GPU | `~/my_dv_proj/vortex/` | ⏳ 待做 | 24 |
| 10 | **NVDLA** | GPU/NPU | `~/my_dv_proj/hw/` | ⏳ 待做 | 48 |
| 11 | **XiangShan** | CPU (香山) | `~/my_dv_proj/XiangShan/` | ⏳ 待做 | - |
| 12 | **openwifi** | WiFi | `~/my_dv_proj/openwifi/` | ⏳ 待做 | - |
| 13 | **verilog-pcie** | PCIe | `~/my_dv_proj/verilog-pcie/` | ⏳ 待做 | - |

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