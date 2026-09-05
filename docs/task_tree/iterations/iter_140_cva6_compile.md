# Iteration 140: CVA6 strict 编译 — 特征代码提取 + 3 处真实修复

**Metadata**:
- **Iteration #**: 140
- **Task Tree Level**: L2 (Accuracy Claim L3 #7: CVA6/coralNPU/vortex strict 编译受阻)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ⚠️ 部分 (编译配方打通 + 3 修复; 完整建图受解码点阻塞, 下一轮续)

## 🎯 本次目标

方豆 "继续, cva6 如果编译不过去, 就把特征代码拿出来看看"。

## 🔬 实际结果

### 编译配方 (CVA6 core 153 文件 + config)

Flist.cva6 用 `${CVA6_REPO_DIR}` / `${TARGET_CFG}` 变量 →
`add_filelist(env={'CVA6_REPO_DIR':..., 'TARGET_CFG':'cv64a6_imafdc_sv39'})`。

### 阻塞 1: cvxif_example free-floating 模块 (44 错) — 特征代码

**特征代码**: `core/cvxif_example/*.sv` 的 type-param 模块
(cvxif_example_coprocessor: `parameter type cvxif_resp_t = logic` + body
`cvxif_resp_o.compressed_ready` 成员访问)。这些模块**从未被实例化**
(standalone 示例) → pyslang 对 free-floating 顶层模块用默认 type 检查 body
→ `logic` 无成员 → InvalidMemberAccess ×44 级联。

**最小复现** (pyslang 行为):
```systemverilog
module dec #(parameter type issue_req_t = logic) (
    input issue_req_t issue_req_i, output logic [31:0] o);
  assign o = issue_req_i.instr;   // 默认 logic 无成员 → InvalidMemberAccess
endmodule                          // ← 未实例化时 pyslang 检查 body 报错
```
**对照**: 加真实类型实例化 → OK (pyslang 实例化时替换类型)。Verilator/VCS
只 elaborate 顶层实例树 → 不报。**定性: pyslang elaboration 行为, 非 sv_query
bug**。**处置: filelist 剔除 3 个未实例化示例文件** (44→1)。

### 阻塞 2: paramOverride orphan 假错 (1 错) — 真 bug 修复

`stream_arbiter.N_INP=4` override (pulp axi pre-elab 兜底) 指向被 drop 的
模块 → `<command-line>:1 CouldNotResolveHierarchicalPath`。compiler.py 注释
早声明 "pre-elab 错误不影响实际 elaboration", 但 strict 模式仍 fatal。
**修** (compiler.py): `_try_retry_override_orphan` — 全部错误来自
`<command-line>` 且 identifier 匹配 override 模块 → 跳过该 override 重建
重编 (限 4 次; 重建须置 `self._comp=None` — 新建非 None 会让 _do_compile
开头直接 return → 0 SyntaxTree 空编译 getRoot=None, 初版踩坑)。

### 阻塞 3: 解码健壮性 (建图崩溃 ×3) — 真 bug 修复

CVA6 大设计暴露 pyslang symbol name 非 utf8 解码崩溃 (pybind getter):
1. `_common.py get_signal` NamedValue `.name` — UnicodeDecodeError → return
   None (sentinel, 注释)
2. `semantic_adapter._extract_signals_from_expr` MemberAccess f-string 拼接 —
   `_safe_attr(left,'symbol')` 返回对象非 str → safe_str 防护
3. `always_extractor` `hasattr(sym,'name')` 触发 pybind getter 解码炸 — 待修
   (下一轮)

### 当前状态

- ✅ CVA6 core strict **编译通过** (剔 3 示例文件 + override retry), root
  有效 (topInstances: cva6/copro_alu/fifo_v3)
- 🚧 完整建图: 解码点逐个修复中 (CVA6 规模暴露多处) — 下一轮续

## 💡 关键发现 / 决策

1. **特征代码方法论有效**: 完整项目编译失败 → 首个错误 → 最小复现 →
   区分 "pyslang 行为" (未实例化 type-param 预 elab) vs "真 bug"
   (override 假错 / 解码崩溃)。pyslang 行为类走 filelist 配方, 真 bug 修代码。
2. **override 假错不该 fatal**: override 仅兜底 free-floating pre-elab 默认
   参数, 模块被 drop = override 无用 — strict 下应跳过重编而非 raise。
3. **解码崩溃 = 大设计暴露的普遍健壮性债**: pyslang pybind 属性访问在非
   utf8 identifier 上抛 UnicodeDecodeError (含 hasattr!), 提取路径须统一
   safe_str/safe_attr 防护 — 逐点修是打地鼠, 后续宜扫全仓裸 .name 提取点。

## 📌 状态

- ✅ 编译阻塞双根因: cvxif 未实例化 type-param (pyslang 行为, filelist 配方)
  + override orphan 假错 (compiler.py 修复)
- ✅ 解码健壮性修复 ×2 (real bug); 第三处 (hasattr) 下一轮
- ✅ unit+cli 1514 passed (compiler 修复后); integration 回归见 commit
- 🚧 CVA6 完整建图: 解码点续修 (iter_141)
