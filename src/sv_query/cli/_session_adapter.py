"""cli/_session_adapter.py — Session 失败响应 → CLI `fail()` 的唯一 adapter (D12).

库层 `sv_query.Session` 的失败信封是结构化 dict::

    {"ok": False, "op"?: str, "request_id"?: str,
     "error_code": str, "error": {"type": str, "message": str}}

CLI 的 transport 信封是既有 `cli._output.fail`::

    {"ok": False, "error": <str>, "error_code": <str>, ...extra}

两种形状**有意不同**：库层给 agent 结构化 `error` dict，CLI 保持既有
字符串信封（改形状会破坏所有命令的失败输出契约）。本模块统一的是：

- **code 词表**：只发出 `sv_query.cli.errors.ErrorCode` 中的值；词表外 → `E_INTERNAL`，
  并把原 code 显式保存在 `session_error_code`（不丢信息、不静默改写）；
- **message 来源**：取 `error.message`；缺失/非字符串/空串 → 显式 fallback
  文案（不输出空 message）。

非目标：不实现命令派发 `run()` 通用 adapter（D14），不构造第二个 Session。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import NoReturn

from sv_query.cli._output import fail
from sv_query.cli.errors import ErrorCode

_MISSING_MESSAGE = "session response has no error message"


def fail_from_session(
    response: object,
    *,
    json_output: bool,
    pretty: bool,
    context: str | None = None,
) -> NoReturn:
    """Map one Session **failure** response onto `cli._output.fail` (rc=1).

    Args:
        response: the dict returned by `Session.execute`; must be a failure
            response (`ok is False`).  Successful responses and non-mappings are
            programming errors → `TypeError` (never silently rendered as a
            failure).
        json_output: forwarded to `fail` (structured JSON vs human text).
        pretty: forwarded to `fail` (JSON indentation).
        context: optional human prefix, e.g. ``"capabilities 查询失败"``.

    Raises:
        TypeError: `response` is not a mapping or is not a failure response.
        typer.Exit: always rc=1 (via `fail`).
    """
    if not isinstance(response, Mapping):
        raise TypeError("fail_from_session expects a Session response mapping")
    if response.get("ok") is not False:
        raise TypeError("fail_from_session expects a Session failure response")

    message = _message(response)
    if context:
        message = f"{context}: {message}"

    code, extra = _cli_code(response.get("error_code"))
    fail(message, json_output, pretty, error_code=code.value, **extra)


def _message(response: Mapping) -> str:
    error = response.get("error")
    if isinstance(error, Mapping):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message
    return _MISSING_MESSAGE


def _cli_code(raw_code: object) -> tuple[ErrorCode, dict[str, str]]:
    """Return a CLI vocabulary code plus extra payload for out-of-vocabulary."""
    if isinstance(raw_code, str):
        try:
            return ErrorCode(raw_code), {}
        except ValueError:
            return ErrorCode.E_INTERNAL, {"session_error_code": raw_code}
    return ErrorCode.E_INTERNAL, {"session_error_code": repr(raw_code)}
