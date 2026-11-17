"""Hidden generic Session request adapter (P183.4 / D14).

Usage::

    sv_query session --request '{"op":"version"}' --json
    sv_query session --request '{"op":"capabilities"}' --json

This is a transport adapter, not a replacement for the Typer command tree
(D15).  It reuses the D13 runner and the D12 failure mapping so there is only
one Session call/error path.
"""
from __future__ import annotations

import json as _json

import typer

from cli._output import fail
from cli._session_runner import SessionRenderOptions, emit_json_result, run_session
from cli.errors import ErrorCode
from sv_query import Session


def _capabilities_handler(request):
    # Lazy import: the hidden transport command must not force legacy CLI
    # modules to import capabilities provider at startup (A/B baseline).
    from cli.core.locate.capabilities import _capabilities_provider

    return _capabilities_provider(request)


def session_cmd(
    request: str = typer.Option(..., "--request", "-r", help="JSON request object"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output (recommended)"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty JSON"),
) -> None:
    """Execute one transport-agnostic Session request (hidden developer entry)."""
    try:
        payload = _json.loads(request)
    except (TypeError, ValueError) as exc:
        fail(
            f"invalid --request JSON: {exc}",
            json_output,
            pretty,
            error_code=ErrorCode.E_INVALID_INPUT.value,
        )
    if not isinstance(payload, dict):
        fail(
            "invalid --request JSON: root must be an object",
            json_output,
            pretty,
            error_code=ErrorCode.E_INVALID_REQUEST.value,
        )

    options = SessionRenderOptions(
        json_output=json_output,
        pretty=pretty,
        context="session request failed",
    )
    session = Session(handlers={"capabilities": _capabilities_handler})
    result = run_session(session, payload, options)

    # This hidden command is JSON-first; even without --json it emits valid
    # JSON via the canonical emitter so callers never parse a bespoke format.
    emit_json_result(result, options)
