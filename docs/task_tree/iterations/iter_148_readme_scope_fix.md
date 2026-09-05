# Iteration 148: README 超能力宣传校对 — cdc/timing/risk 实验功能去宣传

**Metadata**:
- **Iteration #**: 148
- **Task Tree Level**: L3 (文档维护 — 能力宣传 vs 代码实际)
- **Parent Task**: README 如实化
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (无代码改动)

## 🎯 本次目标

方豆: "把文档里的, 超出现在代码能力的部分, 做一下更新。那些 cdc 的描述,
先去掉" — README 把实验性功能 (cdc/timing/risk) 当能力宣传, 超出实际。

## 🔬 实际结果

### 核查

- cdc.py/timing.py/risk.py 命令真实存在且注册 (main.py), 但 help 均标
  `[EXPERIMENTAL]`; 项目已有 `docs/EXPERIMENTAL_FEATURES.md` (cdc 等 6
  命令明确 "不承诺稳定/准确/文档完整")
- **README 入口把实验功能当能力列** (CLI 能力表 + Experimental 节) =
  超能力宣传 (用户入口误导)
- sva timing 子命令真实存在 (sva.py def timing) — 保留

### 修改 (README.md)

1. Experimental 节: 去掉 `cdc analyze / timing analyze / risk analyze`
   (同批 EXPERIMENTAL, 一并降级), 注明 "以 --help 为准, 不承诺稳定性";
   保留 coverage/verify/fix (有 usage 测试)
2. CLI 能力表: 删 `cdc/timing/risk | 跨时钟域/时序/风险` 行
3. 相关文档: 加 `EXPERIMENTAL_FEATURES.md` 链接 (实验边界读者可见)
4. 目录结构注释 (analyzer/ cdc/timing) 保留 — 代码结构描述非能力宣传

## 📌 状态

- ✅ README cdc/timing/risk 能力宣传去除 (剩代码结构注释)
- ✅ 实验边界链接可见
- 无代码改动 (命令保留, 自身已标 EXPERIMENTAL)
