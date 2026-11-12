# sv_query 故障排查

---

## 1. 找不到项目

```bash
# 检查 USER_PROFILE.md 主目录
ls <PROJ_DIR>/sv_query/run_cli.py
# 不存在? 重新 git clone
cd <PROJ_DIR>
git clone https://<REPO_URL>.git
```

---

## 2. 依赖问题

### 2.1 `ModuleNotFoundError: No module named 'pyslang'`

```bash
pip install pyslang
# 锁版本:
pip install 'pyslang>=10.0.0,<12.0.0'
```

### 2.2 `ImportError: cannot import name 'X' from 'pyslang'`

v11 把 X 移到 submodule。shim 处理, 如果还报:

```bash
# 检查 shim
python3 -c "from trace.core._pyslang_compat import X" 2>&1
# 报错? 重装 sv_query
cd <PROJ_DIR>/sv_query
pip install -e .
```

### 2.3 `ModuleNotFoundError: No module named 'trace'`

```bash
cd <PROJ_DIR>/sv_query
pip install -e .
# 或:
PYTHONPATH=<PROJ_DIR>/sv_query/src python3 run_cli.py ...
```

---

## 3. SV 解析错误

### 3.1 `SyntaxError: unexpected token`

```bash
python3 run_cli.py stats -f bad.sv
# 报 parser error
# 检查 bad.sv 的语法
```

### 3.2 `Unable to resolve ...`

```bash
# 模块间引用没找到
# 用 --filelist 把所有 .sv 列上
python3 run_cli.py stats --filelist filelist.f
# filelist.f 格式: Verilator 风格
# +incdir+path/
# file1.sv
# file2.sv
```

---

## 4. 信号找不到

### 4.1 `Signal not found: top.X`

```bash
# 看实际有的信号
python3 run_cli.py stats -f top.sv

# 看模块名
python3 run_cli.py stats -f top.sv | grep -i module
```

### 4.2 跨模块信号路径

```bash
# 子模块信号: <top>.<sub_inst>.<signal>
# 例: top.u_decoder.q 而不是 decoder.q

# 错:  trace fanin q
# 对:  trace fanin top.u_decoder.q
```

### 4.3 generate 块内信号

```bash
# 路径: top.gen_array[0].data
python3 run_cli.py trace fanin top.gen_array[0].data -f top.sv
```

---

## 5. evidence 不准确

### 5.1 `credibility_score < 0.5`

可能原因:
- 信号在 function 里 (没 always 块)
- 参数 parameter
- parser 失败 + fallback

**处理**: 报告用户, 给 `source_location` (含 file / line_start / line_end / column) 让人工看具体行。

### 5.2 evidence 完全缺失

```json
{"ok": false, "command": "trace_evidence", "error": "no evidence for signal top.X", "errors": ["no evidence for signal top.X"]}
```

原因:
- 信号没在任何 always/initial 里赋值
- 信号是 input 端口 (被外部驱动)

**处理**: 用 `trace fanin` 看上游, 或 `trace impact` 看下游。

---

## 6. 测试失败

### 6.1 改完代码测试挂了

```bash
cd <PROJ_DIR>/sv_query
python3 -m pytest sim/tests/ -q 2>&1 | tail -30
```

看 `sim/TEST_REPORT.md` 找具体失败。

### 6.2 跑某个测试

```bash
python3 -m pytest sim/tests/regression/test_X.py -v
```

### 6.3 加新测试

```bash
# 放 sim/tests/regression/test_<feature>.py
# 用 unittest 风格
# 跑全量确认不挂
```

---

## 7. 性能问题

### 7.1 大文件慢

```bash
# 加 --depth 限制 trace 深度
python3 run_cli.py trace fanin top.q -f big.sv --depth 3

# 用 filelist 分批处理
```

### 7.2 CDC 分析慢

CDC 检查走 `audit --checks cdc` (旧的 `cdc analyze` 命令已退役, 且没有 `--no-fanin-only` flag):

```bash
# 只跑 CDC 一项, 其它检查项不跑 (比默认全跑快)
python3 run_cli.py audit -f big.sv --checks cdc --json -q

# 大项目: 先用 filelist prune 裁掉无关 top, 再跑
python3 run_cli.py filelist prune --filelist big.f --top my_top --output small.f --apply
python3 run_cli.py audit --filelist small.f --checks cdc --json -q
```

---

## 8. git 提交失败

### 8.1 网络问题 (`github.com:443` 卡)

```bash
# 检查 ~/.gitconfig
grep -A 2 "^\[http\]" ~/.gitconfig

# proxy 应该是空或删除:
git config --global --unset http.proxy
git config --global --unset http.version

# 验证:
git push backup main   # 本仓库没有 origin remote
```

### 8.2 确认在正确的主目录

本机**只有一份** sv_query: `~/my_dv_proj/sv_query` (无下划线)。
历史的 `~/my_dvproj/` (有下划线) 别名目录**已不存在**, 不需要对比同步。

```bash
cd ~/my_dv_proj/sv_query && pwd
# /Users/fundou/my_dv_proj/sv_query

git remote -v
# backup / ssh-origin  (没有 origin)

git status --porcelain
```

要推送时注意**没有 `origin` remote**:
```bash
git push backup main       # https
git push ssh-origin main   # ssh
```

---

## 9. 完整诊断清单 (给 agent)

```bash
# 1. 位置
cd <PROJ_DIR>/sv_query && pwd

# 2. 依赖
python3 -c "import pyslang; print(f'pyslang {pyslang.__version__}')"

# 3. shim
python3 -c "from trace.core._pyslang_compat import SyntaxKind, SyntaxTree; print('compat OK')"

# 4. 项目状态
git status
git log --oneline | head -3

# 5. 跑 smoke
python3 -m pytest sim/tests/integration/test_pyslang_version_compat.py -q

# 6. 跑全量
python3 -m pytest sim/tests/ -q

# 7. 试一个命令
python3 run_cli.py stats -f sim/test_simple.sv
```


---

## 6. LLM 调用常见问题

### 6.1 stdout 含 SWAP warning, 破坏 JSON 解析

**症状**: `json.loads(stdout)` 失败, "Extra data: line 1 column N"

**根因**: pyslang 触发 SWAP 检测, stderr warning 通过 stderr 输出 (默认). LLM 工具如果不 redirect stderr 就污染 stdout.

**修法** (3 种):
```bash
# 1. 加 --quiet/-q 抑制所有 stderr
python3 run_cli.py trace fanin top.q -f top.sv --json -q

# 2. 重定向 stderr 到 /dev/null
python3 run_cli.py trace fanin top.q -f top.sv --json 2>/dev/null

# 3. 环境变量
SVQ_QUIET=1 python3 run_cli.py trace fanin top.q -f top.sv --json
```

> flag 必须放在**子命令之后** (`trace fanin ... --json`), 放中间 Typer 会报 unknown option。

### 6.2 错误信息是字符串, 难分类

**症状**: LLM 收到 `{"error": "[Errno 2] No such file ..."}`, 难做 if/else.

**修法**: 用 `error_code` 字段 (stable, 不会变):
```json
{"ok": false, "error_code": "E_FILE_NOT_FOUND", "error": "..."}
```

15 种 code (OK + 14 个 E_ 前缀), 权威定义见 `src/cli/errors.py` 的 `ErrorCode`:

```
OK, E_INTERNAL, E_USAGE, E_FILE_NOT_FOUND, E_FILELIST_NOT_FOUND,
E_FILELIST_INCOMPLETE, E_FILELIST_INVALID, E_INVALID_INPUT,
E_ELABORATION_FAILED, E_PARSE_ERROR, E_TARGET_NOT_FOUND,
E_SIGNAL_NOT_FOUND, E_SIGNAL_AMBIGUOUS, E_NO_DATA, E_PARTIAL_RESULT
```

⚠️ **不是每条失败都带 error_code**: 通用失败信封是 `{"ok": false, "error": ...}`,
其中 `error` 可能是**字符串**也可能是**对象** `{"type": "FileNotFoundError", "message": "..."}`
(实测: `stats` / `dataflow analyze` 用对象形式, `verify structural` / `graph nodes` 用字符串形式)。
所以解析时要兼容两种形状, 别直接对 `error` 调 `.lower()`。

完整 schema: `tools/llm_schema.json`

### 6.3 结果太多, 爆 LLM context

**症状**: `trace fanin clk` 返回 500 个 drivers, 超出 context window.

**修法**:
```bash
# 1. cap (最常用)
python3 run_cli.py trace fanin clk --max-results 100 --json -q
# 返回: result.truncated=true, result.total_count=500

# 2. depth 限制
python3 run_cli.py trace fanin clk --depth 3 --json -q

# 3. audit 只跑单项检查 (替代已退役的 --summary 模式)
python3 run_cli.py audit -f big.sv --checks cdc --json -q
```

### 6.4 JSON 字段含义不确定

**修法**: 读 `tools/llm_schema.json` (Draft 2020-12), 或跑验证脚本:
```bash
python3 tools/llm_schema_validate.py
```

### 6.5 LLM 应该用哪个 project root?

**答案**: 只有一个 —— `~/my_dv_proj/sv_query` (USER_PROFILE.md 主目录)。

本机**不存在** `~/my_dvproj/` (有下划线) 这个别名目录, 别再去那里找。
见 [locations.md](locations.md)。

---

## 7. filelist 工程问题 (跟 sv_query 代码无关)

### 7.1 报 "实例 'xxx' 的模块 'yyy' 没有找到端口定义"

**根因**: filelist 缺文件 (transitive dep 漏了).

**修法**: 用 `grep -l "module yyy" <PROJ_DIR>/<proj>/**/*.sv` 找模块定义, 加到 filelist.

### 7.2 Strict mode 报 InvalidMemberAccess

**根因**: pyslang C++ 解析器不支持该 SV 写法 (如 `.T(typedef_struct)` 参数化 port type).

**修法**:
1. **修 sv_query 代码: 不能修**, 这是 pyslang bug
2. **修 sv 输入**: 简化该 module (向 sv_query 项目方反馈)
3. **xfail 测试**: 在测试代码加 `@pytest.mark.xfail(reason="pyslang limitation")`

### 7.3 axi_pkg 类型找不到

**根因**: SV strict mode 要求 packages 先于使用它们的 modules. filelist 里 axi_pkg.sv 在 axi_demux.sv 后面.

**修法**: 把 axi_pkg.sv 移到 filelist 第一行 (在 include 之后, 其他 module 之前).


---

## 8. CoralNPU 实际项目案例

### 8.1 RvvCore.sv "UndeclaredIdentifier RVVInstruction"

**症状**: `RvvCore.sv:33 [UndeclaredIdentifier]`, `RvvFrontEnd.sv:38 [UndeclaredIdentifier]`

**根因**: RVVInstruction typedef 在 `rvv/inc/rvv_backend.svh`, 但 RvvCore.sv/RvvFrontEnd.sv 不 \`include 它 (依赖 build system filelist 顺序).

**错误修法** (按推荐顺序):
```bash
# 1. 排除复杂模块, 先分析其他部分 (推荐)
python3 run_cli.py stats --filelist <(find ... -name "*.sv"     -not -name "*_tb.sv"     -not -path "*RvvCore*"     -not -path "*RvvFrontEnd*") --json -q

# 2. 只看 RvvCore 内部信号 (不管 typedef 错误)
python3 run_cli.py trace evidence rstn_o --json -q

# 3. 接受错误: 这是 CoralNPU 项目自己的 build 顺序问题, 不是 sv_query bug
# 报 UndeclaredIdentifier 不代表 sv_query 错, 而代表"需要 build system 先 parse svh"
```

### 8.2 "实例 '' 的模块 '' 没有找到端口定义"

**症状**: stderr warning `实例 '' 的模块 '' 没有找到端口定义` (空字符串!)

**根因**: sv_query 在某些情况下解析失败, 输出空 instance name / 空 module name. 这是 sv_query 的小 bug.

**修法**: 这 warning 可以安全忽略, 不影响 elaboration 主流程. 后续 PR 应修 sv_query 让 warning 报告有效 instance.

### 8.3 84-file filelist 在 low-memory machine (<16GB) 上跑 3+ 分钟

**症状**: stats 命令长时间无输出, 可能 OOM.

**根因**: pyslang elaboration 需要连续内存, 84 .sv + 10 .svh + recursive deps 可能超出 <16GB RAM.

**修法**: 渐进式 filelist (见 SKILL.md "实际项目分析工作流" 章节):
1. 先 2 modules 验证 (~1s)
2. + common cells (~5s)
3. + design, 排除复杂 (~30s)
4. 最后 + 全部 (可能 3+ min, 接受)

跑前先 `python3 -c "import time; a = bytearray(4 * 1024**3); time.sleep(3); del a"` 回收内存.


---

## 9. CoralNPU $clog2 macro 解析限制

### 9.1 症状

```
rvv_backend.svh:70: error: too few arguments for '$clog2'; expected 1 but 0 were provided
  logic [`VL_WIDTH-1:0]         vl;
         ^~~~~~~~~
rvv_backend_define.svh:149: note: expanded from macro 'VL_WIDTH'
`define VL_WIDTH                $clog2(`VLEN)+1
                                ^~~~~~~~~~~~~
```

**根因**: `\`define VL_WIDTH $clog2(\`VLEN)+1` — macro 内部包了系统函数 `$clog2()`, 但 pyslang **没**递归展开内部 backtick macro. 结果 `$clog2()` 被解释成"0 个参数"。

**这不是 sv_query 的 bug**: 这是 pyslang C++ parser 的限制. SystemVerilog 标准说 macro 在 system function 里 **应该**展开, 但 pyslang 不做.

### 9.2 怎么验证是 macro 展开问题

```bash
# 1. 看具体错误
$clog2(... ) expected 1 but 0 were provided

# 2. 展开 trace:
#    `VL_WIDTH → $clog2(`VLEN)+1
#    `VLEN     → 没展开! pyslang 把 "(`VLEN)" 当字面量
#    → $clog2() 0 args
```

### 9.3 怎么绕过 (修 CoralNPU / 类似项目时)

```systemverilog
// ❌ 不工作 (pyslang bug)
`define VL_WIDTH  $clog2(`VLEN)+1
logic [`VL_WIDTH-1:0] vl;

// ✅ 工作 (显式 numeric)
`define VLEN      128
`define VL_WIDTH  $clog2(128)+1  // hard-code

// ✅ 工作 (绕开 macro in system function)
`define VL_WIDTH  8   // 128 → clog2(128) = 7 → +1 = 8
logic [`VL_WIDTH-1:0] vl;
```

### 9.4 影响范围

CoralNPU 整个 rvv backend 都有这问题:
- `rvv_backend.svh` (主 backend)
- `rvv_backend_alu.svh`
- `rvv_backend_alu_unit.sv`
- `rvv_backend_alu_unit_addsub.sv`
- 等 30+ 文件

→ **结论**: rvv_backend 完整 elaborate 需要 CoralNPU 自己修 macro, 或 sv_query 等 pyslang 修这个 bug.

### 9.5 sv_query 应该能做的 (后续 PR)

- [ ] **ADR-1**: 文档化 "macro in system function" 是已知限制
- [ ] **改进**: stats 输出里加 "macro_expansion_errors" 单独计数, 区别 elaboration errors
- [ ] **改进**: trace/evidence 命令在 macro 展开失败时仍可工作 (基于 instance-level symbolic)
