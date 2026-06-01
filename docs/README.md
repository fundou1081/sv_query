# 开源 RTL 验证问题库 (sv_query)

> 基于多个开源项目 RTL 源码的系统化验证问题生成
>
> **核心方法**: 通过阅读实际 RTL 源代码，为每个模块生成 16-22 道验证问题
>
> **目标**: 训练对 RTL 内部信号路径的追踪能力，涵盖协议解析、数据转换、路由、真实场景四大维度

---

## 项目进度总览

| # | 项目 | 方向 | 本地路径 | 状态 | 问题数 |
|---|------|------|----------|------|--------|
| 1 | **OpenTitan** | 安全 MCU | `~/my_dv_proj/opentitan/` | ✅ 完成 | 176 题 |
| 2 | **CVA6** | CPU (工业级) | `~/my_dv_proj/cva6/` | ✅ 完成 | 待定 |
| 3 | **riscv-boom (BOOM)** | OoO CPU | `~/my_dv_proj/riscv-boom/` | 🆕 新下载 | 待定 |
| 4 | **rocket-chip** | 完整 SoC | `~/my_dv_proj/rocket-chip/` | 🆕 新下载 | 待定 |
| 5 | **NVDLA** | GPU/NPU | `~/my_dv_proj/hw/` | ✅ 完成 | 待定 |
| 6 | **ProNoC** | NoC 互联 | `~/my_dv_proj/ProNoC/` | ✅ 完成 | 待定 |
| 7 | **verilog-axi** | AXI 协议 | `~/my_dv_proj/verilog-axi/` | ✅ 已有 | 待定 |
| 8 | **Vortex** | GPU | `~/my_dv_proj/vortex/` | ✅ 已有 | 待定 |
| 9 | **XiangShan** | CPU (香山) | `~/my_dv_proj/XiangShan/` | ✅ 已有 | 待定 |
| 10 | **openwifi** | WiFi | `~/my_dv_proj/openwifi/` | ✅ 已有 | 待定 |
| 11 | **verilog-pcie** | PCIe | `~/my_dv_proj/verilog-pcie/` | ✅ 已有 | 待定 |
| 12 | **Mayoiuta** | NPU | `~/my_dv_proj/Mayoiuta/` | 🆕 新下载 | 待定 |
| 13 | **clacc** | NPU (Eyeriss-like) | `~/my_dv_proj/clacc/` | 🆕 新下载 | 待定 |

**总计：13 个开源项目，覆盖 CPU/GPU/NPU/互联/协议等方向**

---

## 项目路径汇总

### 🖥️ CPU 类

| 项目 | RTL 路径 | 总线 | 规模 |
|------|----------|------|------|
| OpenTitan | `hw/ip/*/rtl/` | TileLink | ~10 模块 |
| **CVA6** | `core/cva6.sv` | AXI4 + AXI4-Lite | ~20K 行 |
| **riscv-boom** | `src/main/scala/` | TileLink (Chisel) | ~15K 行 |
| **rocket-chip** | `src/main/scala/` | TileLink (Chisel) | ~20K 行 |
| **XiangShan** | `src/main/scala/` | Rocket + NoC | ~100K 行 |
| neorv32 | `rtl/` | Wishbone | 小型 |
| picorv32 | `rtl/` | Wishbone | 最小 |
| serv | `rtl/` | Wishbone | 串行 |

### 🎮 GPU 类

| 项目 | RTL 路径 | 总线 | 规模 |
|------|----------|------|------|
| **NVDLA** | `vmod/nvdla/*/` | AXI4 | **811K 行** |
| **Vortex** | `hw/` | 自定义 | 中型 |

### 🧠 NPU/AI加速器 类

| 项目 | RTL 路径 | 总线 | 规模 |
|------|----------|------|------|
| **Mayoiuta** | `hardware/` | AXI4 | 小型 (204K) |
| **clacc** | `./` (Verilog) | 自定义 | 小型 (844K) |

### 🔗 互联/协议 类

| 项目 | RTL 路径 | 总线 | 规模 |
|------|----------|------|------|
| **verilog-axi** | `rtl/` | AXI4 | ~10K 行 |
| **ProNoC** | `mpsoc/rtl/` | NoC | ~30K 行 |

### 📡 通信 类

| 项目 | RTL 路径 | 总线 | 规模 |
|------|----------|------|------|
| **openwifi** | `rtl/` | 自定义 WiFi | 68M |
| **verilog-pcie** | `rtl/` | PCIe + AXI | 8.3M |
| **verilog-ethernet** | `rtl/` | AXI 流式 | 14M |

---

## 问题结构（每模块 16-22 题）

| 阶段 | 维度 | 问题类型 |
|------|------|----------|
| Phase 1 | 基础 | 协议解析、信号定义 |
| Phase 2 | 中等 | 数据转换、路由路径 |
| Phase 3 | 刁钻 | 边界条件、竞争冒险 |
| Phase 4 | 真实场景 | 溯源分析、故障诊断 |

---

## 已完成项目详情

### OpenTitan (10 模块完成)

| # | 模块 | 难度 | 问题数 |
|---|------|------|--------|
| 1 | ADC_CTRL | ★★☆☆☆ | 21 |
| 2 | AES | ★★★★☆ | 21 |
| 3 | OTBN | ★★★★★ | 22 |
| 4 | DMA | ★★★☆☆ | 16 |
| 5 | I2C | ★★★★☆ | 16 |
| 6 | KMAC | ★★★☆☆ | 16 |
| 7 | TLUL | ★★★☆☆ | 16 |
| 8 | SYSRST_CTRL | ★★☆☆☆ | 16 |
| 9 | SPI_DEVICE | ★★★★☆ | 16 |
| 10 | USBDEV | ★★★★☆ | 16 |

---

## 文件结构

```
sv_query/docs/
├── opentitan实战/                    # OpenTitan 10 模块已完成
│   ├── README.md
│   ├── verification/
│   │   ├── adc_ctrl/...
│   │   ├── aes/...
│   │   └── ...
├── cva6实战/                         # 待建设
├── riscv-boom实战/                  # 待建设
├── rocket-chip实战/                 # 待建设
├── nvdla实战/                        # 待建设
├── pronoc实战/                       # 待建设
├── verilog-axi实战/                 # 待建设
├── vortex实战/                       # 待建设
├── xiangshan实战/                    # 待建设
├── openwifi实战/                     # 待建设
├── verilog-pcie实战/                 # 待建设
├── mayoiuta实战/                     # 待建设
└── clacc实战/                        # 待建设
```

---

## 可视化命令

### 信号图可视化

```bash
# 生成 DOT 文件（用于 Graphviz 渲染）
python run_cli.py visualize graph -f <file.sv> --dot output.dot

# 生成 PNG 图片（正方形比例）
dot -Tpng -Gsize=10 -Gratio=compress output.dot -o output.png

# 生成 HTML 交互式图
python run_cli.py visualize graph -f <file.sv> --html output.html

# 多文件项目 - 使用 include 路径
python run_cli.py visualize graph -f <file.sv> -I /path/include

# 多文件项目 - 使用 filelist (Verilator/Modelsim 风格)
python run_cli.py visualize graph -f top.sv --filelist project.fl
```

**图片比例**：默认生成正方形图片 (10 英寸，ratio=compress)，不裁剪超出内容。

### Filelist 支持

支持 Verilator / Modelsim 风格的 filelist 格式:

```filelist
// 注释
# 也可以用 # 开头

// include 搜索路径
+incdir+${CVA6_REPO_DIR}/core/include

// 环境变量展开
${CVA6_REPO_DIR}/core/cva6.sv
$HOME/my_project/module.sv

// 嵌套加载
-F vendor/hpdcache.Flist

// 宏定义
+define+DEBUG=1
```

详细语法: 参考 `docs/FILELIST.md`

### 验证缺口可视化

```bash
# 可视化高风险但无 SVA/Coverage 的信号
python run_cli.py visualize gap -f <file.sv> --dot gap.dot --png --min-risk 25
```

---

## 使用方法

1. **选择项目**：确定要学习的开源项目
2. **阅读问题清单**：`VERIFICATION_QUESTIONS.md`
3. **尝试回答**：基于 RTL 源码思考问题
4. **对照答案**：`results/ANSWERS.md` 检验
5. **追踪信号路径**：使用 `grep -n` 在 RTL 目录中定位关键信号

### 多文件项目

对于大型 SV 项目（如 CVA6, OpenTitan），使用 filelist:

```bash
export CVA6_REPO_DIR=/path/to/cva6
export TARGET_CFG=cv64a6_imafdc_sv39

python run_cli.py visualize graph -f $CVA6_REPO_DIR/core/cva6.sv --filelist $CVA6_REPO_DIR/core/Flist.cva6
```

详细示例: 参考 `docs/FILELIST.md` 的"实际案例：CVA6"章节。

---

## 下一步扩展计划

- [ ] CVA6 验证问题生成
- [ ] NVDLA 验证问题生成
- [ ] verilog-axi (AXI 协议专项)
- [ ] openwifi (WiFi 物理层)
- [ ] ProNoC (NoC 互联)

---

**最后更新**: 2026-06-01
**项目总数**: 13 个开源 RTL 项目
**测试通过**: 1265 (2026-06-01 刷新)