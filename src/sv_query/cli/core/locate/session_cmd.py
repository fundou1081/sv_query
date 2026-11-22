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
import sys

import typer

from sv_query import Session
from sv_query.cli._output import fail
from sv_query.cli._session_runner import SessionRenderOptions, emit_json_result, run_session
from sv_query.cli.errors import ErrorCode
from sv_query.session import E_HANDLER_FAILED, E_INVALID_REQUEST, error_response


def _capabilities_handler(request):
    # Lazy import: the hidden transport command must not force legacy CLI
    # modules to import capabilities provider at startup (A/B baseline).
    from sv_query.cli.core.locate.capabilities import _capabilities_provider

    return _capabilities_provider(request)


def _serve_line(raw: str, gs, session) -> dict:
    """Parse and execute one line; every failure is a structured envelope."""
    try:
        request = _json.loads(raw)
    except (TypeError, ValueError) as exc:
        return error_response(None, E_INVALID_REQUEST,
                              f"invalid request JSON: {exc}")
    if not isinstance(request, dict):
        return error_response(None, E_INVALID_REQUEST,
                              "request root must be an object")
    op = request.get("op") if isinstance(request.get("op"), str) else None
    rid = request.get("request_id") if isinstance(
        request.get("request_id"), str) else None
    try:
        gs.refresh()
    except Exception as exc:
        return error_response(op, E_HANDLER_FAILED, f"refresh failed: {exc}", rid)
    return session.execute(request)


def _serve(filelist: str | None, from_snapshot: str | None, file: str | None) -> None:
    """Local JSON-lines graph session: one build, many graph queries."""
    from sv_query import Session
    from sv_query.graph_session import GraphSession

    try:
        gs = GraphSession(
            file=file, filelist=filelist, from_snapshot=from_snapshot,
        )
    except Exception as exc:
        try:
            print(_json.dumps(error_response(None, E_INVALID_REQUEST, str(exc))),
                  flush=True)
        except BrokenPipeError:
            return
        raise typer.Exit(code=1) from None

    try:
        with gs:
            session = Session(handlers=gs.handlers())
            for raw in sys.stdin:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    print(_json.dumps(_serve_line(raw, gs, session),
                                      ensure_ascii=False), flush=True)
                except BrokenPipeError:
                    break
    except BrokenPipeError:
        return


def session_cmd(
    request: str = typer.Option(None, "--request", "-r", help="JSON request object"),
    serve: bool = typer.Option(False, "--serve", help="Read JSON-lines requests from stdin; one graph for all queries"),
    file: str = typer.Option(None, "--file", "-f", help="[serve] single source file"),
    filelist: str = typer.Option(None, "--filelist", help="[serve] filelist (.f/.fl)"),
    from_snapshot: str = typer.Option(None, "--from-snapshot", help="[serve] load graph/MIG from snapshot tag"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output (recommended)"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty JSON"),
) -> None:
    """Execute one Session request, or a local stdio graph session with --serve."""
    if serve:
        _serve(filelist=filelist, from_snapshot=from_snapshot, file=file)
        return
    if not request:
        fail("--request is required unless --serve is used", json_output,
             pretty, error_code=ErrorCode.E_INVALID_REQUEST.value)
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
