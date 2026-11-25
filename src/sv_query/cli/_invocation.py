"""CLI invocation context (P197.8): raw args without mutating sys.argv."""
from __future__ import annotations

import contextvars

_ARGS: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    "sv_query_cli_args", default=())


def set_invocation_args(args: list[str] | tuple[str, ...]) -> contextvars.Token:
    return _ARGS.set(tuple(args))


def reset_invocation_args(token: contextvars.Token) -> None:
    _ARGS.reset(token)


def invocation_args() -> tuple[str, ...]:
    return _ARGS.get()
