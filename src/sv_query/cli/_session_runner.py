"""Read-only Session runner (P183.4 / D13).

Single place that calls ``Session.execute`` for a CLI command:
validate the response, map failures to the existing CLI fail envelope, and
return the successful ``result`` mapping.  Rendering stays command-specific.

This is intentionally *not* a generic Typer dispatcher yet (D14); it is the
one runner that D14 can build on.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sv_query.cli._output import emit_json as _emit_json
from sv_query.cli._session_adapter import fail_from_session


@dataclass(frozen=True)
class SessionRenderOptions:
    """Explicit render/failure options; no env or global state."""

    json_output: bool = False
    pretty: bool = False
    context: str | None = None


def run_session(session, request: Mapping[str, object], options: SessionRenderOptions) -> dict:
    """Execute one Session request exactly once and return its ``result``.

    Raises:
        TypeError: response is not a mapping, ``ok`` is not bool, or a
            successful response lacks a mapping ``result``.
        typer.Exit: failure response (via ``fail_from_session``).
    """
    response = session.execute(request)
    if not isinstance(response, Mapping):
        raise TypeError("Session.execute must return a mapping")
    ok = response.get("ok")
    if ok is True:
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise TypeError("successful Session response has no mapping 'result'")
        return dict(result)
    if ok is False:
        fail_from_session(
            response,
            json_output=options.json_output,
            pretty=options.pretty,
            context=options.context,
        )
    raise TypeError("Session response 'ok' must be a bool")


def emit_json_result(result: object, options: SessionRenderOptions) -> None:
    """Print a JSON result via the canonical CLI emitter (no duplicate)."""
    _emit_json(result, pretty=options.pretty)
