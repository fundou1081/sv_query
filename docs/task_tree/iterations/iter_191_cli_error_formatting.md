# Iteration 191: CLI 顶层统一错误格式化 — 垃圾输入不再甩 traceback

**Metadata**:
- **Iteration #**: 191
- **Task Tree Level**: L2 (CLI 边界人机接口)
- **Parent Task**: iter_189/190 边界正确性续 (方豆 "继续")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 7 类非法输入 × 3 子命令全部干净报错 + 40 测试锁死

## 🎯 本次目标

iter_190 的敌意输入矩阵显示: **没有崩溃了** (iter_189 修复), 但非法输入会把
**原始 Python traceback** 甩给用户 (rc=1, 满屏内部栈帧)。本轮把它统一成一行
可读错误, 并加永久回归锁。

## 📊 当前状态 / 预期结果

| 输入 | 修复前表现 |
|---|---|
| 二进制 / UTF-16 当源码 | rc=1 + `UnicodeDecodeError` traceback |
| 目录当文件 | rc=1 + `IsADirectoryError` traceback |
| 文件不存在 | rc=1 + `FileNotFoundError` traceback |
| filelist 当源码 | rc=1 + `CompilationError` traceback |
| filelist 不存在 | rc=1 + `FileNotFoundError: Filelist not found` traceback |
| filelist 条目缺失 | ⚠️ rc=0 (只有 warning) — 见"未决项" |

## 🔬 实际结果

### 1. 统一入口 `src/cli/main.py::run()`

```python
def run() -> None:
    from trace.core.compiler import CompilationError
    try:
        app()
    except (CompilationError, OSError, UnicodeDecodeError) as e:
        if os.environ.get("SVQ_DEBUG", "").lower() in ("1", "true", "yes"):
            raise                      # 开发者需要完整 traceback
        ... 只留前 5 行 + "完整内容: SVQ_DEBUG=1"
        print(f"sv_query: error: {head}", file=sys.stderr)
        raise SystemExit(1) from None
```

关键设计取舍 (**不违反 AGENTS "禁止静默 fallback"**):
- **只格式化"输入/环境类"异常** (OSError 家族 / UnicodeDecodeError /
  CompilationError) —— 这些是用户输入问题, 栈帧对用户零价值;
- **其他异常照旧抛**: 真 bug 必须留 traceback (不掩盖);
- **不吞错**: 退出码仍是 1, 信息仍在 stderr, 只是去掉了内部栈;
- `SVQ_DEBUG=1` 恢复完整 traceback (给开发者/未来 debug 留门)。

两个入口共用同一实现: `run_cli.py::main()` 与 console script
`cli._entry:main()` 都改为调用 `main.run()` (过去各自直接 `app()`, 行为可能漂移)。

### 2. 结果 (7 非法 × 3 子命令 = 21 组)

| 输入 | 现在 |
|---|---|
| 二进制 / UTF-16 | `sv_query: error: 'utf-8' codec can't decode byte 0x80 ...` (rc=1) |
| 目录当文件 | `sv_query: error: [Errno 21] Is a directory: '.../a_dir.sv'` (rc=1) |
| 文件不存在 | `sv_query: error: Source file not found: ...` (rc=1) |
| filelist 不存在 | `sv_query: error: Filelist not found: ...` (rc=1) |
| filelist 当源码 | `sv_query: error: <file>: 解析结果的根节点是 SyntaxKind.DivideExpression ...` (rc=1, 含"请用 --filelist"提示) |
| **traceback** | **全部消失**; `run_cli.py` 与 `sv_query` 一致 |

### 3. 永久回归锁 `sim/tests/integration/test_cli_hostile_input.py` (40 测试)

fixtures 落在 `sim/tests/fixtures/hostile_input/` (与项目 fixture 约定一致):
`filelist_as_sv.sv` / `not_verilog.txt` / `binary.sv` / `utf16.sv` / `a_dir.sv` /
`empty.sv` / `only_comment.sv` / `only_define.sv` / `only_endmodule.sv` /
`bom_crlf.sv` / `normal.sv`。

三条不变量 (把 iter_189/190/191 三件事一起锁死):
1. **绝不因信号死亡** (rc<0 / 133 / 134 / 138 / 139 都算崩);
2. **绝不打印 `Traceback (most recent call last)`**;
3. 非法输入必须 rc≠0 (不许"看起来成功"= 静默失败)。

外加**反向断言**: 7 类"合法但极端"输入 (空文件 / 仅注释 / 仅 `define` /
裸 `endmodule` / CRLF+BOM / 正常 module) 必须 **rc=0** —— 防止把守卫写成
"一律拒绝"这类过度防御。以及 `SVQ_DEBUG=1` 必须恢复 traceback。

## 💡 关键发现 / 关键技术 / 决策

1. **"崩溃 → 静默 → 不可读"是三层问题**: iter_189 解决"崩进程", iter_190 解决
   "静默", iter_191 解决"用户读不懂"。三层都处理完, 边界才算真的稳。
2. **两个入口必须共用同一实现**: `run_cli.py` 与 console script 各自 `app()`
   → 任何入口级改进都要改两处 (且容易漂移)。本轮统一到 `main.run()`。
3. **错误格式化 ≠ 吞错**: 判定标准 = 退出码仍非 0 + 信息仍在 stderr + 未预期
   异常不接 (真 bug 留栈) + 有 debug 开关。四条都满足才不算"掩盖问题"。
4. **反向断言同样重要**: 只测"非法输入要失败"会诱导出"一律拒绝"的守卫;
   必须同时锁"合法极端输入要成功"。

## 📢 未决项 (登记, 未擅自动)

| # | 事 | 现状 → 建议 |
|---|---|---|
| 1 | `--filelist` 条目**全部**缺失时 rc=0 (只有 warning) | 现在"可见但不致命": 用户仍会拿到空图。是否升级为错误取决于"filelist 是唯一输入源吗"的语义 → 建议方豆定; 注意 CLI 侧与 tracer 侧解析基准不同 (iter_190 结论), 不能在 CLI 侧无条件硬失败 |
| 2 | `check_regression.py` 阈值 / `reclaim_memory()` / 13 个 SVG skip / push | 见 iter_187~190 记录, 均待方豆拍板 |

## 📎 关联

- 代码: `src/cli/main.py` (`run()`)、`run_cli.py`、`src/cli/_entry.py`
- 测试: `sim/tests/integration/test_cli_hostile_input.py` (40)、
  fixtures `sim/tests/fixtures/hostile_input/`
- 前置: `iter_189_addsyntaxtree_sigtrap_guard.md` (崩溃)、
  `iter_190_except_pass_cleanup.md` (静默)
