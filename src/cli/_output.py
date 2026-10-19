"""
cli/_output.py — CLI 输出的**单一实现**

[iter_246 B4] 背景: `def output_json(data, pretty)` 曾在 7 个命令模块各写一份
(graph / stats / diff / trace / dataflow / controlflow / expression), 7 份**逐字节相同**。
加字段、改缩进、改 `ensure_ascii` 都要改 7 处 —— 迟早分叉。这里收敛为一份。

[为什么文本输出没有一起收敛]
每个命令的文本版式互不相同 (树 / 表格 / 段落 / 分节), 强行统一需要先抽象版式 DSL,
那属于 T3 的结构性工作。本模块只收敛**形状固定**的部分: JSON 信封与失败信封。

[契约]
- 输出一律走 stdout (`print`), 便于 `capsys` 与管道
- `--json` 模式下**不得**再有额外的人类可读文本混进 stdout
- 失败必须显式: `fail()` 打印结构化信封并 `raise typer.Exit(code=1)`, 不返回空结果
"""
from __future__ import annotations

import json

import typer


def emit_json(data, pretty: bool = False) -> None:
    """把 dict 打印到 stdout。

    Args:
        data: 可 JSON 序列化的对象 (通常是 `{"ok": True, "command": ..., ...}` 信封)
        pretty: True 时 2 空格缩进
    """
    print(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False))


def fail(msg: str, json_output: bool, pretty: bool, **extra) -> None:
    """结构化失败 (rc=1)。禁止静默返回空结果。

    Args:
        msg: 人读错误消息
        json_output: True 时输出 `{"ok": false, "error": ...}` 信封
        pretty: JSON 缩进
        **extra: 附加字段 (如 `unknown=[...]`, `hint="..."`)

    Raises:
        typer.Exit: 始终 rc=1
    """
    payload = {"ok": False, "error": msg, **extra}
    if json_output:
        typer.echo(json.dumps(payload, indent=2 if pretty else None, ensure_ascii=False))
    else:
        typer.echo(f"❌ {msg}")
    raise typer.Exit(code=1)
