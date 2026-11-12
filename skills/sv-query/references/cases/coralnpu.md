# CoralNPU 实战案例 (2026-06-28)

> 来源: SKILL.md 提取, 用户在主会话要求"用 skill 跑一下某个开源项目, 就以 google 的 npu 项目为例"
> 项目: Google CoralNPU (`<PROJ_DIR>/coralnpu`), 210 .sv + 6 .v, RISC-V Vector Ext

---

## 实际项目分析工作流 (CoralNPU 案例 2026-06-28)

完整分析 Google CoralNPU (`<PROJ_DIR>/coralnpu`, 210 .sv + 6 .v, RISC-V Vector Ext) 时学到的实战经验:

### Step 0: 先做**最小可行 subset** (不要一上来就跑全 filelist)

```bash
# 1. 找顶层 module (hdl/verilog/*.sv, 不是 _tb.sv)
ls <PROJ_DIR>/coralnpu/hdl/verilog/*.sv

# 2. 找 rvv/ 子模块
ls <PROJ_DIR>/coralnpu/hdl/verilog/rvv/design/

# 3. 排除 _tb.sv (testbench 拖慢 + 引入 include 错误)
find ... -name "*.sv" | grep -v _tb.sv > /tmp/coralnpu_simple.f
```

### Step 1: 先跑**最小 2 module** (5 min, 验证流程)

```bash
cat > /tmp/coralnpu_two.f << 'EOF'
+incdir+<PROJ_DIR>/coralnpu/hdl/verilog
<PROJ_DIR>/coralnpu/hdl/verilog/ClockGate.sv
<PROJ_DIR>/coralnpu/hdl/verilog/RstSync.sv
EOF

# 期望: 19 nodes / 23 edges / 0 errors (确认 elaboration 干净)
python3 run_cli.py stats --filelist /tmp/coralnpu_two.f --json -q
```

✅ 这个能 pass 表示 sv_query + filelist + pyslang 都 OK, 可以继续扩大.

### Step 2: 扩到子模块 + 顶级 (10-20 min, 验证子模块互连)

```bash
# 加 common cells + design (排除 RvvCore/RvvFrontEnd 复杂 typedef chain)
find <PROJ_DIR>/coralnpu/hdl/verilog -name "*.sv"     -not -name "*_tb.sv"     -not -path "*rvv/design/RvvCore*"     -not -path "*rvv/design/RvvFrontEnd*" > /tmp/coralnpu.f

python3 run_cli.py stats --filelist /tmp/coralnpu.f --json -q
# 期望: ~2100 nodes / ~2400 edges / 60+ errors (UndeclaredIdentifier, 可接受)
```

❌ RvvCore.sv 用 `RVVInstruction` typedef (在 rvv/inc/rvv_backend.svh), 但 .sv 文件不 \`include 该 svh.
→ **不要** 把 .svh 加到 filelist (sv_query 不自动预处理, 反而引入新错误).

### Step 3: 跑 5 个核心分析命令 (用 LLM-friendly flags)

```bash
# 标准 LLM 调用模板 (Phase 1+2 改进):
python3 run_cli.py trace fanout rstn_o --filelist /tmp/coralnpu_two.f --json -q

# 大项目用 --max-results cap
python3 run_cli.py trace fanout clk_i --filelist /tmp/coralnpu.f --json -q --max-results 50
# 返回: result.loads (max 50) + result.truncated + result.total_count

# 看具体信号的源码 evidence
python3 run_cli.py trace evidence clk_i --filelist /tmp/coralnpu_two.f --json -q
# 返回: credibility_score (内部 always/initial 才有效, top-level input = 0)
```

### 经验教训 (避免重蹈覆辙)

| 坑 | 症状 | 修法 |
|---|------|-----|
| **加 .svh 到 filelist** | 88 errors (vs 66 不加) | 不加 .svh, 用 typedef stub sv |
| **跑 84-file 全 filelist on low-memory machine (<16GB)** | 3+ min + OOM 风险 | 从 2 module 开始, 验证再扩大 |
| **trace evidence on top-level INPUT** | 空 evidence, credibility_score=0 | 这是对的 (input 不被驱动), 改看内部信号 |
| **不加 --quiet** | stdout 有 SWAP warning, LLM 解析失败 | **永远** `--quiet` 或 `-q` |
| **用 `--no-strict` 当 workaround** | 该 flag 已移除；elaboration 失败必须查 filelist/源码根因 | 不要绕过 strict；修输入 |
| **trace fanout clk (clock 信号)** | 0 loads (clock 不被 fanout) | 看内部 always_ff 驱动的 data 信号 |

### 大项目的"渐进式 elaboration"策略

1. **2 modules** → 确认 elaboration 干净 (ClockGate + RstSync)
2. **+ common cells** → 确认基础模块互连 (73 files)
3. **+ design, 排除复杂 typedef** → 看大部分 RTL (~2100 nodes)
4. **+ .svh headers** → 解析 typedef chain (会引入 ~20 个新错误, 权衡)
5. **+ RvvCore/RvvFrontEnd** → 全功能 (~3900 nodes, 88 errors)

每步验证 elaboration 干净 (errors 不增加 5x), 再继续. **不要** 一上来就跑全部.

---



| 错误 | 原因 | 修法 |
|------|------|------|
| `ModuleNotFoundError: pyslang` | 依赖没装 | `pip install -e <PROJ_DIR>/sv_query` |
| `ImportError: ... in _pyslang_compat` | pyslang 不在 [10, 12) 范围 | `pip install 'pyslang>=10.0.0,<12.0.0'` |
| `No module named top` | 信号名错了 | 先跑 `python3 run_cli.py stats -f file.sv` 看实际 module 名 |
| `Json decode error` | 源码不是合法 SV | 用 `--debug` 看 parser 输出 |
| `credibility_score < 0.5` | evidence 模糊 (只会是 0.0/0.2/0.4) | 看 `source_location` 人工确认 |
| stdout 含 SWAP warning 等 | stderr 污染 | 加 `--quiet`/`-q` 或 `2>/dev/null` |

详细 troubleshooting → [references/troubleshooting.md](../troubleshooting.md)

---


---

## 主要发现

1. **edff port naming mismatch** (CoralNPU 真 bug!)
   - 模块 port 是 `e`, 调用方用 `.en(single_push)` — CoralNPU 自己代码 bug, sv_query 抓到
2. **`$clog2(\\`VLEN)` macro 展开问题** — CoralNPU macro + pyslang 共同限制
3. **low-memory machine (<16GB) 大 filelist OOM** — 需要 `bytearray(4GB); time.sleep(3); del a` 强分配回收
