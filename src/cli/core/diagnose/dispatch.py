"""
core/diagnose/dispatch.py — [iter_248 T2] `diagnose` 单一入口 (4 → 1)

[为什么合并]
原先是 4 个平级子命令 (`diagnose imports|report|timescale|widths`),
外加 4 个 `fix` 兼容别名 —— 默认可见面里占了 4 个位置, 而它们的**输入完全相同**
(`--filelist` + 编译日志级别), 区别只是"查什么"。agent 需要先猜"我该调哪个",
这正是命令面膨胀的典型形态。

[为什么不是 4 个 schema 硬合成一个]
四类检查的**输出载荷不同** (缺失依赖 / 错误分类 / 缺 timescale 的文件 / typedef 位宽),
所以不做 schema 合并; 只把"入口"合并: 一个命令 + 一个 `check` 枚举参数,
各自保留原有载荷形状 (`command` 字段仍写 `diagnose <check>`)。

[与 `fix` 老路径的关系]
`fix <check>` 已删除 (iter_248)。诊断本来就是只读的, "fix" 这个名字是历史误称;
写文件能力在 `tools/fix_*.py`。
"""
from __future__ import annotations

import typer

from cli.core.diagnose.imports import imports_cmd
from cli.core.diagnose.report import fix_report
from cli.core.diagnose.timescale import fix_timescale
from cli.core.diagnose.widths import widths_cmd

CHECKS = ("imports", "report", "timescale", "widths")

_HINT = "可选值: " + " | ".join(CHECKS)


def diagnose_cmd(
    check: str = typer.Argument(..., help=f"检查项 ({_HINT})"),
    filelist: str = typer.Option(..., "--filelist", help="Path to filelist (.f/.fl)"),
    project_root: str = typer.Option(
        None, "--project-root", help="[imports/widths] 要扫描的目录 (默认: filelist 所在目录的 src/)"
    ),
    timescale: str = typer.Option("1ns/1ps", "--timescale", help="[timescale] 要补的指令"),
    include_headers: bool = typer.Option(False, "--include-headers", help="[timescale] 也修 .svh 头文件"),
    top: int = typer.Option(20, "--top", "-n", help="[imports/widths] 最多显示 N 条建议"),
    log_level: str = typer.Option("ERROR", "--log-level", help="Compiler log level"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="[JSON] Pretty-print"),
) -> None:
    """只读诊断: 编译/依赖问题报告 (不改任何文件)。

    会写文件的动作在 tools/: `tools/fix_imports.py` (补 filelist)、
    `tools/fix_timescale.py` (补 timescale, 带 .bak 备份)。

    `check` 决定查什么:
      - `imports`   : UndeclaredIdentifier 的定义来源 → 建议补哪些文件到 filelist
      - `report`    : 按错误码分类的修复方向报告
      - `timescale` : 列出缺 `timescale 的文件
      - `widths`    : typedef `$clog2` 的真实位宽解析
    """
    if check not in CHECKS:
        typer.echo(f"❌ 未知检查项: {check}. {_HINT}", err=True)
        raise typer.Exit(code=2)

    if check == "imports":
        imports_cmd(filelist=filelist, project_root=project_root, log_level=log_level,
                    json_output=json_output, pretty=pretty, top=top)
    elif check == "widths":
        widths_cmd(filelist=filelist, project_root=project_root, log_level=log_level,
                   json_output=json_output, pretty=pretty, top=top)
    elif check == "report":
        fix_report(filelist=filelist, log_level=log_level,
                   json_output=json_output, pretty=pretty)
    else:  # timescale
        fix_timescale(filelist=filelist, timescale=timescale, include_headers=include_headers,
                      log_level=log_level, json_output=json_output, pretty=pretty)
