# Iteration 098: T11 — L4 SVG 布局 1:1 truth (非 generate)

**Metadata**:
- **Iteration #**: 098
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T11
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (9 passed)

## 🎯 本次目标

T11: 为 L4 SVG 渲染层 (非 generate) 建立 1:1 golden — 之前只有 case27 一个
SVG 级 truth, 普通数据流/分支图布局无锁定。

## 📊 当前状态 / 预期结果

- 渲染层 (V100 SVG) 几乎裸奔 (仅 case27)
- 预期: 端口/信号/op 标签 + 分类渲染 (fill 颜色) + case/条件边标签

## 🔬 实际结果

### 新增 test_layout_truth.py (9 测试, 真实 CLI subprocess 渲染)

**combined (5_combined)**:
- SVG 根 + 标题; 端口 a/b/c/y; 信号 sum/prod; op '+'/'×' + 常量 8'd128
- 分类渲染结构: op 橙 #fff3e0 ×5, 信号黄 #fff9c4 ×5

**with_case (9_case)**:
- 'case (2, b0, b1, b10, default, sel)' op 标签
- 4 条条件边标签精确 (sel==2'b0 / 2'b1 / 2'b10 / default)
- 端口 6 个 + 分支 '+' op

### 小修
- 首版 case 标签过滤 `"case" in l` 误匹配标题 'Dataflow: with_case' —
  收紧为 `startswith("case (")`

## 💡 关键发现 / 决策

1. SVG 级 golden 用 fill 颜色区分节点类别 (op 橙/信号黄) 做结构计数 —
   case27 同款手法, 扩展到普通数据流。
2. case 渲染 = case op 标签 + 边上条件标签 — 分支可见性可断言。

## 📌 状态

- ✅ test_layout_truth.py 9 passed (T11 完成)
- 下一步: T12 trace 查询精确 driver 集 (最后一项)
