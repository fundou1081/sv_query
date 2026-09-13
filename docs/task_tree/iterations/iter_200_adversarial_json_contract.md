# Iteration 200: 对抗性测试 — 文本结构化输出契约 (发现 4 个问题)

**Metadata**:
- **Iteration #**: 200
- **Task Tree Level**: L2 (输出契约 / 对抗验证)
- **Parent Task**: 方豆 "来做一些对抗性测试，找到现有功能的问题"
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ⚠️ 4 个问题 (1 契约缺口 + 2 静默忽略 + 1 输入校验), 均已复现

## 🎯 本次目标

对抗性测试: 专打刚建立的"文本结构化输出"契约 (iter_198/199) 与边界组合, 目标是
**找出问题**, 不是验证通过。

## 🔬 实际结果

矩阵: 14 组组合 (正常/空文件/缺条目 filelist/不存在 module/二进制/flag 组合/参数边界),
4 组异常 + 3 项静默行为确认。

### F1 ⚠️ `--json` 的错误路径**不产出 JSON** (契约缺口, 最高价值)

| 用例 | 结果 |
|---|---|
| `pipeline --json` + filelist 缺条目 | rc=1, **stdout 空**, stderr 人读文本 |
| `pipeline --json` + 二进制文件 | rc=1, **stdout 空** |
| `timing analyze --json` + 文件不存在 | rc=1, **stdout 空** |
| `timing analyze --json` + 二进制 | rc=1, **stdout 空** |

成功信封是 `{ok: true, command, result}`, 但**没有错误信封** → 消费者 (LLM/脚本)
在"出错的时刻"反而拿不到结构化信息, 只能去 grep 人读 stderr。
这是 `ok` 字段的存在所暗示的契约缺一半。

### F2 ⚠️ `--json` 与输出类 flag 组合时**静默丢弃**请求的输出

`sv_query visualize pipeline -f X --json --svg /tmp/out.svg`
→ rc=0, **SVG 文件未生成**, 且**没有任何提示/警告** (实测 `SVG 文件生成=False`)。
用户显式要求的产物被静默忽略 → 与 AGENTS "不静默" 精神冲突。

### F3 ⚠️ `--json` 与 `--timing` 组合时**静默忽略语义**

`sv_query visualize pipeline -f X --json --timing`
→ rc=0, JSON 里**没有 timing 信息**, stderr 也**没有提示**。

### F4 ⚠️ `--max-paths` 负值被静默当成 0

| 参数 | 结果 |
|---|---|
| `--max-paths 0` | rc=0, 返回 0 条 (合理) |
| `--max-paths -1` | rc=0, **返回 0 条** (负值未报错, 也未取"全部"语义) |

## 💡 关键发现 / 关键技术 / 决策

1. **"成功契约"≠"完整契约"**: iter_198/199 建立的 `{ok, command, result}` 只覆盖
   成功路径; 对抗测试一打就露 —— **错误路径必须有对称的结构化表示**, 否则 `ok`
   字段只是装饰。
2. **`--json` 改变了输出模式, 但其它 flag 仍在"正常模式"语义上被解析** → 组合时
   静默失效 (F2/F3)。这类"模式互斥但无校验"是 CLI 最常见的坑。
3. **参数校验缺失 (F4)**: 负值/越界值应报错或定义明确语义 (如 -1 = 全部), 不能
   静默折叠成 0 —— 用户无法区分"没有关键路径"和"参数被吞了"。
4. **对抗矩阵成本很低, 收益高**: 14 组用例约 1 分钟跑完, 直接暴露 4 个问题;
   建议把它固化为回归测试 (见下"建议")。

## 📢 建议修复 (待方豆拍板)

| # | 问题 | 建议方案 | 代价 |
|---|---|---|---|
| F1 | 错误路径无 JSON | `--json` 时错误也打 **`{ok:false, command, error:{type, message}}`** 到 stdout (stderr 保留人读文本); 或明确"错误只走 stderr"并写进契约+测试 | 小 |
| F2/F3 | flag 静默忽略 | `--json` 与 `--svg/--png/--timing` 同时出现 → **显式告警** (stderr) 或直接报错; 也可让 JSON 嵌套其它输出路径 | 小 |
| F4 | 负值参数 | `--max-paths < 0` → 报错 (或定义 -1=全部) | 极小 |
| — | 建议固化 | 把本轮的 14 组对抗矩阵变成 `sim/tests/cli/test_json_contract_adversarial.py` (锁住 F1~F4 修复后的行为) | 小 |

## 📎 关联

- 被测契约: `iter_198_pipeline_json_output.md` / `iter_199_timing_json_tests.md`
- 相关纪律: AGENTS "禁止静默 fallback" / "失败必须可见"
