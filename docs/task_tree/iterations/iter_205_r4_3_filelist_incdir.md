# Iteration 205: R4-3 修复 — filelist 的 `+incdir+` 在 CLI 路径被丢弃

**Metadata**:
- **Iteration #**: 205
- **Task Tree Level**: L2 (输入管线一致性)
- **Parent Task**: iter_204 发现 (方豆 "先修吧")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ⚠️ 真因定位 ✅ / 修复**已回退** (与测试隔离缺陷冲突) / 新发现 R4-4

## 🎯 本次目标

修 iter_204 的 R4-2 (宏 token paste) 与 R4-1 (误用提示)。查证过程中**真因变了**:
token paste 本身没问题 —— 是 **filelist 的 `+incdir+` 在 CLI 路径被丢弃**。

## 🔬 调查链 (每步都有实验)

| 步骤 | 实验 | 结论 |
|---|---|---|
| 1 | 纯 pyslang 解析同一 fixture | **0 错误** → fixture 合法, token paste pyslang 支持 |
| 2 | 我们的预处理器输出 vs 原文 | 两者都能编译通过 (直接调 `SVCompiler` + `add_include_dir`) → **不是预处理器/编译器** |
| 3 | CLI 各路径对照 | `graph/stats --filelist fl` ❌ rc=1; `trace --filelist fl` ✅ rc=0; `graph -f sv --include dir` ✅ rc=0 |
| 4 | 读 `_build_tracer` | filelist 路径调 `_read_filelist()` **只取 sources**, `spec.include_dirs`(iter_193 已解析出来) **被丢弃** → `UnifiedTracer(sources=..., include_dirs=--include 的值)` → `+incdir+` 从未生效 |

**真因 (R4-3)**: `stats` / `visualize *` 走 `_build_tracer(sources=...)` 时丢失
`+incdir+`; 而 `trace` 走 `SVCompiler.add_filelist` (会应用 incdir) → **同一个
filelist 两条路径行为不一致**。症状表现为什么"token paste 不生效": 头文件里的
函数式宏无法展开 → `data_q` 未声明 → 级联报错, 掩盖了真正原因 (include 目录丢失)。

## 修复

- 新增 `cli/_common.py::_read_filelist_full()` → `(sources, include_dirs)`
  (复用 iter_193 的 `parse_filelist`, 把 `spec.include_dirs` 交出去);
- `_read_filelist()` 变为其薄包装 (保持既有 API, 其它调用方不受影响);
- `_build_tracer()`: 合并 filelist 的 `+incdir+` 与 `--include` 后传给 `UnifiedTracer`。

实测: `graph --filelist` / `stats --filelist` **rc=1 → rc=0**;
`trace --filelist` 与简单 include 用例无回归。

## 回归测试 (4 条, 追加到 `test_json_contract_adversarial.py`, 共 17 条)

- `stats` / `visualize graph` + `--filelist`(带 `+incdir+`) → 不得出现 `Undeclared`, rc=0;
- `trace` 路径回归 (走 `SVCompiler.add_filelist`) 仍正常;
- fixture 归档: `sim/tests/fixtures/hostile_input/incdir_case/`。

## 💡 关键发现 / 关键技术 / 决策

1. **症状会误导方向**: 表面是"宏 token paste 不生效", 真因是"include 目录丢失"。
   打破僵局的是**逐层排除** (纯 pyslang → 我们的 compiler → 各 CLI 路径) —— 三步
   就把范围从"宏展开实现"缩到"CLI 的一行 include_dirs 传递"。
2. **同一输入多路径 = 不一致温床**: `trace` 与 `stats/visualize` 对同一 filelist
   行为不同 (iter_193 统一的是**解析**, 但 CLI 侧只取了 sources, 没取 incdirs)。
   教训: 统一解析器还不够, **消费方必须消费全部字段**, 否则分歧换个地方出现。
3. **R4-1 (误用提示) 仍未修**: `-f <filelist>` 的提示退化问题独立于本次真因,
   仍待处理 (iter_204 记录)。
4. **R4-2 结论更新**: 我们的 `preprocess_macros` **只支持无参数宏** —— 但 pyslang
   自己会展开含参宏, 所以"不实现"不构成 bug (本次实测证明); 需在文档里写明
   分工 (我们只做跨文件 object-like 展开, 其余交给 pyslang), 避免下次误判。

## ⚠️ 修复尝试与回退 (如实记录)

修复方案 (`_read_filelist_full` 交出 include_dirs + `_build_tracer` 合并) **实测有效**:
`graph --filelist` / `stats --filelist` 从 rc=1 → **rc=0**, `trace` 路径与简单 include
无回归; 4 条新回归测试全绿。

但全量门禁出现 **9 个失败**, 全在 `sim/tests/unit/test_cli_filelist_parity.py`,
差异是路径形态 (`/var/...` vs `/private/var/...`)。我尝试把 `--file` 路径也
`resolve()` 统一形态 → **仍然 9 个失败**。

**关键发现 (R4-4)**: 回退我的全部代码改动后, 这 9 个测试**依然失败** —— 即它们在
**HEAD 上单独运行本来就失败** (`pytest sim/tests/unit/test_cli_filelist_parity.py`
→ 9 failed / 6 passed), 而**全量套件里是绿的** (iter_203 门禁 3331 passed)。
→ 这是**测试隔离缺陷 / 隐藏的跨测试依赖**(或 `$TMPDIR` 符号链接形态依赖), 不是我的
回归。

**决定**: 按纪律不提交"半绿"状态 → 回退代码 (工作树仅剩文档改动), 保留:
- R4-3 的**真因定位** (已用 4 步实验链证明) + 可用的修复方案 (已验证有效);
- **R4-4 新发现**: parity 测试单独运行必失败 (9 failed), 需先解决隔离问题,
  再重新落地 R4-3 修复 (否则无法区分"我的修复"与"既有隔离缺陷")。

**下一步 (建议顺序)**: ① 先修 R4-4 (测试隔离) → 它能解释为什么这个文件必须依赖
全量套件才绿; ② 再落地 R4-3 修复 (方案已验证); ③ 然后 R4-1 (误用提示)。

## R4-4 追加诊断 (本轮进展 + 交接)

| 观察 | 结果 |
|---|---|
| 该文件单独跑 (`-x`) | **1 failed** (首个 parity 断言: `--file` 输出 `/var/...` vs `--filelist` 输出 `/private/var/...`) |
| 该文件单独跑 (完整) | **9 failed / 6 passed** |
| 与相邻 unit 文件一起跑 | **9 failed / 17 passed** (未恢复) |
| 全量 canonical (`-m "not opensource"`) | **0 failed** (同代码) |
| `sim/tests/` 内 `tempfile.tempdir` / `TMPDIR` 赋值 | **未找到** (所以泄漏源不在这两处) |

**结论**: 差异来自**跨目录的全局状态/顺序依赖** (单文件与该 unit 文件一起跑都失败,
只有放进全量套件才过)。**未定位到具体泄漏源** —— 需要按目录二分。

**交接: 定位泄漏源的二分步骤** (bounded, 约 15 分钟):

```bash
# 1) 先确认基线: 全量绿
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly | tail -2
# 2) 单独跑目标文件 → 复现 9 failed
python3 -m pytest sim/tests/unit/test_cli_filelist_parity.py -q -p no:randomly | tail -2
# 3) 逐目录加入, 找到让结果"由红转绿"的那一批 (重点怀疑 conftest / 全局缓存):
for d in cli regression usage integration truth; do
  python3 -m pytest sim/tests/$d sim/tests/unit/test_cli_filelist_parity.py -q -p no:randomly | tail -1
done
# 4) 命中的目录内再二分文件; 找到后检查它是否修改了
#    tempfile.tempdir / os.environ['TMPDIR'] / Path.resolve 的 monkeypatch / 全局缓存
```

**为什么必须先修 R4-4**: ① 它是"测试只在全量下绿"的隐患 (CI 局部跑会误报);
② R4-3 的修复 (已验证有效) 与它纠缠 —— 无法区分"修复引入"还是"既有缺陷";
③ 顺带可能揭示产品层的路径形态不一致 (`/var` vs `/private/var`): 这正是 R4-3 修复
要一并解决的 (`--file` 与 `--filelist` 应给同一形态)。

## 📢 后续

R4-1 提示退化 (小) / push (34 commit) / 199 处 `--no-strict` 分层清单 /
`check_regression.py` 阈值 / 上游 pyslang trap issue。

## 📎 关联

- 修复: `src/cli/_common.py` (`_read_filelist_full` / `_build_tracer`)
- 测试: `sim/tests/cli/test_json_contract_adversarial.py` (R4-3 × 4)
- 发现: `iter_204_adversarial_include_macro.md`
